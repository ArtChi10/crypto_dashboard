import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.conf import settings

django.setup()

from mlcore.services import (  # noqa: E402
    BaselineTrainingResult,
    CatBoostTrainingResult,
    DatasetPreparationResult,
    FullPipelineResult,
    RunPersistenceService,
)
from mlcore.services.dummy_training_service import DummyTrainingResult  # noqa: E402
from runs.models import (  # noqa: E402
    DatasetArtifact,
    MetricSnapshot,
    ModelArtifact,
    PipelineRun,
    ReportArtifact,
)

DEFAULT_RESULT = object()


class RunPersistenceServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = RunPersistenceService()
        self.run_ids = []

    def tearDown(self):
        PipelineRun.objects.filter(id__in=self.run_ids).delete()

    def test_save_full_pipeline_result_creates_all_metadata_records(self):
        run = self._create_run()
        result = self._make_result()

        saved = self.service.save_full_pipeline_result(run, result)

        self.assertEqual(DatasetArtifact.objects.filter(run=run).count(), 2)
        self.assertEqual(ModelArtifact.objects.filter(run=run).count(), 3)
        self.assertEqual(MetricSnapshot.objects.filter(run=run).count(), 3)
        self.assertEqual(ReportArtifact.objects.filter(run=run).count(), 3)

        processed_artifact = DatasetArtifact.objects.get(
            run=run,
            artifact_type=DatasetArtifact.ArtifactType.PROCESSED,
        )
        final_artifact = DatasetArtifact.objects.get(
            run=run,
            artifact_type=DatasetArtifact.ArtifactType.FINAL,
        )
        self.assertEqual(processed_artifact.file_path, "datasets/processed/processed.parquet")
        self.assertEqual(processed_artifact.row_count, 80)
        self.assertEqual(final_artifact.file_path, "datasets/final/final.parquet")
        self.assertEqual(final_artifact.row_count, 60)

        dummy_model = ModelArtifact.objects.get(
            run=run,
            model_type="dummy",
        )
        self.assertEqual(dummy_model.file_path, "models/dummy.joblib")
        self.assertEqual(dummy_model.params_json["feature_columns"], ["feature_1", "feature_2"])
        self.assertEqual(dummy_model.params_json["train_rows"], 42)

        dummy_metrics = MetricSnapshot.objects.get(
            run=run,
            model_type="dummy",
        )
        self.assertEqual(dummy_metrics.accuracy, 0.7)
        self.assertEqual(dummy_metrics.precision, 0.0)
        self.assertEqual(dummy_metrics.recall, 0.0)
        self.assertEqual(dummy_metrics.f1, 0.0)
        self.assertEqual(dummy_metrics.roc_auc, 0.5)
        self.assertEqual(dummy_metrics.confusion_matrix_json, [[4, 0], [2, 0]])

        baseline_model = ModelArtifact.objects.get(
            run=run,
            model_type=ModelArtifact.ModelType.BASELINE,
        )
        self.assertEqual(baseline_model.file_path, "models/baseline.joblib")
        self.assertEqual(baseline_model.params_json["feature_columns"], ["feature_1", "feature_2"])
        self.assertEqual(baseline_model.params_json["train_rows"], 42)

        baseline_metrics = MetricSnapshot.objects.get(
            run=run,
            model_type=ModelArtifact.ModelType.BASELINE,
        )
        self.assertEqual(baseline_metrics.accuracy, 0.8)
        self.assertEqual(baseline_metrics.precision, 0.75)
        self.assertEqual(baseline_metrics.recall, 0.6)
        self.assertEqual(baseline_metrics.f1, 0.6667)
        self.assertEqual(baseline_metrics.roc_auc, 0.82)
        self.assertEqual(baseline_metrics.confusion_matrix_json, [[4, 1], [2, 3]])

        report_artifact = ReportArtifact.objects.get(
            run=run,
            report_type=ReportArtifact.ReportType.TARGET_DISTRIBUTION,
        )
        self.assertEqual(report_artifact.file_path, "reports/target_distribution.png")
        metrics_report_artifact = ReportArtifact.objects.get(
            run=run,
            report_type=ReportArtifact.ReportType.METRICS_PLOT,
        )
        self.assertEqual(metrics_report_artifact.file_path, "reports/metrics_plot.png")
        feature_report_artifact = ReportArtifact.objects.get(
            run=run,
            report_type=ReportArtifact.ReportType.FEATURE_IMPORTANCE,
        )
        self.assertEqual(feature_report_artifact.file_path, "reports/feature_importance.png")

        self.assertEqual(saved.processed_dataset_artifact, processed_artifact)
        self.assertEqual(saved.final_dataset_artifact, final_artifact)
        self.assertEqual(saved.dummy_model_artifact, dummy_model)
        self.assertEqual(saved.dummy_metric_snapshot, dummy_metrics)
        self.assertEqual(saved.baseline_model_artifact, baseline_model)
        self.assertIsNotNone(saved.catboost_model_artifact)
        self.assertIsNotNone(saved.catboost_metric_snapshot)
        self.assertEqual(saved.target_distribution_report_artifact, report_artifact)
        self.assertEqual(saved.metrics_comparison_report_artifact, metrics_report_artifact)
        self.assertEqual(saved.feature_importance_report_artifact, feature_report_artifact)

    def test_save_full_pipeline_result_allows_missing_baseline_result(self):
        run = self._create_run()
        result = self._make_result(baseline_result=None)

        saved = self.service.save_full_pipeline_result(run, result)

        self.assertEqual(DatasetArtifact.objects.filter(run=run).count(), 2)
        self.assertEqual(ModelArtifact.objects.filter(run=run).count(), 2)
        self.assertEqual(MetricSnapshot.objects.filter(run=run).count(), 2)
        self.assertEqual(ReportArtifact.objects.filter(run=run).count(), 3)
        self.assertIsNone(saved.baseline_model_artifact)
        self.assertIsNone(saved.baseline_metric_snapshot)
        self.assertEqual(
            set(ModelArtifact.objects.filter(run=run).values_list("model_type", flat=True)),
            {"dummy", ModelArtifact.ModelType.CATBOOST},
        )

    def test_save_full_pipeline_result_allows_missing_catboost_result(self):
        run = self._create_run()
        result = self._make_result(catboost_result=None)

        saved = self.service.save_full_pipeline_result(run, result)

        self.assertEqual(DatasetArtifact.objects.filter(run=run).count(), 2)
        self.assertEqual(ModelArtifact.objects.filter(run=run).count(), 2)
        self.assertEqual(MetricSnapshot.objects.filter(run=run).count(), 2)
        self.assertEqual(ReportArtifact.objects.filter(run=run).count(), 2)
        self.assertIsNone(saved.catboost_model_artifact)
        self.assertIsNone(saved.catboost_metric_snapshot)
        self.assertEqual(
            set(ModelArtifact.objects.filter(run=run).values_list("model_type", flat=True)),
            {"dummy", ModelArtifact.ModelType.BASELINE},
        )

    def test_save_full_pipeline_result_uses_transaction_atomic(self):
        run = self._create_run()
        result = self._make_result()
        atomic = RecordingAtomic()

        with patch("django.db.transaction.atomic", atomic):
            self.service.save_full_pipeline_result(run, result)

        self.assertTrue(atomic.called)
        self.assertTrue(atomic.entered)
        self.assertTrue(atomic.exited)

    def test_metadata_path_keeps_relative_path_when_not_under_media_root(self):
        self.assertEqual(
            self.service._metadata_path(Path("tmp_artifacts/model.joblib")),
            "tmp_artifacts/model.joblib",
        )

    def test_metadata_path_makes_relative_media_path_media_root_relative(self):
        self.assertEqual(
            self.service._metadata_path(Path("media") / "reports" / "target_distribution.png"),
            "reports/target_distribution.png",
        )

    def _create_run(self):
        run = PipelineRun.objects.create(
            name="Persistence unit test",
            symbols_json=["BTCUSDT"],
            interval="1h",
            target_horizon=3,
        )
        self.run_ids.append(run.id)
        return run

    @staticmethod
    def _make_result(
        dummy_result=DEFAULT_RESULT,
        baseline_result=DEFAULT_RESULT,
        catboost_result=DEFAULT_RESULT,
    ) -> FullPipelineResult:
        if dummy_result is DEFAULT_RESULT:
            dummy_result = DummyTrainingResult(
                model_path=Path(settings.MEDIA_ROOT) / "models" / "dummy.joblib",
                metrics={
                    "accuracy": 0.7,
                    "precision": 0.0,
                    "recall": 0.0,
                    "f1": 0.0,
                    "roc_auc": 0.5,
                    "confusion_matrix": [[4, 0], [2, 0]],
                },
                feature_columns=["feature_1", "feature_2"],
                train_rows=42,
                valid_rows=9,
                test_rows=9,
            )
        if baseline_result is DEFAULT_RESULT:
            baseline_result = BaselineTrainingResult(
                model_path=Path(settings.MEDIA_ROOT) / "models" / "baseline.joblib",
                metrics={
                    "accuracy": 0.8,
                    "precision": 0.75,
                    "recall": 0.6,
                    "f1": 0.6667,
                    "roc_auc": 0.82,
                    "confusion_matrix": [[4, 1], [2, 3]],
                },
                feature_columns=["feature_1", "feature_2"],
                train_rows=42,
                valid_rows=9,
                test_rows=9,
            )
        if catboost_result is DEFAULT_RESULT:
            catboost_result = CatBoostTrainingResult(
                model_path=Path(settings.MEDIA_ROOT) / "models" / "catboost.cbm",
                metrics={
                    "accuracy": 0.85,
                    "precision": 0.8,
                    "recall": 0.7,
                    "f1": 0.7467,
                    "roc_auc": None,
                    "confusion_matrix": [[5, 1], [2, 4]],
                },
                feature_columns=["feature_1", "feature_2"],
                train_rows=42,
                valid_rows=9,
                test_rows=9,
            )

        return FullPipelineResult(
            preparation_result=DatasetPreparationResult(
                processed_path=Path(settings.MEDIA_ROOT)
                / "datasets"
                / "processed"
                / "processed.parquet",
                final_path=Path(settings.MEDIA_ROOT) / "datasets" / "final" / "final.parquet",
                raw_rows=100,
                processed_rows=80,
                final_rows=60,
                feature_columns=["feature_1", "feature_2"],
                target_column="target",
            ),
            baseline_result=baseline_result,
            catboost_result=catboost_result,
            dummy_result=dummy_result,
            target_distribution_report_path=Path(settings.MEDIA_ROOT)
            / "reports"
            / "target_distribution.png",
            metrics_comparison_report_path=Path(settings.MEDIA_ROOT)
            / "reports"
            / "metrics_plot.png",
            feature_importance_report_path=(
                Path(settings.MEDIA_ROOT) / "reports" / "feature_importance.png"
                if catboost_result is not None
                else None
            ),
        )


class RecordingAtomic:
    def __init__(self):
        self.called = False
        self.entered = False
        self.exited = False

    def __call__(self):
        self.called = True
        return self

    def __enter__(self):
        self.entered = True

    def __exit__(self, exc_type, exc_value, traceback):
        self.exited = True


if __name__ == "__main__":
    unittest.main()
