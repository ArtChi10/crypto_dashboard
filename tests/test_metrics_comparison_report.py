import tempfile
import unittest
from pathlib import Path

import pandas as pd

from mlcore.services import (
    BaselineTrainingResult,
    CatBoostTrainingResult,
    DatasetPreparationResult,
    FullPipelineService,
)
from mlcore.services.report_service import MetricsComparisonReportService


class MetricsComparisonReportServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base_dir = Path(self.temp_dir.name)

    def test_build_creates_png_for_two_models(self):
        path = self.base_dir / "reports" / "metrics_plot.png"

        result_path = MetricsComparisonReportService().build(
            {
                "baseline": self._metrics(accuracy=0.71, roc_auc=0.78),
                "catboost": self._metrics(accuracy=0.82, roc_auc=0.91),
            },
            path,
        )

        self.assertEqual(result_path, path)
        self.assert_png(path)

    def test_build_creates_png_for_baseline_only(self):
        path = self.base_dir / "baseline_metrics.png"

        MetricsComparisonReportService().build(
            {"baseline": self._metrics()},
            path,
        )

        self.assert_png(path)

    def test_build_creates_png_for_catboost_only(self):
        path = self.base_dir / "catboost_metrics.png"

        MetricsComparisonReportService().build(
            {"catboost": self._metrics()},
            path,
        )

        self.assert_png(path)

    def test_build_handles_missing_roc_auc_without_failing(self):
        path = self.base_dir / "metrics_without_auc.png"

        MetricsComparisonReportService().build(
            {
                "baseline": self._metrics(roc_auc=None),
                "catboost": self._metrics(roc_auc=0.8),
            },
            path,
        )

        self.assert_png(path)

    def test_build_raises_when_no_model_metrics_are_present(self):
        with self.assertRaisesRegex(ValueError, "at least one model"):
            MetricsComparisonReportService().build({}, self.base_dir / "metrics.png")

    def test_full_pipeline_returns_metrics_comparison_report_for_baseline_only(self):
        final_path = self.base_dir / "datasets" / "final" / "final.parquet"
        final_df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=12, freq="h"),
                "feature_1": range(12),
                "target": [0, 1] * 6,
            }
        )
        service = FullPipelineService(
            dataset_preparation_service=RecordingDatasetPreparationService(final_path),
            dataset_repository=RecordingDatasetRepository(final_df),
            baseline_training_service=RecordingTrainingService(
                BaselineTrainingResult(
                    model_path=self.base_dir / "models" / "baseline.joblib",
                    metrics=self._metrics(roc_auc=None),
                    feature_columns=["feature_1"],
                    train_rows=8,
                    valid_rows=2,
                    test_rows=2,
                )
            ),
            catboost_training_service=RecordingTrainingService(
                CatBoostTrainingResult(
                    model_path=self.base_dir / "models" / "catboost.cbm",
                    metrics=self._metrics(),
                    feature_columns=["feature_1"],
                    train_rows=8,
                    valid_rows=2,
                    test_rows=2,
                )
            ),
        )

        result = service.run(
            raw_df=final_df,
            run_id=31,
            train_baseline=True,
            train_catboost=False,
        )

        self.assertIsNotNone(result.metrics_comparison_report_path)
        self.assertIn("metrics_plot", result.metrics_comparison_report_path.name)
        self.assert_png(result.metrics_comparison_report_path)

    @staticmethod
    def _metrics(accuracy=0.8, roc_auc=0.9):
        return {
            "accuracy": accuracy,
            "precision": 0.75,
            "recall": 0.7,
            "f1": 0.72,
            "roc_auc": roc_auc,
            "confusion_matrix": [[3, 1], [2, 4]],
        }

    def assert_png(self, path):
        self.assertTrue(path.is_file())
        self.assertGreater(path.stat().st_size, 0)
        self.assertEqual(path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")


class RecordingDatasetPreparationService:
    def __init__(self, final_path):
        self.final_path = final_path

    def prepare(self, raw_df, run_id, horizon=3, symbol=None):
        return DatasetPreparationResult(
            processed_path=self.final_path.with_name("processed.parquet"),
            final_path=self.final_path,
            raw_rows=len(raw_df),
            processed_rows=len(raw_df),
            final_rows=len(raw_df),
            feature_columns=["feature_1"],
            target_column="target",
        )


class RecordingDatasetRepository:
    def __init__(self, final_df):
        self.final_df = final_df

    def load(self, path):
        return self.final_df


class RecordingTrainingService:
    def __init__(self, result):
        self.result = result

    def train_and_evaluate(self, df, run_id):
        return self.result


if __name__ == "__main__":
    unittest.main()
