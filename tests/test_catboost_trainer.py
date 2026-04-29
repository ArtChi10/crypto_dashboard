import unittest

import pandas as pd
from catboost import CatBoostClassifier

from mlcore.training import CatBoostTrainer


class CatBoostTrainerTests(unittest.TestCase):
    def setUp(self):
        self.trainer = CatBoostTrainer(iterations=5, verbose=False)

    def test_get_feature_columns_excludes_reserved_and_non_numeric_columns(self):
        df = self._make_frame()

        feature_columns = self.trainer.get_feature_columns(df)

        self.assertEqual(feature_columns, ["feature_1", "feature_2"])

    def test_train_returns_catboost_classifier_with_default_parameters(self):
        df = self._make_frame()

        model = self.trainer.train(df, df["target"])

        self.assertIsInstance(model, CatBoostClassifier)
        params = model.get_params()
        self.assertEqual(params["iterations"], 5)
        self.assertEqual(params["learning_rate"], 0.05)
        self.assertEqual(params["depth"], 6)
        self.assertEqual(params["loss_function"], "Logloss")
        self.assertEqual(params["eval_metric"], "AUC")
        self.assertEqual(params["random_seed"], 42)
        self.assertFalse(params["verbose"])
        self.assertFalse(params["allow_writing_files"])

    def test_train_uses_only_selected_feature_columns(self):
        df = self._make_frame()

        model = self.trainer.train(df, df["target"])
        predictions = model.predict(df[self.trainer.feature_columns_])

        self.assertEqual(self.trainer.feature_columns_, ["feature_1", "feature_2"])
        self.assertEqual(len(predictions), len(df))

    def test_train_supports_validation_set(self):
        df = self._make_frame(row_count=40)
        train_df = df.iloc[:30].reset_index(drop=True)
        valid_df = df.iloc[30:].reset_index(drop=True)

        model = self.trainer.train(
            train_df,
            train_df["target"],
            x_valid=valid_df,
            y_valid=valid_df["target"],
        )

        self.assertIn("validation", model.get_evals_result())

    def test_train_raises_for_single_class_y_train(self):
        df = self._make_frame()

        with self.assertRaisesRegex(ValueError, "at least two classes"):
            self.trainer.train(df, [1] * len(df))

    def test_train_raises_without_numeric_feature_columns(self):
        df = self._make_frame()[["timestamp", "symbol", "target", "note"]]

        with self.assertRaisesRegex(ValueError, "numeric feature"):
            self.trainer.train(df, df["target"])

    def test_train_raises_for_incomplete_validation_set(self):
        df = self._make_frame()

        with self.assertRaisesRegex(ValueError, "provided together"):
            self.trainer.train(df, df["target"], x_valid=df)

    @staticmethod
    def _make_frame(row_count: int = 30) -> pd.DataFrame:
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


if __name__ == "__main__":
    unittest.main()
