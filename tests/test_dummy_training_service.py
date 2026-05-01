import tempfile
import unittest
from pathlib import Path

import pandas as pd

from mlcore.repositories import ArtifactRepository, ModelRepository
from mlcore.services.dummy_training_service import DummyTrainingService


class DummyTrainingServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base_dir = Path(self.temp_dir.name)

    def test_train_and_evaluate_saves_dummy_model_and_returns_metrics(self):
        service = DummyTrainingService(
            artifact_repository=ArtifactRepository(self.base_dir),
            model_repository=ModelRepository(),
        )

        result = service.train_and_evaluate(self._make_final_df(), run_id=12)

        self.assertTrue(result.model_path.is_file())
        self.assertEqual(result.model_path.suffix, ".joblib")
        self.assertIn("model_dummy_run_12_", result.model_path.name)
        self.assertEqual(result.feature_columns, ["feature_1", "feature_2"])
        self.assertEqual((result.train_rows, result.valid_rows, result.test_rows), (8, 1, 3))
        self.assertEqual(
            set(result.metrics),
            {"accuracy", "precision", "recall", "f1", "roc_auc", "confusion_matrix"},
        )
        self.assertEqual(
            set(result.test_predictions),
            {"timestamp", "y_true", "y_pred", "y_proba"},
        )
        self.assertEqual(len(result.test_predictions), result.test_rows)

    def test_train_and_evaluate_allows_one_class_train_split(self):
        service = DummyTrainingService(
            artifact_repository=ArtifactRepository(self.base_dir),
            model_repository=ModelRepository(),
        )
        df = self._make_final_df(target=[0] * 9 + [1, 1, 1])

        result = service.train_and_evaluate(df, run_id=13)

        self.assertTrue(result.model_path.is_file())
        self.assertEqual(result.metrics["roc_auc"], None)
        self.assertNotIn("y_proba", result.test_predictions)

    def test_missing_target_raises_value_error(self):
        service = DummyTrainingService()
        df = pd.DataFrame({"timestamp": pd.date_range("2024-01-01", periods=3, freq="h")})

        with self.assertRaisesRegex(ValueError, "Missing required columns: target"):
            service.train_and_evaluate(df, run_id=1)

    @staticmethod
    def _make_final_df(target=None):
        if target is None:
            target = [0, 1] * 6
        return pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=12, freq="h"),
                "symbol": ["BTCUSDT"] * 12,
                "feature_1": range(12),
                "feature_2": [value % 3 for value in range(12)],
                "target": target,
            }
        )


if __name__ == "__main__":
    unittest.main()
