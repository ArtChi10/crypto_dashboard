import tempfile
import unittest
from pathlib import Path

import pandas as pd

from mlcore.repositories import ArtifactRepository, ModelRepository
from mlcore.services import CatBoostTrainingService
from mlcore.training import CatBoostTrainer


class CatBoostTrainingServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base_dir = Path(self.temp_dir.name)

    def test_train_and_evaluate_returns_result_and_saves_cbm_model(self):
        df = self._make_frame()
        service = CatBoostTrainingService(
            artifact_repository=ArtifactRepository(self.base_dir),
            trainer=CatBoostTrainer(iterations=5, verbose=False),
        )

        result = service.train_and_evaluate(df, run_id=7)

        self.assertTrue(result.model_path.is_file())
        self.assertEqual(result.model_path.parent, self.base_dir / "models")
        self.assertEqual(result.model_path.suffix, ".cbm")
        self.assertTrue(result.model_path.name.startswith("model_catboost_run_7_"))
        self.assertEqual(result.feature_columns, ["feature_1", "feature_2"])
        self.assertEqual((result.train_rows, result.valid_rows, result.test_rows), (56, 12, 12))
        self.assertEqual(
            set(result.metrics),
            {"accuracy", "precision", "recall", "f1", "roc_auc", "confusion_matrix"},
        )
        self.assertEqual(set(result.feature_importances), {"feature_1", "feature_2"})

        loaded = ModelRepository().load(result.model_path)
        self.assertEqual(len(loaded.predict(df[result.feature_columns])), len(df))

    def test_train_and_evaluate_passes_valid_set_and_evaluates_test_set(self):
        trainer = RecordingTrainer()
        evaluator = RecordingEvaluator()
        model_repository = RecordingModelRepository()
        artifact_repository = FixedArtifactRepository(self.base_dir / "models" / "model.cbm")
        service = CatBoostTrainingService(
            trainer=trainer,
            evaluator=evaluator,
            artifact_repository=artifact_repository,
            model_repository=model_repository,
        )

        result = service.train_and_evaluate(self._make_frame(), run_id=3)

        self.assertEqual(trainer.feature_columns, ["feature_1", "feature_2"])
        self.assertEqual((trainer.train_rows, trainer.valid_rows), (56, 12))
        self.assertEqual(evaluator.test_rows, 12)
        self.assertEqual(model_repository.saved_model, trainer.model)
        self.assertEqual(model_repository.saved_path, artifact_repository.path)
        self.assertEqual(result.metrics, {"accuracy": 1.0})
        self.assertEqual(result.feature_importances, {"feature_1": 0.6, "feature_2": 0.4})

    def test_train_and_evaluate_raises_for_missing_target(self):
        service = CatBoostTrainingService(
            artifact_repository=ArtifactRepository(self.base_dir),
            trainer=CatBoostTrainer(iterations=5, verbose=False),
        )
        df = self._make_frame().drop(columns=["target"])

        with self.assertRaisesRegex(ValueError, "Missing required columns: target"):
            service.train_and_evaluate(df, run_id=1)

    def test_train_and_evaluate_raises_without_numeric_features(self):
        service = CatBoostTrainingService(
            artifact_repository=ArtifactRepository(self.base_dir),
            trainer=CatBoostTrainer(iterations=5, verbose=False),
        )
        df = self._make_frame()[["timestamp", "symbol", "target", "note"]]

        with self.assertRaisesRegex(ValueError, "numeric feature"):
            service.train_and_evaluate(df, run_id=1)

    @staticmethod
    def _make_frame(row_count: int = 80) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=row_count, freq="h"),
                "symbol": ["BTCUSDT"] * row_count,
                "feature_1": range(row_count),
                "feature_2": [index % 5 for index in range(row_count)],
                "target": [index % 2 for index in range(row_count)],
                "note": ["ignore"] * row_count,
            }
        )


class RecordingTrainer:
    def __init__(self):
        self.feature_columns = None
        self.train_rows = None
        self.valid_rows = None
        self.model = RecordingModel()

    def get_feature_columns(self, df):
        self.feature_columns = ["feature_1", "feature_2"]
        return self.feature_columns

    def train(self, x_train, y_train, x_valid=None, y_valid=None):
        self.train_rows = len(x_train)
        self.valid_rows = len(x_valid)
        self.y_train_rows = len(y_train)
        self.y_valid_rows = len(y_valid)
        return self.model


class RecordingModel:
    def get_feature_importance(self):
        return [0.6, 0.4]


class RecordingEvaluator:
    def __init__(self):
        self.test_rows = None

    def evaluate_model(self, model, x_test, y_test):
        self.test_rows = len(x_test)
        self.y_test_rows = len(y_test)
        return {"accuracy": 1.0}


class RecordingModelRepository:
    def __init__(self):
        self.saved_model = None
        self.saved_path = None

    def save(self, model, path):
        self.saved_model = model
        self.saved_path = path


class FixedArtifactRepository:
    def __init__(self, path):
        self.path = path

    def model_path(self, model_type, run_id, extension="cbm"):
        return self.path


if __name__ == "__main__":
    unittest.main()
