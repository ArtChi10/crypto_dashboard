from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from django.conf import settings
from django.utils import timezone

from mlcore.loaders.binance_loader import BinanceMarketDataProvider
from mlcore.repositories import ArtifactRepository, DatasetRepository, ModelRepository
from mlcore.services.baseline_training_service import BaselineTrainingService
from mlcore.services.catboost_training_service import CatBoostTrainingService
from mlcore.services.dataset_preparation_service import DatasetPreparationService
from mlcore.services.full_pipeline_service import FullPipelineService
from mlcore.services.run_persistence_service import RunPersistenceService
from mlcore.services.run_pipeline_use_case import RunPipelineUseCase


@dataclass(frozen=True)
class BinancePipelineResult:
    run: Any | None
    raw_artifact: Any | None
    pipeline_result: Any | None
    error_message: str


class BinancePipelineUseCase:
    MAX_ERROR_MESSAGE_LENGTH = 1000
    INTERVAL_DELTAS = {
        "1m": pd.Timedelta(minutes=1),
        "3m": pd.Timedelta(minutes=3),
        "5m": pd.Timedelta(minutes=5),
        "15m": pd.Timedelta(minutes=15),
        "30m": pd.Timedelta(minutes=30),
        "1h": pd.Timedelta(hours=1),
        "2h": pd.Timedelta(hours=2),
        "4h": pd.Timedelta(hours=4),
        "6h": pd.Timedelta(hours=6),
        "8h": pd.Timedelta(hours=8),
        "12h": pd.Timedelta(hours=12),
        "1d": pd.Timedelta(days=1),
    }

    def __init__(
        self,
        market_data_provider: BinanceMarketDataProvider | None = None,
        artifact_repository: ArtifactRepository | None = None,
        dataset_repository: DatasetRepository | None = None,
        run_pipeline_use_case: RunPipelineUseCase | None = None,
    ) -> None:
        self.market_data_provider = market_data_provider or BinanceMarketDataProvider()
        self.artifact_repository = artifact_repository or ArtifactRepository(settings.MEDIA_ROOT)
        self.dataset_repository = dataset_repository or DatasetRepository()
        self.run_pipeline_use_case = run_pipeline_use_case or self._build_run_pipeline_use_case()

    def execute(
        self,
        symbol: str,
        interval: str,
        start_date: Any,
        end_date: Any,
        target_horizon: int,
        train_baseline: bool = True,
        train_catboost: bool = True,
        enable_forecast_replay: bool = False,
        replay_steps: int = 5,
    ) -> BinancePipelineResult:
        run = None
        raw_artifact = None
        try:
            run = self._create_run(
                symbol=symbol,
                interval=interval,
                start_date=start_date,
                end_date=end_date,
                target_horizon=target_horizon,
            )
            raw_df = self.market_data_provider.get_ohlcv(
                symbol=symbol,
                interval=interval,
                start=start_date,
                end=end_date,
            )
            raw_artifact = self._save_raw_dataset(run, raw_df, symbol=symbol)
            future_df = None
            if enable_forecast_replay:
                future_start, future_end = self._forecast_replay_window(
                    end_date=end_date,
                    interval=interval,
                    target_horizon=target_horizon,
                    replay_steps=replay_steps,
                )
                future_df = self.market_data_provider.get_ohlcv(
                    symbol=symbol,
                    interval=interval,
                    start=future_start,
                    end=future_end,
                )
            pipeline_result = self.run_pipeline_use_case.execute(
                run,
                raw_df,
                train_baseline=train_baseline,
                train_catboost=train_catboost,
                future_df=future_df,
                enable_forecast_replay=enable_forecast_replay,
                replay_steps=replay_steps,
            )
            return BinancePipelineResult(
                run=run,
                raw_artifact=raw_artifact,
                pipeline_result=pipeline_result,
                error_message="",
            )
        except Exception as exc:
            error_message = self._short_error_message(exc)
            if run is not None:
                self._mark_failed(run, error_message)
            return BinancePipelineResult(
                run=run,
                raw_artifact=raw_artifact,
                pipeline_result=None,
                error_message=error_message,
            )

    @staticmethod
    def _create_run(
        symbol: str,
        interval: str,
        start_date: Any,
        end_date: Any,
        target_horizon: int,
    ) -> Any:
        from runs.models import PipelineRun

        return PipelineRun.objects.create(
            name=f"Binance pipeline {symbol} {interval}",
            status=PipelineRun.Status.CREATED,
            symbols_json=[symbol],
            interval=interval,
            start_date=start_date,
            end_date=end_date,
            target_horizon=target_horizon,
            initiated_by="binance_cli",
        )

    def _save_raw_dataset(self, run: Any, raw_df: pd.DataFrame, symbol: str) -> Any:
        from runs.models import DatasetArtifact

        raw_path = self.artifact_repository.dataset_path(
            DatasetArtifact.ArtifactType.RAW,
            run.id,
            symbol=symbol,
            extension="parquet",
        )
        self.dataset_repository.save(raw_df, raw_path)
        return DatasetArtifact.objects.create(
            run=run,
            artifact_type=DatasetArtifact.ArtifactType.RAW,
            symbol=symbol,
            file_path=self._metadata_path(raw_path),
            row_count=len(raw_df),
        )

    def _build_run_pipeline_use_case(self) -> RunPipelineUseCase:
        model_repository = ModelRepository()
        dataset_preparation_service = DatasetPreparationService(
            artifact_repository=self.artifact_repository,
            dataset_repository=self.dataset_repository,
        )
        baseline_training_service = BaselineTrainingService(
            artifact_repository=self.artifact_repository,
            model_repository=model_repository,
        )
        catboost_training_service = CatBoostTrainingService(
            artifact_repository=self.artifact_repository,
            model_repository=model_repository,
        )
        full_pipeline_service = FullPipelineService(
            dataset_preparation_service=dataset_preparation_service,
            baseline_training_service=baseline_training_service,
            catboost_training_service=catboost_training_service,
            dataset_repository=self.dataset_repository,
        )
        return RunPipelineUseCase(
            full_pipeline_service=full_pipeline_service,
            persistence_service=RunPersistenceService(),
        )

    @staticmethod
    def _metadata_path(path: str | Path) -> str:
        path = Path(path)
        if not path.is_absolute():
            return path.as_posix()

        try:
            return path.resolve().relative_to(Path(settings.MEDIA_ROOT).resolve()).as_posix()
        except ValueError:
            return path.as_posix()

    @staticmethod
    def _mark_failed(run: Any, error_message: str) -> None:
        run.refresh_from_db()
        run.status = run.Status.FAILED
        if run.started_at is None:
            run.started_at = timezone.now()
        run.finished_at = timezone.now()
        run.error_message = error_message
        run.save(update_fields=["status", "started_at", "finished_at", "error_message"])

    @classmethod
    def _short_error_message(cls, exc: Exception) -> str:
        message = str(exc) or exc.__class__.__name__
        return message[: cls.MAX_ERROR_MESSAGE_LENGTH]

    @classmethod
    def _forecast_replay_window(
        cls,
        end_date: Any,
        interval: str,
        target_horizon: int,
        replay_steps: int,
    ) -> tuple[pd.Timestamp, pd.Timestamp]:
        step = cls._interval_delta(interval)
        try:
            total_steps = int(target_horizon) + int(replay_steps)
        except (TypeError, ValueError) as exc:
            raise ValueError("target_horizon and replay_steps must be integers.") from exc
        if total_steps < 2:
            raise ValueError("target_horizon and replay_steps must cover at least two candles.")

        end_timestamp = pd.to_datetime(end_date)
        if pd.isna(end_timestamp):
            raise ValueError("end_date must be a valid date or datetime.")

        future_start = end_timestamp + step
        future_end = end_timestamp + (step * total_steps)
        return future_start, future_end

    @classmethod
    def _interval_delta(cls, interval: str) -> pd.Timedelta:
        normalized = str(interval or "").strip()
        if normalized not in cls.INTERVAL_DELTAS:
            supported = ", ".join(sorted(cls.INTERVAL_DELTAS))
            raise ValueError(
                f"Unsupported replay interval: {interval!r}. Expected one of: {supported}."
            )
        return cls.INTERVAL_DELTAS[normalized]
