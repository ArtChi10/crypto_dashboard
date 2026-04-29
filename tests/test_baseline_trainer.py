import unittest

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from mlcore.training import BaselineTrainer


class BaselineTrainerTests(unittest.TestCase):
    def setUp(self):
        self.trainer = BaselineTrainer()

    def test_get_feature_columns_excludes_reserved_and_non_numeric_columns(self):
        df = self._make_frame()

        feature_columns = self.trainer.get_feature_columns(df)

        self.assertEqual(feature_columns, ["feature_1", "feature_2"])

    def test_train_returns_pipeline_with_scaler_and_logistic_regression(self):
        df = self._make_frame()

        model = self.trainer.train(df, df["target"])

        self.assertIsInstance(model, Pipeline)
        self.assertIsInstance(model.named_steps["standard_scaler"], StandardScaler)
        logistic_regression = model.named_steps["logistic_regression"]
        self.assertIsInstance(logistic_regression, LogisticRegression)
        self.assertEqual(logistic_regression.max_iter, 1000)
        self.assertEqual(logistic_regression.random_state, 42)
        self.assertIsNone(logistic_regression.class_weight)

    def test_train_uses_only_selected_feature_columns(self):
        df = self._make_frame()

        model = self.trainer.train(df, df["target"])
        predictions = model.predict(df[self.trainer.feature_columns_])

        self.assertEqual(self.trainer.feature_columns_, ["feature_1", "feature_2"])
        self.assertEqual(len(predictions), len(df))

    def test_train_raises_for_single_class_y_train(self):
        df = self._make_frame()

        with self.assertRaisesRegex(ValueError, "at least two classes"):
            self.trainer.train(df, [1] * len(df))

    def test_train_raises_without_numeric_feature_columns(self):
        df = self._make_frame()[["timestamp", "symbol", "target", "note"]]

        with self.assertRaisesRegex(ValueError, "numeric feature"):
            self.trainer.train(df, df["target"])

    @staticmethod
    def _make_frame() -> pd.DataFrame:
        return pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=20, freq="h"),
                "symbol": ["BTCUSDT"] * 20,
                "feature_1": range(20),
                "feature_2": [index % 3 for index in range(20)],
                "target": [0, 1] * 10,
                "note": ["ignore"] * 20,
            }
        )


if __name__ == "__main__":
    unittest.main()
