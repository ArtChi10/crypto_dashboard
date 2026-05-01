from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.conf import settings


@dataclass(frozen=True)
class RunPersistenceResult:
    processed_dataset_artifact: Any
    final_dataset_artifact: Any
    baseline_model_artifact: Any | None
    baseline_metric_snapshot: Any | None
    catboost_model_artifact: Any | None
    catboost_metric_snapshot: Any | None
    dummy_model_artifact: Any | None = None
    dummy_metric_snapshot: Any | None = None
    target_distribution_report_artifact: Any | None = None
    metrics_comparison_report_artifact: Any | None = None
    feature_importance_report_artifact: Any | None = None
    stability_table_report_artifact: Any | None = None
    stability_plot_report_artifact: Any | None = None


class RunPersistenceService:
    DUMMY_MODEL_TYPE = "dummy"
    STABILITY_TABLE_REPORT_TYPE = "stability_table"
    STABILITY_PLOT_REPORT_TYPE = "stability_plot"

    def save_full_pipeline_result(self, run: Any, result: Any) -> RunPersistenceResult:
        from django.db import transaction

        from runs.models import DatasetArtifact, MetricSnapshot, ModelArtifact, ReportArtifact

        with transaction.atomic():
            processed_dataset_artifact = DatasetArtifact.objects.create(
                run=run,
                artifact_type=DatasetArtifact.ArtifactType.PROCESSED,
                file_path=self._metadata_path(result.preparation_result.processed_path),
                row_count=result.preparation_result.processed_rows,
            )
            final_dataset_artifact = DatasetArtifact.objects.create(
                run=run,
                artifact_type=DatasetArtifact.ArtifactType.FINAL,
                file_path=self._metadata_path(result.preparation_result.final_path),
                row_count=result.preparation_result.final_rows,
            )
            dummy_model_artifact = None
            dummy_metric_snapshot = None
            dummy_result = getattr(result, "dummy_result", None)
            if dummy_result is not None:
                dummy_model_artifact = self._create_model_artifact(
                    ModelArtifact,
                    run,
                    model_type=self.DUMMY_MODEL_TYPE,
                    model_result=dummy_result,
                )
                dummy_metric_snapshot = self._create_metric_snapshot(
                    MetricSnapshot,
                    run,
                    model_type=self.DUMMY_MODEL_TYPE,
                    metrics=dummy_result.metrics,
                )

            baseline_model_artifact = None
            baseline_metric_snapshot = None
            if result.baseline_result is not None:
                baseline_model_artifact = self._create_model_artifact(
                    ModelArtifact,
                    run,
                    model_type=ModelArtifact.ModelType.BASELINE,
                    model_result=result.baseline_result,
                )
                baseline_metric_snapshot = self._create_metric_snapshot(
                    MetricSnapshot,
                    run,
                    model_type=ModelArtifact.ModelType.BASELINE,
                    metrics=result.baseline_result.metrics,
                )

            catboost_model_artifact = None
            catboost_metric_snapshot = None
            if result.catboost_result is not None:
                catboost_model_artifact = self._create_model_artifact(
                    ModelArtifact,
                    run,
                    model_type=ModelArtifact.ModelType.CATBOOST,
                    model_result=result.catboost_result,
                )
                catboost_metric_snapshot = self._create_metric_snapshot(
                    MetricSnapshot,
                    run,
                    model_type=ModelArtifact.ModelType.CATBOOST,
                    metrics=result.catboost_result.metrics,
                )

            target_distribution_report_artifact = None
            target_distribution_report_path = getattr(
                result,
                "target_distribution_report_path",
                None,
            )
            if target_distribution_report_path is not None:
                target_distribution_report_artifact = ReportArtifact.objects.create(
                    run=run,
                    report_type=ReportArtifact.ReportType.TARGET_DISTRIBUTION,
                    file_path=self._metadata_path(target_distribution_report_path),
                )

            metrics_comparison_report_artifact = None
            metrics_comparison_report_path = getattr(
                result,
                "metrics_comparison_report_path",
                None,
            )
            if metrics_comparison_report_path is not None:
                metrics_comparison_report_artifact = ReportArtifact.objects.create(
                    run=run,
                    report_type=ReportArtifact.ReportType.METRICS_PLOT,
                    file_path=self._metadata_path(metrics_comparison_report_path),
                )

            stability_table_report_artifact = None
            stability_table_report_path = getattr(
                result,
                "stability_table_report_path",
                None,
            )
            if stability_table_report_path is not None:
                stability_table_report_artifact = ReportArtifact.objects.create(
                    run=run,
                    report_type=self.STABILITY_TABLE_REPORT_TYPE,
                    file_path=self._metadata_path(stability_table_report_path),
                )

            stability_plot_report_artifact = None
            stability_plot_report_path = getattr(
                result,
                "stability_plot_report_path",
                None,
            )
            if stability_plot_report_path is not None:
                stability_plot_report_artifact = ReportArtifact.objects.create(
                    run=run,
                    report_type=self.STABILITY_PLOT_REPORT_TYPE,
                    file_path=self._metadata_path(stability_plot_report_path),
                )

            feature_importance_report_artifact = None
            feature_importance_report_path = getattr(
                result,
                "feature_importance_report_path",
                None,
            )
            if feature_importance_report_path is not None:
                feature_importance_report_artifact = ReportArtifact.objects.create(
                    run=run,
                    report_type=ReportArtifact.ReportType.FEATURE_IMPORTANCE,
                    file_path=self._metadata_path(feature_importance_report_path),
                )

        return RunPersistenceResult(
            processed_dataset_artifact=processed_dataset_artifact,
            final_dataset_artifact=final_dataset_artifact,
            dummy_model_artifact=dummy_model_artifact,
            dummy_metric_snapshot=dummy_metric_snapshot,
            baseline_model_artifact=baseline_model_artifact,
            baseline_metric_snapshot=baseline_metric_snapshot,
            catboost_model_artifact=catboost_model_artifact,
            catboost_metric_snapshot=catboost_metric_snapshot,
            target_distribution_report_artifact=target_distribution_report_artifact,
            metrics_comparison_report_artifact=metrics_comparison_report_artifact,
            feature_importance_report_artifact=feature_importance_report_artifact,
            stability_table_report_artifact=stability_table_report_artifact,
            stability_plot_report_artifact=stability_plot_report_artifact,
        )

    @classmethod
    def _create_model_artifact(
        cls,
        model_artifact_model: Any,
        run: Any,
        model_type: str,
        model_result: Any,
    ) -> Any:
        return model_artifact_model.objects.create(
            run=run,
            model_type=model_type,
            file_path=cls._metadata_path(model_result.model_path),
            params_json={
                "feature_columns": model_result.feature_columns,
                "train_rows": model_result.train_rows,
                "valid_rows": model_result.valid_rows,
                "test_rows": model_result.test_rows,
            },
        )

    @staticmethod
    def _create_metric_snapshot(
        metric_snapshot_model: Any,
        run: Any,
        model_type: str,
        metrics: dict[str, Any],
    ) -> Any:
        return metric_snapshot_model.objects.create(
            run=run,
            model_type=model_type,
            accuracy=metrics.get("accuracy"),
            precision=metrics.get("precision"),
            recall=metrics.get("recall"),
            f1=metrics.get("f1"),
            roc_auc=metrics.get("roc_auc"),
            confusion_matrix_json=metrics.get("confusion_matrix"),
        )

    @staticmethod
    def _metadata_path(path: str | Path) -> str:
        path = Path(path)
        media_root = Path(settings.MEDIA_ROOT).resolve()

        try:
            return path.resolve().relative_to(media_root).as_posix()
        except ValueError:
            return path.as_posix()
