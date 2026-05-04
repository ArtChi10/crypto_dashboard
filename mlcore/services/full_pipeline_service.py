from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from mlcore.repositories import ArtifactRepository, DatasetRepository, ModelRepository
from mlcore.services.baseline_training_service import (
    BaselineTrainingResult,
    BaselineTrainingService,
)
from mlcore.services.catboost_training_service import (
    CatBoostTrainingResult,
    CatBoostTrainingService,
)
from mlcore.services.dataset_preparation_service import (
    DatasetPreparationResult,
    DatasetPreparationService,
)
from mlcore.services.dummy_training_service import DummyTrainingResult, DummyTrainingService
from mlcore.services.forecast_replay_service import ForecastReplayService
from mlcore.services.report_service import (
    FeatureImportanceReportService,
    ForecastReplayReportService,
    MetricsComparisonReportService,
    PeriodStabilityReportService,
    TargetDistributionReportService,
)


@dataclass(frozen=True)
class FullPipelineResult:
    preparation_result: DatasetPreparationResult
    baseline_result: BaselineTrainingResult | None
    catboost_result: CatBoostTrainingResult | None
    dummy_result: DummyTrainingResult | None = None
    target_distribution_report_path: Path | None = None
    metrics_comparison_report_path: Path | None = None
    feature_importance_report_path: Path | None = None
    stability_table_report_path: Path | None = None
    stability_plot_report_path: Path | None = None
    forecast_replay_report_path: Path | None = None
    forecast_replay_table_path: Path | None = None


