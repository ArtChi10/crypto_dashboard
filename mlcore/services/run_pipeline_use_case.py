from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.utils import timezone

from mlcore.services.full_pipeline_service import FullPipelineResult, FullPipelineService
from mlcore.services.run_persistence_service import RunPersistenceResult, RunPersistenceService


@dataclass(frozen=True)
class RunPipelineResult:
    full_pipeline_result: FullPipelineResult
    persistence_result: RunPersistenceResult


class RunPipelineUseCase:
    DEFAULT_HORIZON = 3
    MAX_ERROR_MESSAGE_LENGTH = 1000

    def __init__(
        self,
        full_pipeline_service: FullPipelineService | None = None,
        persistence_service: RunPersistenceService | None = None,
    ) -> None:
        self.full_pipeline_service = full_pipeline_service or FullPipelineService()
        self.persistence_service = persistence_service or RunPersistenceService()

    def execute(
        self,
        run: Any,
        raw_df: Any,
        train_baseline: bool = True,
        train_catboost: bool = True,
        future_df: Any | None = None,
        enable_forecast_replay: bool = False,
        replay_steps: int = 5,
    ) -> RunPipelineResult:
        self._mark_running(run)
        try:
            full_pipeline_result = self.full_pipeline_service.run(
                raw_df,
                run_id=run.id,
                horizon=run.target_horizon or self.DEFAULT_HORIZON,
                symbol=self._single_symbol(run.symbols_json),
                train_baseline=train_baseline,
                train_catboost=train_catboost,
                future_df=future_df,
                enable_forecast_replay=enable_forecast_replay,
                replay_steps=replay_steps,
            )
            persistence_result = self.persistence_service.save_full_pipeline_result(
                run,
                full_pipeline_result,
            )
            self._mark_success(run)
            return RunPipelineResult(
                full_pipeline_result=full_pipeline_result,
                persistence_result=persistence_result,
            )
        except Exception as exc:
            self._mark_failed(run, exc)
            raise

    @staticmethod
    def _mark_running(run: Any) -> None:
        run.status = run.Status.RUNNING
        run.started_at = timezone.now()
        run.finished_at = None
        run.error_message = ""
        run.save(update_fields=["status", "started_at", "finished_at", "error_message"])

    @staticmethod
    def _mark_success(run: Any) -> None:
        run.status = run.Status.SUCCESS
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "finished_at"])

    @classmethod
    def _mark_failed(cls, run: Any, exc: Exception) -> None:
        run.status = run.Status.FAILED
        run.finished_at = timezone.now()
        run.error_message = cls._short_error_message(exc)
        run.save(update_fields=["status", "finished_at", "error_message"])

    @classmethod
    def _short_error_message(cls, exc: Exception) -> str:
        message = str(exc) or exc.__class__.__name__
        return message[: cls.MAX_ERROR_MESSAGE_LENGTH]

    @staticmethod
    def _single_symbol(symbols: Any) -> str | None:
        if isinstance(symbols, (list, tuple)) and len(symbols) == 1:
            return str(symbols[0])
        return None
