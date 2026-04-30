from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
from mlcore.services.report_service import TargetDistributionReportService


@dataclass(frozen=True)
class FullPipelineResult:
    preparation_result: DatasetPreparationResult
    baseline_result: BaselineTrainingResult | None
    catboost_result: CatBoostTrainingResult | None
    target_distribution_report_path: Path | None = None


class FullPipelineService:
    def __init__(
        self,
        dataset_preparation_service: DatasetPreparationService | None = None,
        baseline_training_service: BaselineTrainingService | None = None,
        catboost_training_service: CatBoostTrainingService | None = None,
        dataset_repository: DatasetRepository | None = None,
        target_distribution_report_service: TargetDistributionReportService | None = None,
    ) -> None:
        self.artifact_repository = self._infer_artifact_repository(
            dataset_preparation_service,
            baseline_training_service,
            catboost_training_service,
        )
        model_repository = self._infer_model_repository(
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

    def run(
        self,
        raw_df: Any,
        run_id: int,
        horizon: int = 3,
        symbol: str | None = None,
        train_baseline: bool = True,
        train_catboost: bool = True,
    ) -> FullPipelineResult:
        if not train_baseline and not train_catboost:
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

        return FullPipelineResult(
            preparation_result=preparation_result,
            baseline_result=baseline_result,
            catboost_result=catboost_result,
            target_distribution_report_path=target_distribution_report_path,
        )

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
