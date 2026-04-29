import unittest

from mlcore.evaluation import Evaluator


class EvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.evaluator = Evaluator()

    def test_evaluate_predictions_returns_binary_classification_metrics(self):
        metrics = self.evaluator.evaluate_predictions(
            y_true=[0, 1, 1, 0],
            y_pred=[0, 1, 0, 0],
            y_proba=[0.1, 0.9, 0.4, 0.2],
        )

        self.assertEqual(
            set(metrics),
            {"accuracy", "precision", "recall", "f1", "roc_auc", "confusion_matrix"},
        )
        self.assertEqual(metrics["accuracy"], 0.75)
        self.assertEqual(metrics["precision"], 1.0)
        self.assertEqual(metrics["recall"], 0.5)
        self.assertAlmostEqual(metrics["f1"], 2 / 3)
        self.assertEqual(metrics["roc_auc"], 1.0)
        self.assertEqual(metrics["confusion_matrix"], [[2, 0], [1, 1]])

    def test_evaluate_predictions_sets_roc_auc_to_none_without_probabilities(self):
        metrics = self.evaluator.evaluate_predictions(
            y_true=[0, 1, 1, 0],
            y_pred=[0, 1, 0, 0],
        )

        self.assertIsNone(metrics["roc_auc"])

    def test_evaluate_predictions_sets_roc_auc_to_none_for_single_class(self):
        metrics = self.evaluator.evaluate_predictions(
            y_true=[0, 0, 0],
            y_pred=[0, 0, 0],
            y_proba=[0.1, 0.2, 0.3],
        )

        self.assertIsNone(metrics["roc_auc"])
        self.assertEqual(metrics["confusion_matrix"], [[3, 0], [0, 0]])

    def test_evaluate_predictions_uses_zero_division_for_empty_positive_predictions(self):
        metrics = self.evaluator.evaluate_predictions(
            y_true=[0, 1, 1, 0],
            y_pred=[0, 0, 0, 0],
        )

        self.assertEqual(metrics["precision"], 0.0)
        self.assertEqual(metrics["recall"], 0.0)
        self.assertEqual(metrics["f1"], 0.0)

    def test_evaluate_model_uses_predict_and_predict_proba(self):
        model = ModelWithProbabilities()

        metrics = self.evaluator.evaluate_model(
            model,
            x_test=["a", "b", "c", "d"],
            y_test=[0, 1, 1, 0],
        )

        self.assertEqual(model.seen_x_test, ["a", "b", "c", "d"])
        self.assertEqual(metrics["confusion_matrix"], [[2, 0], [1, 1]])
        self.assertEqual(metrics["roc_auc"], 1.0)

    def test_evaluate_model_sets_roc_auc_to_none_without_predict_proba(self):
        metrics = self.evaluator.evaluate_model(
            PredictOnlyModel(),
            x_test=["a", "b", "c", "d"],
            y_test=[0, 1, 1, 0],
        )

        self.assertIsNone(metrics["roc_auc"])


class ModelWithProbabilities:
    def __init__(self):
        self.seen_x_test = None

    def predict(self, x_test):
        self.seen_x_test = x_test
        return [0, 1, 0, 0]

    def predict_proba(self, x_test):
        self.seen_x_test = x_test
        return [
            [0.9, 0.1],
            [0.1, 0.9],
            [0.6, 0.4],
            [0.8, 0.2],
        ]


class PredictOnlyModel:
    def predict(self, x_test):
        return [0, 1, 0, 0]


if __name__ == "__main__":
    unittest.main()
