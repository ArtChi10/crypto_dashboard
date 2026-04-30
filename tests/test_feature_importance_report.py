import tempfile
import unittest
from pathlib import Path

import pandas as pd

from mlcore.services import CatBoostTrainingResult, DatasetPreparationResult, FullPipelineService
from mlcore.services.report_service import FeatureImportanceReportService


class FeatureImportanceReportServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base_dir = Path(self.temp_dir.name)

    def test_build_creates_png_for_feature_importances(self):
        path = self.base_dir / "reports" / "feature_importance.png"

        result_path = FeatureImportanceReportService().build(
            feature_names=["feature_1", "feature_2", "feature_3"],
            importances=[0.2, 0.8, 0.4],
            path=path,
        )

        self.assertEqual(result_path, path)
        self.assert_png(path)

    def test_build_limits_to_top_n_features(self):
        path = self.base_dir / "feature_importance_top2.png"

        result_path = FeatureImportanceReportService().build(
            feature_names=["feature_1", "feature_2", "feature_3"],
            importances=[0.2, 0.8, 0.4],
            path=path,
            top_n=2,
        )

        self.assertEqual(result_path, path)
        self.assert_png(path)

    def test_build_raises_for_empty_importances(self):
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            FeatureImportanceReportService().build([], [], self.base_dir / "empty.png")

    def test_build_raises_for_mismatched_lengths(self):
        with self.assertRaisesRegex(ValueError, "same length"):
            FeatureImportanceReportService().build(
                ["feature_1", "feature_2"],
                [0.5],
                self.base_dir / "mismatch.png",
            )

    def test_full_pipeline_returns_feature_importance_report_when_catboost_runs(self):
        final_path = self.base_dir / "datasets" / "final" / "final.parquet"
        final_df = self._final_frame()
        service = FullPipelineService(
            dataset_preparation_service=RecordingDatasetPreparationService(final_path),
            dataset_repository=RecordingDatasetRepository(final_df),
            baseline_training_service=RecordingTrainingService(result=None),
            catboost_training_service=RecordingTrainingService(
                result=CatBoostTrainingResult(
                    model_path=self.base_dir / "models" / "catboost.cbm",
                    metrics=self._metrics(),
                    feature_columns=["feature_1", "feature_2"],
                    train_rows=8,
                    valid_rows=2,
                    test_rows=2,
                    feature_importances={"feature_1": 0.25, "feature_2": 0.75},
                )
            ),
        )

        result = service.run(
            raw_df=final_df,
            run_id=32,
            train_baseline=False,
            train_catboost=True,
        )

        self.assertIsNotNone(result.feature_importance_report_path)
        self.assertIn("feature_importance", result.feature_importance_report_path.name)
        self.assert_png(result.feature_importance_report_path)

    def test_full_pipeline_skips_feature_importance_report_when_catboost_is_disabled(self):
        final_path = self.base_dir / "datasets" / "final" / "final.parquet"
        final_df = self._final_frame()
        service = FullPipelineService(
            dataset_preparation_service=RecordingDatasetPreparationService(final_path),
            dataset_repository=RecordingDatasetRepository(final_df),
            baseline_training_service=RecordingTrainingService(
                result=CatBoostTrainingResult(
                    model_path=self.base_dir / "models" / "baseline.joblib",
                    metrics=self._metrics(),
                    feature_columns=["feature_1"],
                    train_rows=8,
                    valid_rows=2,
                    test_rows=2,
                )
            ),
            catboost_training_service=RecordingTrainingService(result=None),
        )

        result = service.run(
            raw_df=final_df,
            run_id=33,
            train_baseline=True,
            train_catboost=False,
        )

        self.assertIsNone(result.feature_importance_report_path)

    @staticmethod
    def _final_frame():
        return pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=12, freq="h"),
                "feature_1": range(12),
                "feature_2": [index % 3 for index in range(12)],
                "target": [0, 1] * 6,
            }
        )

    @staticmethod
    def _metrics():
        return {
            "accuracy": 0.8,
            "precision": 0.75,
            "recall": 0.7,
            "f1": 0.72,
            "roc_auc": 0.9,
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
            feature_columns=["feature_1", "feature_2"],
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
