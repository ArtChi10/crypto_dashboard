import unittest

import pandas as pd

from mlcore.targets import TargetBuilder


class TargetBuilderTests(unittest.TestCase):
    def setUp(self):
        self.builder = TargetBuilder()

    def test_build_adds_target_and_drops_future_close(self):
        df = self._make_price_frame()

        result = self.builder.build(df, horizon=2)

        self.assertIn("target", result.columns)
        self.assertNotIn("future_close", result.columns)
        self.assertEqual(result.groupby("symbol").size().to_dict(), {"BTCUSDT": 3, "ETHUSDT": 3})
        self.assertEqual(
            result.groupby("symbol")["target"].apply(list).to_dict(),
            {
                "BTCUSDT": [0, 1, 1],
                "ETHUSDT": [0, 0, 0],
            },
        )
        self.assertEqual(list(result.index), list(range(len(result))))

    def test_build_sorts_and_calculates_target_per_symbol(self):
        df = self._make_price_frame()
        row_order = [5, 1, 6, 0, 7, 2, 8, 3, 9, 4]
        df = df.iloc[row_order]

        result = self.builder.build(df, horizon=1)

        self.assertEqual(
            list(result[["symbol", "timestamp"]].itertuples(index=False, name=None)),
            sorted(result[["symbol", "timestamp"]].itertuples(index=False, name=None)),
        )
        self.assertEqual(result.groupby("symbol").size().to_dict(), {"BTCUSDT": 4, "ETHUSDT": 4})
        self.assertEqual(
            result.groupby("symbol")["target"].apply(list).to_dict(),
            {
                "BTCUSDT": [1, 0, 1, 1],
                "ETHUSDT": [0, 0, 0, 0],
            },
        )

    def test_build_raises_for_missing_columns(self):
        df = self._make_price_frame().drop(columns=["close"])

        with self.assertRaisesRegex(ValueError, "Missing required columns: close"):
            self.builder.build(df)

    def test_build_validates_horizon(self):
        df = self._make_price_frame()

        for horizon in (0, -1, 1.5, "2", True):
            with self.subTest(horizon=horizon):
                with self.assertRaisesRegex(ValueError, "horizon must be an integer"):
                    self.builder.build(df, horizon=horizon)

    @staticmethod
    def _make_price_frame():
        timestamps = pd.date_range("2024-01-01", periods=5, freq="h")
        return pd.DataFrame(
            {
                "timestamp": timestamps.tolist() * 2,
                "close": [1, 2, 1, 3, 4, 5, 4, 3, 2, 1],
                "symbol": ["BTCUSDT"] * 5 + ["ETHUSDT"] * 5,
            }
        )


if __name__ == "__main__":
    unittest.main()
