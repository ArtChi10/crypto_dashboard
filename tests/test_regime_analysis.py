import unittest

import pandas as pd

from mlcore.evaluation.regime import RegimeAnalysisService


class RegimeAnalysisServiceTests(unittest.TestCase):
    def test_add_regime_labels_creates_volatility_and_trend_labels(self):
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=6, freq="h"),
                "close": [100, 101, 102, 103, 105, 108],
                "volatility_14": [0.01, 0.02, 0.03, 0.04, 0.05, 0.06],
            }
        )

        result = RegimeAnalysisService().add_regime_labels(
            df,
            trend_window=2,
            trend_threshold=0.01,
        )

        self.assertIn("volatility_regime", result.columns)
        self.assertIn("trend_return", result.columns)
        self.assertIn("trend_regime", result.columns)
        self.assertIn("low_volatility", set(result["volatility_regime"]))
        self.assertIn("medium_volatility", set(result["volatility_regime"]))
        self.assertIn("high_volatility", set(result["volatility_regime"]))
        self.assertIn("uptrend", set(result["trend_regime"]))

    def test_add_regime_labels_handles_nan_values(self):
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=4, freq="h"),
                "close": [100, None, 101, 102],
                "volatility_14": [None, None, 0.02, 0.03],
            }
        )

        result = RegimeAnalysisService().add_regime_labels(df, trend_window=1)

        self.assertIn("unknown_volatility", set(result["volatility_regime"]))
        self.assertIn("unknown_trend", set(result["trend_regime"]))

    def test_evaluate_by_regime_returns_metrics(self):
        predictions = pd.DataFrame(
            {
                "volatility_regime": [
                    "low_volatility",
                    "low_volatility",
                    "high_volatility",
                    "high_volatility",
                ],
                "y_true": [0, 1, 0, 1],
                "y_pred": [0, 0, 1, 1],
                "y_proba": [0.2, 0.4, 0.8, 0.7],
            }
        )

        result = RegimeAnalysisService().evaluate_by_regime(
            predictions,
            regime_col="volatility_regime",
        )

        self.assertEqual(set(result["regime"]), {"low_volatility", "high_volatility"})
        self.assertTrue(
            {"accuracy", "precision", "recall", "f1", "roc_auc"}.issubset(result.columns)
        )

    def test_evaluate_by_regime_handles_one_class_roc_auc(self):
        predictions = pd.DataFrame(
            {
                "trend_regime": ["sideways", "sideways", "uptrend", "uptrend"],
                "y_true": [1, 1, 0, 1],
                "y_pred": [1, 0, 0, 1],
                "y_proba": [0.8, 0.4, 0.2, 0.9],
            }
        )

        result = RegimeAnalysisService().evaluate_by_regime(
            predictions,
            regime_col="trend_regime",
        )
        sideways_row = result.loc[result["regime"] == "sideways"].iloc[0]

        self.assertTrue(pd.isna(sideways_row["roc_auc"]))

    def test_evaluate_by_regime_requires_columns(self):
        with self.assertRaisesRegex(ValueError, "Missing required columns"):
            RegimeAnalysisService().evaluate_by_regime(
                pd.DataFrame({"y_true": [0], "y_pred": [0]}),
                regime_col="trend_regime",
            )


if __name__ == "__main__":
    unittest.main()
