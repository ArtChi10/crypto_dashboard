import tempfile
import unittest
from pathlib import Path

import pandas as pd

from mlcore.repositories import ArtifactRepository
from mlcore.services import (
    BaselineTrainingResult,
    CatBoostTrainingResult,
    CatBoostTrainingService,
    DatasetPreparationResult,
    FullPipelineService,
)
from mlcore.training import CatBoostTrainer


class FullPipelineServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base_dir = Path(self.temp_dir.name)

    def test_run_prepares_dataset_and_trains_both_models(self):
        artifact_repository = ArtifactRepository(self.base_dir)
        service = FullPipelineService(
            catboost_training_service=CatBoostTrainingService(
                artifact_repository=artifact_repository,
                trainer=CatBoostTrainer(iterations=5, verbose=False),
            )
        )

        result = service.run(self._make_raw_frame(), run_id=7, horizon=3, symbol="BTCUSDT")

        self.assertTrue(result.preparation_result.processed_path.is_file())
        self.assertTrue(result.preparation_result.final_path.is_file())
        self.assertIsNotNone(result.baseline_result)
        self.assertIsNotNone(result.catboost_result)
        self.assertTrue(result.baseline_result.model_path.is_file())
        self.assertTrue(result.catboost_result.model_path.is_file())
        self.assertEqual(result.baseline_result.model_path.suffix, ".joblib")
        self.assertEqual(result.catboost_result.model_path.suffix, ".cbm")
        self.assertEqual(
            set(result.baseline_result.metrics),
            {"accuracy", "precision", "recall", "f1", "roc_auc", "confusion_matrix"},
        )
        self.assertEqual(
            set(result.catboost_result.metrics),
            {"accuracy", "precision", "recall", "f1", "roc_auc", "confusion_matrix"},
        )

    def test_run_can_disable_baseline(self):
        service = self._make_service()

        result = service.run(
            self._make_raw_frame(),
            run_id=1,
            horizon=3,
            symbol="BTCUSDT",
            train_baseline=False,
            train_catboost=True,
        )

        self.assertIsNone(result.baseline_result)
        self.assertIsNotNone(result.catboost_result)

    def test_run_can_disable_catboost(self):
        service = self._make_service()

        result = service.run(
            self._make_raw_frame(),
            run_id=1,
            horizon=3,
            symbol="BTCUSDT",
            train_baseline=True,
            train_catboost=False,
        )

        self.assertIsNotNone(result.baseline_result)
        self.assertIsNone(result.catboost_result)

    def test_run_raises_when_all_training_is_disabled(self):
        preparation_service = RecordingDatasetPreparationService(self.base_dir / "final.parquet")
        service = FullPipelineService(dataset_preparation_service=preparation_service)

        with self.assertRaisesRegex(ValueError, "At least one training flag"):
            service.run(
                self._make_raw_frame(),
                run_id=1,
                train_baseline=False,
                train_catboost=False,
            )

        self.assertFalse(preparation_service.called)

    def test_run_loads_final_dataset_before_training(self):
        final_path = self.base_dir / "final.parquet"
        final_df = pd.DataFrame({"feature_1": [1, 2], "target": [0, 1]})
        preparation_service = RecordingDatasetPreparationService(final_path)
        dataset_repository = RecordingDatasetRepository(final_df)
        baseline_service = RecordingTrainingService(
            BaselineTrainingResult(
                model_path=self.base_dir / "baseline.joblib",
                metrics={"accuracy": 1.0},
                feature_columns=["feature_1"],
                train_rows=1,
                valid_rows=0,
                test_rows=1,
            )
        )
        catboost_service = RecordingTrainingService(
            CatBoostTrainingResult(
                model_path=self.base_dir / "catboost.cbm",
                metrics={"accuracy": 1.0},
                feature_columns=["feature_1"],
                train_rows=1,
                valid_rows=0,
                test_rows=1,
            )
        )
        service = FullPipelineService(
            dataset_preparation_service=preparation_service,
            baseline_training_service=baseline_service,
            catboost_training_service=catboost_service,
            dataset_repository=dataset_repository,
        )

        result = service.run(self._make_raw_frame(), run_id=9, horizon=3, symbol="BTCUSDT")

        self.assertEqual(dataset_repository.loaded_path, final_path)
        self.assertIs(baseline_service.seen_df, final_df)
        self.assertIs(catboost_service.seen_df, final_df)
        self.assertIs(result.baseline_result, baseline_service.result)
        self.assertIs(result.catboost_result, catboost_service.result)

    def _make_service(self):
        artifact_repository = ArtifactRepository(self.base_dir)
        return FullPipelineService(
            catboost_training_service=CatBoostTrainingService(
                artifact_repository=artifact_repository,
                trainer=CatBoostTrainer(iterations=5, verbose=False),
            )
        )

    @staticmethod
    def _make_raw_frame(row_count: int = 90) -> pd.DataFrame:
        close_pattern = [1, 3, 2, 4]
        close_values = [close_pattern[index % len(close_pattern)] for index in range(row_count)]
        return pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=row_count, freq="h"),
                "open": close_values,
                "high": [value + 1 for value in close_values],
                "low": [value - 1 for value in close_values],
                "close": close_values,
                "volume": range(100, 100 + row_count),
                "symbol": ["BTCUSDT"] * row_count,
            }
        )


class RecordingDatasetPreparationService:
    def __init__(self, final_path):
        self.final_path = final_path
        self.called = False

    def prepare(self, raw_df, run_id, horizon=3, symbol=None):
        self.called = True
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
        self.loaded_path = None

    def load(self, path):
        self.loaded_path = path
        return self.final_df


class RecordingTrainingService:
    def __init__(self, result):
        self.result = result
        self.seen_df = None
        self.seen_run_id = None

    def train_and_evaluate(self, df, run_id):
        self.seen_df = df
        self.seen_run_id = run_id
        return self.result


if __name__ == "__main__":
    unittest.main()
