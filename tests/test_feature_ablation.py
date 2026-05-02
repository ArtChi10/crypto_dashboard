import unittest

import pandas as pd

from mlcore.evaluation.ablation import FeatureAblationService
from mlcore.training.baseline_trainer import BaselineTrainer
from mlcore.training.dummy_trainer import DummyBaselineTrainer


class FeatureAblationServiceTests(unittest.TestCase):
    def test_default_feature_groups_are_defined(self):
        groups = FeatureAblationService.DEFAULT_FEATURE_GROUPS

        self.assertEqual(groups["price_raw"], ("open", "high", "low", "close"))
        self.assertEqual(groups["returns"], ("return_1", "return_3", "return_6", "return_12"))
        self.assertEqual(groups["moving_average"], ("ma_7", "ma_14", "ema_7", "ema_30"))
        self.assertEqual(groups["volatility"], ("volatility_7", "volatility_14"))
        self.assertEqual(groups["volume"], ("volume", "volume_change", "volume_ma_7"))
        self.assertEqual(groups["candle"], ("candle_body", "candle_range"))

    def test_evaluate_groups_runs_all_features_and_without_each_group(self):
        train, test = self._make_train_test()

        result = FeatureAblationService().evaluate_groups(
            lambda: DummyBaselineTrainer(),
            train,
            test,
        )

        self.assertEqual(len(result), 7)
        self.assertEqual(
            result["experiment"].tolist(),
            [
                "all_features",
                "without_price_raw",
                "without_returns",
                "without_moving_average",
                "without_volatility",
                "without_volume",
                "without_candle",
            ],
        )
        self.assertEqual(result.loc[0, "included_feature_count"], 19)
        self.assertTrue(result["accuracy"].notna().all())
        self.assertTrue(result["error_message"].isna().all())

    def test_evaluate_groups_handles_missing_group_with_error_row(self):
        train, test = self._make_train_test(include_all_groups=False)

        result = FeatureAblationService().evaluate_groups(
            lambda: DummyBaselineTrainer(),
            train,
            test,
        )

        missing_row = result[result["experiment"] == "without_volatility"].iloc[0]
        self.assertEqual(missing_row["included_feature_count"], 0)
        self.assertIn("volatility", missing_row["error_message"])
        self.assertTrue(pd.isna(missing_row["accuracy"]))

    def test_evaluate_groups_supports_only_groups_mode(self):
        train, test = self._make_train_test()

        result = FeatureAblationService().evaluate_groups(
            lambda: DummyBaselineTrainer(),
            train,
            test,
            feature_groups={"price_raw": ["open", "close"], "returns": ["return_1"]},
            mode="only_groups",
        )

        self.assertEqual(result["experiment"].tolist(), ["price_raw", "returns"])
        self.assertEqual(result["included_feature_count"].tolist(), [2, 1])
        self.assertTrue(result["error_message"].isna().all())

    def test_evaluate_groups_uses_fresh_trainer_per_experiment(self):
        train, test = self._make_train_test()
        trainers = []

        def trainer_factory():
            trainer = RecordingTrainer()
            trainers.append(trainer)
            return trainer

        FeatureAblationService().evaluate_groups(
            trainer_factory,
            train,
            test,
            feature_groups={"price_raw": ["open"], "returns": ["return_1"]},
            mode="only_groups",
        )

        self.assertEqual(len(trainers), 2)
        self.assertEqual([trainer.train_call_count for trainer in trainers], [1, 1])
        self.assertEqual(trainers[0].train_columns, [["open"]])
        self.assertEqual(trainers[1].train_columns, [["return_1"]])

    def test_evaluate_groups_uses_injected_evaluator(self):
        train, test = self._make_train_test()
        evaluator = RecordingEvaluator()

        result = FeatureAblationService(evaluator=evaluator).evaluate_groups(
            lambda: DummyBaselineTrainer(),
            train,
            test,
            feature_groups={"price_raw": ["open"]},
            mode="only_groups",
        )

        self.assertEqual(evaluator.call_count, 1)
        self.assertEqual(result.loc[0, "accuracy"], 0.25)
        self.assertIsNone(result.loc[0, "roc_auc"])

    def test_evaluate_groups_records_training_error(self):
        train, test = self._make_train_test()
        train["target"] = 0

        result = FeatureAblationService().evaluate_groups(
            lambda: BaselineTrainer(),
            train,
            test,
            feature_groups={"price_raw": ["open", "close"]},
            mode="only_groups",
        )

        self.assertIn("at least two classes", result.loc[0, "error_message"])
        self.assertTrue(pd.isna(result.loc[0, "accuracy"]))

    def test_evaluate_groups_can_raise_training_error(self):
        train, test = self._make_train_test()
        train["target"] = 0

        with self.assertRaisesRegex(ValueError, "at least two classes"):
            FeatureAblationService().evaluate_groups(
                lambda: BaselineTrainer(),
                train,
                test,
                feature_groups={"price_raw": ["open", "close"]},
                mode="only_groups",
                raise_on_error=True,
            )

    def test_evaluate_groups_validates_inputs(self):
        train, test = self._make_train_test()

        with self.assertRaisesRegex(ValueError, "trainer_factory"):
            FeatureAblationService().evaluate_groups(DummyBaselineTrainer(), train, test)
        with self.assertRaisesRegex(ValueError, "Missing required columns: target"):
            FeatureAblationService().evaluate_groups(
                lambda: DummyBaselineTrainer(),
                train.drop(columns=["target"]),
                test,
            )
        with self.assertRaisesRegex(ValueError, "mode"):
            FeatureAblationService().evaluate_groups(
                lambda: DummyBaselineTrainer(),
                train,
                test,
                mode="unknown",
            )

    @staticmethod
    def _make_train_test(include_all_groups=True):
        row_count = 60
        data = {
            "timestamp": pd.date_range("2024-01-01", periods=row_count, freq="h"),
            "symbol": ["BTCUSDT"] * row_count,
            "open": range(row_count),
            "high": range(1, row_count + 1),
            "low": range(row_count),
            "close": range(row_count),
            "return_1": [0.1] * row_count,
            "volume": range(100, 100 + row_count),
            "target": [index % 2 for index in range(row_count)],
        }
        if include_all_groups:
            data.update(
                {
                    "return_3": [0.2] * row_count,
                    "return_6": [0.3] * row_count,
                    "return_12": [0.4] * row_count,
                    "ma_7": range(row_count),
                    "ma_14": range(row_count),
                    "ema_7": range(row_count),
                    "ema_30": range(row_count),
                    "volatility_7": [0.01] * row_count,
                    "volatility_14": [0.02] * row_count,
                    "volume_change": [0.5] * row_count,
                    "volume_ma_7": range(200, 200 + row_count),
                    "candle_body": [1] * row_count,
                    "candle_range": [2] * row_count,
                }
            )

        df = pd.DataFrame(data)
        train = df.iloc[:40].reset_index(drop=True)
        test = df.iloc[40:].reset_index(drop=True)
        return train, test


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
        self.train_call_count = 0
        self.train_columns = []

    def train(self, x_train, y_train):
        self.train_call_count += 1
        self.train_columns.append(list(x_train.columns))
        return AlternatingModel()


class AlternatingModel:
    def predict(self, x_test):
        return [index % 2 for index in range(len(x_test))]

    def predict_proba(self, x_test):
        return [[0.8, 0.2] if index % 2 == 0 else [0.2, 0.8] for index in range(len(x_test))]


if __name__ == "__main__":
    unittest.main()