class FullPipelineService:
    def __init__(
        self,
        dataset_preparation_service: DatasetPreparationService | None = None,
        dummy_training_service: DummyTrainingService | None = None,
        baseline_training_service: BaselineTrainingService | None = None,
        catboost_training_service: CatBoostTrainingService | None = None,
        dataset_repository: DatasetRepository | None = None,
        target_distribution_report_service: TargetDistributionReportService | None = None,
        metrics_comparison_report_service: MetricsComparisonReportService | None = None,
        period_stability_report_service: PeriodStabilityReportService | None = None,
        feature_importance_report_service: FeatureImportanceReportService | None = None,
        forecast_replay_service: ForecastReplayService | None = None,
        forecast_replay_report_service: ForecastReplayReportService | None = None,
    ) -> None:
        self.artifact_repository = self._infer_artifact_repository(
            dataset_preparation_service,
            dummy_training_service,
            baseline_training_service,
            catboost_training_service,
        ) or ArtifactRepository(Path("media"))
        model_repository = self._infer_model_repository(
            dummy_training_service,
            baseline_training_service,
            catboost_training_service,
        )
        self.dataset_repository = (
            dataset_repository
            or self._infer_dataset_repository(dataset_preparation_service)
            or DatasetRepository()
        )
        self.dataset_preparation_service = dataset_preparation_service or DatasetPreparationService(
            artifact_repository=self.artifact_repository,
            dataset_repository=self.dataset_repository,
        )
        self.dummy_training_service = dummy_training_service or DummyTrainingService(
            artifact_repository=self.artifact_repository,
            model_repository=model_repository,
        )
        self.baseline_training_service = baseline_training_service or BaselineTrainingService(
            artifact_repository=self.artifact_repository,
            model_repository=model_repository,
        )
        self.catboost_training_service = catboost_training_service or CatBoostTrainingService(
            artifact_repository=self.artifact_repository,
            model_repository=model_repository,
        )
        self.target_distribution_report_service = (
            target_distribution_report_service or TargetDistributionReportService()
        )
        self.metrics_comparison_report_service = (
            metrics_comparison_report_service or MetricsComparisonReportService()
        )
        self.period_stability_report_service = (
            period_stability_report_service or PeriodStabilityReportService()
        )
        self.feature_importance_report_service = (
            feature_importance_report_service or FeatureImportanceReportService()
        )
        self.forecast_replay_service = forecast_replay_service or ForecastReplayService()
        self.forecast_replay_report_service = (
            forecast_replay_report_service or ForecastReplayReportService()
        )

    def run(
        self,
        raw_df: Any,
        run_id: int,
        horizon: int = 3,
        symbol: str | None = None,
        train_dummy: bool = True,
        train_baseline: bool = True,
        train_catboost: bool = True,
        future_df: Any | None = None,
        enable_forecast_replay: bool = False,
        replay_steps: int = 5,
    ) -> FullPipelineResult:
        if not train_dummy and not train_baseline and not train_catboost:
            raise ValueError("At least one training flag must be True.")

        preparation_result = self.dataset_preparation_service.prepare(
            raw_df,
            run_id=run_id,
            horizon=horizon,
            symbol=symbol,
        )
        final_df = self.dataset_repository.load(preparation_result.final_path)
        target_distribution_report_path = self.target_distribution_report_service.build(
            final_df,
            self._report_path(
                "target_distribution",
                run_id=run_id,
                final_path=preparation_result.final_path,
                extension="png",
            ),
        )

        dummy_result = None
        if train_dummy:
            dummy_result = self.dummy_training_service.train_and_evaluate(
                final_df,
                run_id=run_id,
            )

        baseline_result = None
        if train_baseline:
            baseline_result = self.baseline_training_service.train_and_evaluate(
                final_df,
                run_id=run_id,
            )

        catboost_result = None
        if train_catboost:
            catboost_result = self.catboost_training_service.train_and_evaluate(
                final_df,
                run_id=run_id,
            )

        metrics_comparison_report_path = None
        metrics_by_model = self._metrics_by_model(dummy_result, baseline_result, catboost_result)
        if metrics_by_model:
            metrics_comparison_report_path = self.metrics_comparison_report_service.build(
                metrics_by_model,
                self._report_path(
                    "metrics_plot",
                    run_id=run_id,
                    final_path=preparation_result.final_path,
                    extension="png",
                ),
            )

        stability_table_report_path = None
        stability_plot_report_path = None
        predictions_by_model = self._predictions_by_model(
            dummy_result,
            baseline_result,
            catboost_result,
        )
        if predictions_by_model:
            stability_report = self.period_stability_report_service.build(
                predictions_by_model,
                self._report_path(
                    "stability_table",
                    run_id=run_id,
                    final_path=preparation_result.final_path,
                    extension="csv",
                ),
                self._report_path(
                    "stability_plot",
                    run_id=run_id,
                    final_path=preparation_result.final_path,
                    extension="png",
                ),
            )
            stability_table_report_path = stability_report.table_path
            stability_plot_report_path = stability_report.plot_path

        feature_importance_report_path = None
        if catboost_result is not None and catboost_result.feature_importances:
            feature_importance_report_path = self.feature_importance_report_service.build(
                list(catboost_result.feature_importances),
                list(catboost_result.feature_importances.values()),
                self._report_path(
                    "feature_importance",
                    run_id=run_id,
                    final_path=preparation_result.final_path,
                    extension="png",
                ),
            )

        forecast_replay_report_path = None
        forecast_replay_table_path = None
        if enable_forecast_replay:
            forecast_replay_table_path, forecast_replay_report_path = self._build_forecast_replay(
                history_df=raw_df,
                future_df=future_df,
                run_id=run_id,
                final_path=preparation_result.final_path,
                horizon=horizon,
                replay_steps=replay_steps,
                dummy_result=dummy_result,
                baseline_result=baseline_result,
                catboost_result=catboost_result,
            )

        return FullPipelineResult(
            preparation_result=preparation_result,
            baseline_result=baseline_result,
            catboost_result=catboost_result,
            dummy_result=dummy_result,
            target_distribution_report_path=target_distribution_report_path,
            metrics_comparison_report_path=metrics_comparison_report_path,
            feature_importance_report_path=feature_importance_report_path,
            stability_table_report_path=stability_table_report_path,
            stability_plot_report_path=stability_plot_report_path,
            forecast_replay_report_path=forecast_replay_report_path,
            forecast_replay_table_path=forecast_replay_table_path,
        )

    @staticmethod
    def _metrics_by_model(
        dummy_result: DummyTrainingResult | None,
        baseline_result: BaselineTrainingResult | None,
        catboost_result: CatBoostTrainingResult | None,
    ) -> dict[str, dict[str, Any]]:
        metrics_by_model = {}
        if dummy_result is not None:
            metrics_by_model["dummy"] = dummy_result.metrics
        if baseline_result is not None:
            metrics_by_model["baseline"] = baseline_result.metrics
        if catboost_result is not None:
            metrics_by_model["catboost"] = catboost_result.metrics
        return metrics_by_model

    @staticmethod
    def _predictions_by_model(
        dummy_result: DummyTrainingResult | None,
        baseline_result: BaselineTrainingResult | None,
        catboost_result: CatBoostTrainingResult | None,
    ) -> dict[str, pd.DataFrame]:
        predictions_by_model = {}
        if dummy_result is not None and not dummy_result.test_predictions.empty:
            predictions_by_model["dummy"] = dummy_result.test_predictions
        if baseline_result is not None and not baseline_result.test_predictions.empty:
            predictions_by_model["baseline"] = baseline_result.test_predictions
        if catboost_result is not None and not catboost_result.test_predictions.empty:
            predictions_by_model["catboost"] = catboost_result.test_predictions
        return predictions_by_model

    def _build_forecast_replay(
        self,
        history_df: Any,
        future_df: Any | None,
        run_id: int,
        final_path: Path,
        horizon: int,
        replay_steps: int,
        dummy_result: DummyTrainingResult | None,
        baseline_result: BaselineTrainingResult | None,
        catboost_result: CatBoostTrainingResult | None,
    ) -> tuple[Path, Path]:
        if future_df is None:
            raise ValueError("future_df must be provided when forecast replay is enabled.")

        model_result = self._forecast_replay_model_result(
            dummy_result=dummy_result,
            baseline_result=baseline_result,
            catboost_result=catboost_result,
        )
        if model_result.model is None:
            raise ValueError("Selected forecast replay model is not available in memory.")

        replay_df = self.forecast_replay_service.build_replay(
            history_df=history_df,
            future_df=future_df,
            model=model_result.model,
            feature_columns=model_result.feature_columns,
            horizon=horizon,
            replay_steps=replay_steps,
        )
        if replay_df.empty:
            raise ValueError("Forecast replay did not produce any rows.")

        table_path = self._report_path(
            "forecast_replay_table",
            run_id=run_id,
            final_path=final_path,
            extension="csv",
        )
        self.dataset_repository.save(replay_df, table_path)

        report_path = self.forecast_replay_report_service.build(
            history_df,
            replay_df,
            self._report_path(
                "forecast_replay",
                run_id=run_id,
                final_path=final_path,
                extension="png",
            ),
        )
        return table_path, report_path

    @staticmethod
    def _forecast_replay_model_result(
        dummy_result: DummyTrainingResult | None,
        baseline_result: BaselineTrainingResult | None,
        catboost_result: CatBoostTrainingResult | None,
    ) -> CatBoostTrainingResult | BaselineTrainingResult | DummyTrainingResult:
        if catboost_result is not None:
            return catboost_result
        if baseline_result is not None:
            return baseline_result
        if dummy_result is not None:
            return dummy_result
        raise ValueError("No trained model is available for forecast replay.")

    def _report_path(
        self,
        report_type: str,
        run_id: int,
        final_path: Path,
        extension: str,
    ) -> Path:
        artifact_repository = self.artifact_repository
        if artifact_repository is None:
            artifact_repository = ArtifactRepository(self._base_dir_from_final_path(final_path))
        return artifact_repository.report_path(report_type, run_id=run_id, extension=extension)

    @staticmethod
    def _base_dir_from_final_path(final_path: Path) -> Path:
        final_path = Path(final_path)
        if final_path.parent.name == "final" and final_path.parent.parent.name == "datasets":
            return final_path.parent.parent.parent
        return final_path.parent

    @staticmethod
    def _infer_artifact_repository(*services: Any) -> ArtifactRepository | None:
        for service in services:
            if service is not None and hasattr(service, "artifact_repository"):
                return service.artifact_repository
        return None

    @staticmethod
    def _infer_dataset_repository(service: Any) -> DatasetRepository | None:
        if service is not None and hasattr(service, "dataset_repository"):
            return service.dataset_repository
        return None

    @staticmethod
    def _infer_model_repository(*services: Any) -> ModelRepository | None:
        for service in services:
            if service is not None and hasattr(service, "model_repository"):
                return service.model_repository
        return None
