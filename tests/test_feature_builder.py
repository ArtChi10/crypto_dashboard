import unittest

import pandas as pd

from mlcore.features import FeatureBuilder


class FeatureBuilderTests(unittest.TestCase):
    def setUp(self):
        self.builder = FeatureBuilder()

    def test_build_creates_technical_features_and_removes_rolling_nans(self):
        df = self._make_price_frame(rows_per_symbol=20)

        result = self.builder.build(df)

        self.assertTrue(set(FeatureBuilder.FEATURE_COLUMNS).issubset(result.columns))
        self.assertEqual(int(result[list(FeatureBuilder.FEATURE_COLUMNS)].isna().sum().sum()), 0)
        self.assertEqual(list(result.index), list(range(len(result))))
        self.assertEqual(len(result), 12)

    def test_build_sorts_and_calculates_features_per_symbol(self):
        df = self._make_price_frame(rows_per_symbol=20)
        row_order = list(range(1, len(df), 2)) + list(range(0, len(df), 2))
        df = df.iloc[row_order]

        result = self.builder.build(df)

        self.assertEqual(
            list(result[["symbol", "timestamp"]].itertuples(index=False, name=None)),
            sorted(result[["symbol", "timestamp"]].itertuples(index=False, name=None)),
        )

        first_btc = result[result["symbol"] == "BTCUSDT"].iloc[0]
        first_eth = result[result["symbol"] == "ETHUSDT"].iloc[0]
        self.assertEqual(first_btc["timestamp"], pd.Timestamp("2024-01-01 14:00:00"))
        self.assertEqual(first_eth["timestamp"], pd.Timestamp("2024-01-01 14:00:00"))
        self.assertAlmostEqual(first_btc["return_1"], (15 / 14) - 1)
        self.assertAlmostEqual(first_eth["return_1"], (115 / 114) - 1)
        self.assertAlmostEqual(first_btc["volume_change"], (114 / 113) - 1)
        self.assertAlmostEqual(first_eth["volume_change"], (214 / 213) - 1)

    def test_build_uses_no_future_values(self):
        df = self._make_price_frame(rows_per_symbol=25)
        changed_future = df.copy()
        future_timestamp = pd.Timestamp("2024-01-01 20:00:00")
        mask = (changed_future["symbol"] == "BTCUSDT") & (
            changed_future["timestamp"] == future_timestamp
        )
        changed_future.loc[mask, "close"] = 10_000.0

        baseline = self.builder.build(df)
        changed = self.builder.build(changed_future)

        past_columns = ["symbol", "timestamp", *FeatureBuilder.FEATURE_COLUMNS]
        baseline_past = baseline[
            (baseline["symbol"] == "BTCUSDT") & (baseline["timestamp"] < future_timestamp)
        ][past_columns]
        changed_past = changed[
            (changed["symbol"] == "BTCUSDT") & (changed["timestamp"] < future_timestamp)
        ][past_columns]
        pd.testing.assert_frame_equal(
            baseline_past.reset_index(drop=True),
            changed_past.reset_index(drop=True),
        )

    def test_build_raises_for_missing_columns(self):
        df = self._make_price_frame(rows_per_symbol=20).drop(columns=["volume"])

        with self.assertRaisesRegex(ValueError, "Missing required columns: volume"):
            self.builder.build(df)

    @staticmethod
    def _make_price_frame(rows_per_symbol):
        rows = []
        for symbol, close_offset, volume_offset in (
            ("BTCUSDT", 0, 100),
            ("ETHUSDT", 100, 200),
        ):
            for index in range(rows_per_symbol):
                close = close_offset + index + 1
                rows.append(
                    {
                        "timestamp": pd.Timestamp("2024-01-01") + pd.Timedelta(hours=index),
                        "open": close - 0.5,
                        "high": close + 1,
                        "low": close - 1,
                        "close": close,
                        "volume": volume_offset + index,
                        "symbol": symbol,
                    }
                )
        return pd.DataFrame(rows)


if __name__ == "__main__":
    unittest.main()
