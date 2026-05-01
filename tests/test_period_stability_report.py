import tempfile
import unittest
from pathlib import Path

import pandas as pd

from mlcore.services import BaselineTrainingResult, DatasetPreparationResult, FullPipelineService
from mlcore.services.report_service import PeriodStabilityReportService


class PeriodStabilityReportServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base_dir = Path(self.temp_dir.name)

    def test_build_creates_csv_and_png_for_multiple_models(self):
        csv_path = self.base_dir / "reports" / "stability_table.csv"
        png_path = self.base_dir / "reports" / "stability_plot.png"

        result = PeriodStabilityReportService().build(
            {
                "dummy": self._predictions(),
                "baseline": self._predictions(),
            },
            csv_path,
            png_path,
        )

        self.assertEqual(result.table_path, csv_path)
        self.assertEqual(result.plot_path, png_path)
        self.assertTrue(csv_path.is_file())
        self.assert_png(png_path)

        report_df = pd.read_csv(csv_path)
        self.assertEqual(set(report_df["model_type"]), {"dummy", "baseline"})
        self.assertEqual(report_df["rows"].tolist(), [24, 24, 24, 24])
        self.assertIn("accuracy", report_df.columns)
        self.assertIn("f1", report_df.columns)
        self.assertIn("roc_auc", report_df.columns)

    def test_build_creates_csv_without_png_when_plot_path_is_missing(self):
        csv_path = self.base_dir / "stability_table.csv"

        result = PeriodStabilityReportService().build(
            {"baseline": self._predictions(row_count=24)},
            csv_path,
        )

        self.assertEqual(result.table_path, csv_path)
        self.assertIsNone(result.plot_path)
        self.assertTrue(csv_path.is_file())

    def test_build_raises_without_predictions(self):
        with self.assertRaisesRegex(ValueError, "at least one model"):
            PeriodStabilityReportService().build({}, self.base_dir / "stability.csv")

    def test_full_pipeline_returns_stability_report_paths(self):
        final_path = self.base_dir / "datasets" / "final" / "final.parquet"
        final_df = self._predictions(row_count=24).rename(
            columns={"y_true": "target", "y_pred": "feature_1"}
        )
        final_df["feature_2"] = range(len(final_df))
        baseline_result = BaselineTrainingResult(
            model_path=self.base_dir / "models" / "baseline.joblib",
            metrics=self._metrics(),
            feature_columns=["feature_1"],
            train_rows=16,
            valid_rows=4,
            test_rows=4,
            test_predictions=self._predictions(row_count=24),
        )
        service = FullPipelineService(
            dataset_preparation_service=RecordingDatasetPreparationService(final_path),
            dataset_repository=RecordingDatasetRepository(final_df),
            dummy_training_service=RecordingTrainingService(result=None),
            baseline_training_service=RecordingTrainingService(result=baseline_result),
            catboost_training_service=RecordingTrainingService(result=None),
        )

        result = service.run(
            raw_df=final_df,
            run_id=41,
            train_dummy=False,
            train_baseline=True,
            train_catboost=False,
        )

        self.assertIsNotNone(result.stability_table_report_path)
        self.assertIsNotNone(result.stability_plot_report_path)
        self.assertTrue(result.stability_table_report_path.is_file())
        self.assert_png(result.stability_plot_report_path)

    @staticmethod
    def _predictions(row_count=48):
        pattern_count = row_count // 4
        return pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=row_count, freq="h"),
                "y_true": [0, 1, 0, 1] * pattern_count,
                "y_pred": [0, 1, 1, 1] * pattern_count,
                "y_proba": [0.1, 0.8, 0.6, 0.7] * pattern_count,
            }
        )

    @staticmethod
    def _metrics():
        return {
            "accuracy": 0.75,
            "precision": 2 / 3,
            "recall": 1.0,
            "f1": 0.8,
            "roc_auc": 1.0,
            "confusion_matrix": [[6, 6], [0, 12]],
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
