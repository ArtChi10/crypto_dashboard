import unittest

import pandas as pd

from mlcore.services.forecast_replay_service import ForecastReplayService


class ForecastReplayServiceTests(unittest.TestCase):
    def test_build_replay_returns_expected_columns_and_rows(self):
        model = FakeProbabilityModel(predictions=[1, 0, 1, 0, 1])

        result = ForecastReplayService().build_replay(
            history_df=self._frame(start=0, row_count=40),
            future_df=self._frame(start=40, row_count=10),
            model=model,
            feature_columns=["close", "return_1", "ma_7", "volume_ma_7"],
            horizon=3,
            replay_steps=5,
        )

        self.assertEqual(
            list(result.columns),
            [
                "timestamp",
                "close",
                "future_close",
                "actual_direction",
                "predicted_direction",
                "predicted_probability",
                "is_correct",
                "actual_change",
                "actual_change_pct",
                "predicted_label",
                "actual_label",
                "result_label",
            ],
        )
        self.assertEqual(len(result), 5)
        self.assertEqual(result["predicted_direction"].tolist(), [1, 0, 1, 0, 1])
        self.assertEqual(result["predicted_probability"].tolist(), [0.8, 0.2, 0.7, 0.3, 0.6])
        self.assertEqual(
            result["actual_direction"].tolist(),
            (result["future_close"] > result["close"]).astype(int).tolist(),
        )
        self.assertEqual(
            result["is_correct"].tolist(),
            (result["predicted_direction"] == result["actual_direction"]).tolist(),
        )
        expected_actual_change = result["future_close"] - result["close"]
        pd.testing.assert_series_equal(
            result["actual_change"],
            expected_actual_change,
            check_names=False,
        )
        pd.testing.assert_series_equal(
            result["actual_change_pct"],
            expected_actual_change / result["close"] * 100,
            check_names=False,
        )
        self.assertEqual(result["predicted_label"].tolist(), ["up", "down", "up", "down", "up"])
        self.assertEqual(
            result["actual_label"].tolist(),
            ["up" if value == 1 else "down" for value in result["actual_direction"]],
        )
        self.assertEqual(
            result["result_label"].tolist(),
            ["correct" if value else "wrong" for value in result["is_correct"]],
        )

    def test_build_replay_does_not_send_leakage_columns_to_model(self):
        model = FakeProbabilityModel(predictions=[1, 1, 0])
        history_df = self._frame(start=0, row_count=40)
        future_df = self._frame(start=40, row_count=8)
        history_df["target"] = [index % 2 for index in range(len(history_df))]
        future_df["target"] = [index % 2 for index in range(len(future_df))]

        ForecastReplayService().build_replay(
            history_df=history_df,
            future_df=future_df,
            model=model,
            feature_columns=["close", "return_1", "ma_7"],
            horizon=3,
            replay_steps=3,
        )

        self.assertEqual(model.seen_columns, ["close", "return_1", "ma_7"])
        self.assertFalse(
            {"future_close", "target", "timestamp", "symbol"} & set(model.seen_columns)
        )

    def test_build_replay_sets_probability_to_none_without_predict_proba(self):
        result = ForecastReplayService().build_replay(
            history_df=self._frame(start=0, row_count=40),
            future_df=self._frame(start=40, row_count=8),
            model=FakePredictOnlyModel(predictions=[0, 1, 0]),
            feature_columns=["close", "return_1", "ma_7"],
            horizon=3,
            replay_steps=3,
        )

        self.assertEqual(result["predicted_probability"].tolist(), [None, None, None])

    def test_build_replay_rejects_leakage_feature_columns(self):
        with self.assertRaisesRegex(ValueError, "leakage columns"):
            ForecastReplayService().build_replay(
                history_df=self._frame(start=0, row_count=40),
                future_df=self._frame(start=40, row_count=8),
                model=FakePredictOnlyModel(predictions=[0]),
                feature_columns=["close", "future_close"],
            )

    @staticmethod
    def _frame(start: int, row_count: int) -> pd.DataFrame:
        indices = range(start, start + row_count)
        close_values = [100 + ((index % 6) - 2) for index in indices]
        return pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=start + row_count, freq="h")[
                    start:
                ],
                "open": [value - 0.5 for value in close_values],
                "high": [value + 1.0 for value in close_values],
                "low": [value - 1.0 for value in close_values],
                "close": close_values,
                "volume": [1000 + index for index in indices],
                "symbol": ["BTCUSDT"] * row_count,
            }
        )


class FakeProbabilityModel:
    def __init__(self, predictions):
        self.predictions = predictions
        self.seen_columns = None

    def predict(self, x):
        self.seen_columns = list(x.columns)
        return self.predictions[: len(x)]

    def predict_proba(self, x):
        probabilities = [0.8, 0.2, 0.7, 0.3, 0.6]
        return [[1 - probability, probability] for probability in probabilities[: len(x)]]


class FakePredictOnlyModel:
    def __init__(self, predictions):
        self.predictions = predictions

    def predict(self, x):
        return self.predictions[: len(x)]


if __name__ == "__main__":
    unittest.main()
