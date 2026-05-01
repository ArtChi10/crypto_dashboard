import unittest

import pandas as pd

from mlcore.evaluation.stability import PeriodStabilityAnalysisService


class PeriodStabilityAnalysisServiceTests(unittest.TestCase):
    def test_analyze_predictions_groups_daily_and_returns_metrics(self):
        df = self._make_hourly_predictions(row_count=48)

        result = PeriodStabilityAnalysisService().analyze_predictions(df, period="D")

        self.assertEqual(len(result), 2)
        self.assertEqual(result["rows"].tolist(), [24, 24])
        self.assertEqual(result["positive_rate"].tolist(), [0.5, 0.5])
        self.assertEqual(result["accuracy"].tolist(), [0.75, 0.75])
        self.assertAlmostEqual(result.loc[0, "precision"], 2 / 3)
        self.assertEqual(result["recall"].tolist(), [1.0, 1.0])
        self.assertEqual(result["f1"].tolist(), [0.8, 0.8])
        self.assertEqual(result["roc_auc"].tolist(), [1.0, 1.0])
        self.assertEqual(result.loc[0, "period_start"], pd.Timestamp("2024-01-01 00:00:00"))
        self.assertEqual(result.loc[0, "period_end"], pd.Timestamp("2024-01-01 23:00:00"))

    def test_analyze_predictions_groups_weekly(self):
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=14, freq="D"),
                "y_true": [0, 1] * 7,
                "y_pred": [0, 1] * 7,
                "y_proba": [0.1, 0.9] * 7,
            }
        )

        result = PeriodStabilityAnalysisService().analyze_predictions(df, period="W")

        self.assertEqual(len(result), 2)
        self.assertEqual(result["rows"].tolist(), [7, 7])
        self.assertEqual(result["accuracy"].tolist(), [1.0, 1.0])

    def test_analyze_predictions_sets_roc_auc_to_none_for_one_class_period(self):
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=48, freq="h"),
                "y_true": [0] * 24 + [0, 1] * 12,
                "y_pred": [0] * 24 + [0, 1] * 12,
                "y_proba": [0.1] * 24 + [0.1, 0.9] * 12,
            }
        )

        result = PeriodStabilityAnalysisService().analyze_predictions(df, period="D")

        self.assertIsNone(result.loc[0, "roc_auc"])
        self.assertEqual(result.loc[1, "roc_auc"], 1.0)

    def test_analyze_predictions_works_without_probabilities(self):
        df = self._make_hourly_predictions(row_count=24).drop(columns=["y_proba"])

        result = PeriodStabilityAnalysisService().analyze_predictions(df, period="D")

        self.assertIsNone(result.loc[0, "roc_auc"])
        self.assertEqual(result.loc[0, "rows"], 24)

    def test_analyze_predictions_filters_periods_below_min_rows(self):
        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-02"]),
                "y_true": [0, 0, 1],
                "y_pred": [0, 0, 1],
            }
        )

        result = PeriodStabilityAnalysisService().analyze_predictions(
            df,
            period="D",
            min_rows=2,
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result.loc[0, "period_start"], pd.Timestamp("2024-01-02"))
        self.assertEqual(result.loc[0, "rows"], 2)

    def test_analyze_predictions_uses_injected_evaluator(self):
        evaluator = RecordingEvaluator()
        service = PeriodStabilityAnalysisService(evaluator=evaluator)

        result = service.analyze_predictions(self._make_hourly_predictions(row_count=48))

        self.assertEqual(evaluator.call_count, 2)
        self.assertEqual(result["accuracy"].tolist(), [0.5, 0.5])
        self.assertEqual(result["roc_auc"].tolist(), [None, None])

    def test_analyze_predictions_requires_prediction_columns(self):
        df = pd.DataFrame({"timestamp": pd.date_range("2024-01-01", periods=3, freq="h")})

        with self.assertRaisesRegex(ValueError, "Missing required columns: y_pred, y_true"):
            PeriodStabilityAnalysisService().analyze_predictions(df)

    def test_analyze_predictions_requires_positive_min_rows(self):
        with self.assertRaisesRegex(ValueError, "min_rows"):
            PeriodStabilityAnalysisService().analyze_predictions(
                self._make_hourly_predictions(),
                min_rows=0,
            )

    @staticmethod
    def _make_hourly_predictions(row_count=24):
        pattern_count = row_count // 4
        return pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=row_count, freq="h"),
                "y_true": [0, 1, 0, 1] * pattern_count,
                "y_pred": [0, 1, 1, 1] * pattern_count,
                "y_proba": [0.1, 0.8, 0.6, 0.7] * pattern_count,
            }
        )


class RecordingEvaluator:
    def __init__(self):
        self.call_count = 0

    def evaluate_predictions(self, y_true, y_pred, y_proba=None):
        self.call_count += 1
        return {
            "accuracy": 0.5,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "roc_auc": None,
            "confusion_matrix": [[1, 0], [1, 0]],
        }


if __name__ == "__main__":
    unittest.main()
