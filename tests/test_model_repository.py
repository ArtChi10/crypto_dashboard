import tempfile
import unittest
from pathlib import Path

import pandas as pd

from mlcore.repositories import ModelRepository
from mlcore.training import BaselineTrainer, CatBoostTrainer


class ModelRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base_dir = Path(self.temp_dir.name)
        self.repo = ModelRepository()

    def test_save_and_load_sklearn_pipeline_as_joblib(self):
        df = self._make_frame()
        model = BaselineTrainer().train(df[["feature_1", "feature_2"]], df["target"])
        path = self.base_dir / "nested" / "models" / "baseline.joblib"

        self.repo.save(model, path)
        loaded = self.repo.load(path)

        self.assertTrue(path.is_file())
        self.assertTrue(path.parent.is_dir())
        self.assertEqual(type(loaded).__name__, "Pipeline")
        self.assertEqual(len(loaded.predict(df[["feature_1", "feature_2"]])), len(df))

    def test_save_and_load_sklearn_pipeline_as_pkl(self):
        df = self._make_frame()
        model = BaselineTrainer().train(df[["feature_1", "feature_2"]], df["target"])
        path = self.base_dir / "models" / "baseline.pkl"

        self.repo.save(model, path)
        loaded = self.repo.load(path)

        self.assertTrue(path.is_file())
        self.assertEqual(type(loaded).__name__, "Pipeline")
        self.assertEqual(len(loaded.predict(df[["feature_1", "feature_2"]])), len(df))

    def test_save_and_load_catboost_classifier_as_cbm(self):
        df = self._make_frame(row_count=30)
        model = CatBoostTrainer(iterations=5, verbose=False).train(
            df[["feature_1", "feature_2"]],
            df["target"],
        )
        path = self.base_dir / "models" / "catboost.cbm"

        self.repo.save(model, path)
        loaded = self.repo.load(path)

        self.assertTrue(path.is_file())
        self.assertEqual(type(loaded).__name__, "CatBoostClassifier")
        self.assertEqual(len(loaded.predict(df[["feature_1", "feature_2"]])), len(df))

    def test_save_raises_for_unknown_extension(self):
        with self.assertRaisesRegex(ValueError, "Unsupported model file extension"):
            self.repo.save(object(), self.base_dir / "models" / "model.txt")

    def test_load_raises_for_unknown_extension(self):
        with self.assertRaisesRegex(ValueError, "Unsupported model file extension"):
            self.repo.load(self.base_dir / "models" / "model.txt")

    def test_save_cbm_raises_without_save_model(self):
        with self.assertRaisesRegex(ValueError, "save_model"):
            self.repo.save(object(), self.base_dir / "models" / "model.cbm")

    @staticmethod
    def _make_frame(row_count: int = 20) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "feature_1": range(row_count),
                "feature_2": [index % 3 for index in range(row_count)],
                "target": [index % 2 for index in range(row_count)],
            }
        )


if __name__ == "__main__":
    unittest.main()
