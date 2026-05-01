import unittest

import pandas as pd
from sklearn.dummy import DummyClassifier

from mlcore.training import DummyBaselineTrainer


class DummyBaselineTrainerTests(unittest.TestCase):
    def test_get_feature_columns_uses_numeric_columns_and_excludes_metadata(self):
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=3, freq="h"),
                "symbol": ["BTCUSDT"] * 3,
                "feature_1": [1.0, 2.0, 3.0],
                "feature_2": [1, 0, 1],
                "category": ["a", "b", "c"],
                "target": [0, 1, 0],
            }
        )

        features = DummyBaselineTrainer().get_feature_columns(df)

        self.assertEqual(features, ["feature_1", "feature_2"])

    def test_train_returns_dummy_classifier(self):
        x_train = pd.DataFrame({"feature_1": [1.0, 2.0, 3.0], "feature_2": [0, 1, 0]})
        y_train = pd.Series([0, 1, 1])

        model = DummyBaselineTrainer().train(x_train, y_train)

        self.assertIsInstance(model, DummyClassifier)
        self.assertTrue(hasattr(model, "predict"))

    def test_train_allows_one_class_y_train(self):
        x_train = pd.DataFrame({"feature_1": [1.0, 2.0, 3.0]})
        y_train = pd.Series([0, 0, 0])

        model = DummyBaselineTrainer().train(x_train, y_train)

        self.assertEqual(model.predict(x_train).tolist(), [0, 0, 0])

    def test_train_raises_when_y_train_is_empty(self):
        x_train = pd.DataFrame({"feature_1": []})
        y_train = pd.Series([], dtype=int)

        with self.assertRaisesRegex(ValueError, "at least one class"):
            DummyBaselineTrainer().train(x_train, y_train)


if __name__ == "__main__":
    unittest.main()
