import unittest

import pandas as pd

from mlcore.evaluation.error_analysis import PredictionErrorAnalysisService


class PredictionErrorAnalysisServiceTests(unittest.TestCase):
    def test_add_error_labels_marks_all_confusion_types(self):
        predictions = self._predictions()

        result = PredictionErrorAnalysisService().add_error_labels(predictions)

        self.assertEqual(
            result["error_type"].tolist(),
            [
                "true_negative",
                "false_positive",
                "false_negative",
                "true_positive",
            ],
        )
        self.assertEqual(result["is_error"].tolist(), [False, True, True, False])

    def test_confidence_uses_predicted_class_probability(self):
        predictions = self._predictions()

        result = PredictionErrorAnalysisService().add_error_labels(predictions)

        self.assertEqual(result["confidence"].round(2).tolist(), [0.8, 0.7, 0.6, 0.9])

    def test_summarize_errors_counts_core_error_metrics(self):
        predictions = self._predictions()

        summary = PredictionErrorAnalysisService().summarize_errors(predictions)

        self.assertEqual(summary["total_rows"], 4)
        self.assertEqual(summary["correct_count"], 2)
        self.assertEqual(summary["error_count"], 2)
        self.assertEqual(summary["true_positive_count"], 1)
        self.assertEqual(summary["true_negative_count"], 1)
        self.assertEqual(summary["false_positive_count"], 1)
        self.assertEqual(summary["false_negative_count"], 1)
        self.assertEqual(summary["error_rate"], 0.5)
        self.assertEqual(summary["false_positive_rate"], 0.5)
        self.assertEqual(summary["false_negative_rate"], 0.5)

    def test_probability_bins_handle_missing_probability(self):
        predictions = pd.DataFrame({"y_true": [0, 1], "y_pred": [0, 1]})

        result = PredictionErrorAnalysisService().summarize_by_probability_bins(predictions)

        self.assertTrue(result.empty)

    def test_probability_bins_count_errors(self):
        predictions = PredictionErrorAnalysisService().add_error_labels(self._predictions())

        result = PredictionErrorAnalysisService().summarize_by_probability_bins(
            predictions,
            bins=5,
        )

        self.assertIn("0.6-0.7", result["confidence_bin"].tolist())
        self.assertEqual(int(result["error_count"].sum()), 2)

    def test_high_confidence_errors_are_sorted_descending(self):
        predictions = self._predictions()

        result = PredictionErrorAnalysisService().high_confidence_errors(
            predictions,
            top_n=2,
        )

        self.assertEqual(result["error_type"].tolist(), ["false_positive", "false_negative"])
        self.assertEqual(result["confidence"].round(2).tolist(), [0.7, 0.6])

    def test_high_confidence_errors_requires_positive_top_n(self):
        with self.assertRaisesRegex(ValueError, "top_n"):
            PredictionErrorAnalysisService().high_confidence_errors(
                self._predictions(),
                top_n=0,
            )

    @staticmethod
    def _predictions():
        return pd.DataFrame(
            {
                "y_true": [0, 0, 1, 1],
                "y_pred": [0, 1, 0, 1],
                "y_proba": [0.2, 0.7, 0.4, 0.9],
            }
        )


if __name__ == "__main__":
    unittest.main()
