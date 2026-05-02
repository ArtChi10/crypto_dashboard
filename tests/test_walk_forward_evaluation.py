import unittest

import pandas as pd

from mlcore.evaluation.walk_forward import WalkForwardEvaluationService
from mlcore.training.baseline_trainer import BaselineTrainer
from mlcore.training.dummy_trainer import DummyBaselineTrainer


class WalkForwardEvaluationServiceTests(unittest.TestCase):
    def test_evaluate_returns_metrics_by_fold(self):
        df = self._make_dataset(row_count=60)

        result = WalkForwardEvaluationService().evaluate(
            DummyBaselineTrainer(),
            df,
            train_window=20,
            test_window=10,
        )

        self.assertEqual(len(result), 4)
        self.assertEqual(result["fold_id"].tolist(), [1, 2, 3, 4])
        self.assertEqual(result["train_rows"].tolist(), [20, 20, 20, 20])
        self.assertEqual(result["test_rows"].tolist(), [10, 10, 10, 10])
        self.assertTrue(result["accuracy"].notna().all())
        self.assertTrue(result["precision"].notna().all())
        self.assertTrue(result["recall"].notna().all())
        self.assertTrue(result["f1"].notna().all())
        self.assertTrue(result["error_message"].isna().all())

    def test_evaluate_uses_injected_evaluator(self):
        df = self._make_dataset(row_count=40)
        evaluator = RecordingEvaluator()

        result = WalkForwardEvaluationService(evaluator=evaluator).evaluate(
            DummyBaselineTrainer(),
            df,
            train_window=20,
            test_window=10,
        )

        self.assertEqual(evaluator.call_count, 2)
        self.assertEqual(result["accuracy"].tolist(), [0.25, 0.25])
        self.assertEqual(result["roc_auc"].tolist(), [None, None])

    def test_evaluate_uses_trainer_feature_columns(self):
        df = self._make_dataset(row_count=30)
        trainer = RecordingTrainer()

        WalkForwardEvaluationService().evaluate(
            trainer,
            df,
            train_window=10,
            test_window=5,
        )

        self.assertEqual(
            trainer.train_columns,
            [["feature_1"], ["feature_1"], ["feature_1"], ["feature_1"]],
        )

    def test_evaluate_falls_back_to_numeric_feature_columns(self):
        df = self._make_dataset(row_count=30)
        trainer = TrainerWithoutFeatureSelector()

        WalkForwardEvaluationService().evaluate(
            trainer,
            df,
            train_window=10,
            test_window=5,
        )

        self.assertEqual(trainer.train_columns[0], ["feature_1", "feature_2"])

    def test_evaluate_records_error_row_when_fold_training_fails(self):
        df = self._make_one_class_first_fold_dataset()

        result = WalkForwardEvaluationService().evaluate(
            BaselineTrainer(),
            df,
            train_window=10,
            test_window=5,
            step=10,
        )

        self.assertEqual(len(result), 2)
        self.assertIn("at least two classes", result.loc[0, "error_message"])
        self.assertTrue(pd.isna(result.loc[0, "accuracy"]))
        self.assertTrue(pd.isna(result.loc[0, "f1"]))

    def test_evaluate_can_raise_fold_training_errors(self):
        df = self._make_one_class_first_fold_dataset()

        with self.assertRaisesRegex(ValueError, "at least two classes"):
            WalkForwardEvaluationService().evaluate(
                BaselineTrainer(),
                df,
                train_window=10,
                test_window=5,
                step=10,
                raise_on_error=True,
            )

    def test_evaluate_requires_target_column(self):
        df = self._make_dataset(row_count=30).drop(columns=["target"])

        with self.assertRaisesRegex(ValueError, "Missing required columns: target"):
            WalkForwardEvaluationService().evaluate(
                DummyBaselineTrainer(),
                df,
                train_window=10,
                test_window=5,
            )

    @staticmethod
    def _make_dataset(row_count):
        return pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=row_count, freq="h"),
                "symbol": ["BTCUSDT"] * row_count,
                "feature_1": range(row_count),
                "feature_2": [index % 5 for index in range(row_count)],
                "category": ["ignored"] * row_count,
                "target": [index % 2 for index in range(row_count)],
            }
        )

    @staticmethod
    def _make_one_class_first_fold_dataset():
        row_count = 30
        return pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=row_count, freq="h"),
                "feature_1": range(row_count),
                "feature_2": [index % 3 for index in range(row_count)],
                "target": [0] * 10 + [index % 2 for index in range(20)],
            }
        )


class RecordingEvaluator:
    def __init__(self):
        self.call_count = 0

    def evaluate_predictions(self, y_true, y_pred, y_proba=None):
        self.call_count += 1
        return {
            "accuracy": 0.25,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "roc_auc": None,
            "confusion_matrix": [[1, 0], [1, 0]],
        }


class RecordingTrainer:
    def __init__(self):
        self.train_columns = []

    def get_feature_columns(self, df):
        return ["feature_1"]

    def train(self, x_train, y_train):
        self.train_columns.append(list(x_train.columns))
        return AlternatingModel()


class TrainerWithoutFeatureSelector:
    def __init__(self):
        self.train_columns = []

    def train(self, x_train, y_train):
        self.train_columns.append(list(x_train.columns))
        return AlternatingModel()


class AlternatingModel:
    def predict(self, x_test):
        return [index % 2 for index in range(len(x_test))]

    def predict_proba(self, x_test):
        return [[0.8, 0.2] if index % 2 == 0 else [0.2, 0.8] for index in range(len(x_test))]


if __name__ == "__main__":
    unittest.main()
