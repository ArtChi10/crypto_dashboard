import unittest

import pandas as pd

from mlcore.preprocessing import DataCleaner, ValidationResult


class DataCleanerTests(unittest.TestCase):
    def setUp(self):
        self.cleaner = DataCleaner()

    def test_clean_converts_sorts_deduplicates_and_removes_invalid_rows(self):
        df = pd.DataFrame(
            {
                "timestamp": [
                    "2024-01-02",
                    "2024-01-01",
                    "2024-01-01",
                    "bad",
                    "2024-01-03",
                    "2024-01-04",
                    "2024-01-02",
                ],
                "open": ["1", "1", "1", "1", "1", "1", "2"],
                "high": ["2", "2", "2", "2", "2", "2", "3"],
                "low": ["0.5", "0.5", "0.5", "0.5", "0.5", "0.5", "1.5"],
                "close": ["1.5", "1.4", "1.4", "1.6", None, "1.7", "2.5"],
                "volume": ["10", "11", "11", "12", "13", "-1", "20"],
                "symbol": [
                    "BTCUSDT",
                    "BTCUSDT",
                    "BTCUSDT",
                    "BTCUSDT",
                    "BTCUSDT",
                    "BTCUSDT",
                    "ETHUSDT",
                ],
            }
        )

        cleaned = self.cleaner.clean(df)

        self.assertEqual(list(cleaned["symbol"]), ["BTCUSDT", "BTCUSDT", "ETHUSDT"])
        self.assertEqual(
            list(cleaned["timestamp"]),
            [
                pd.Timestamp("2024-01-01"),
                pd.Timestamp("2024-01-02"),
                pd.Timestamp("2024-01-02"),
            ],
        )
        self.assertEqual(list(cleaned["close"]), [1.4, 1.5, 2.5])
        self.assertEqual(list(cleaned.index), [0, 1, 2])
        self.assertEqual(len(cleaned), 3)

    def test_clean_raises_for_missing_columns(self):
        df = pd.DataFrame(
            {
                "timestamp": ["2024-01-01"],
                "open": [1],
                "high": [2],
                "low": [0.5],
                "close": [1.5],
                "symbol": ["BTCUSDT"],
            }
        )

        with self.assertRaisesRegex(ValueError, "Missing required columns: volume"):
            self.cleaner.clean(df)

    def test_validate_returns_missing_column_errors(self):
        df = pd.DataFrame(
            {
                "timestamp": ["2024-01-01"],
                "open": [1],
                "high": [2],
                "low": [0.5],
                "close": [1.5],
                "symbol": ["BTCUSDT"],
            }
        )

        result = self.cleaner.validate(df)

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.errors, ["Missing required columns: volume"])

    def test_validate_returns_invalid_value_errors(self):
        df = pd.DataFrame(
            {
                "timestamp": ["bad", "2024-01-01"],
                "open": ["x", "1"],
                "high": ["2", "2"],
                "low": ["0.5", "0.5"],
                "close": ["1.5", None],
                "volume": ["-1", "bad"],
                "symbol": ["BTCUSDT", "BTCUSDT"],
            }
        )

        result = self.cleaner.validate(df)

        self.assertFalse(result.is_valid)
        self.assertTrue(any("timestamp" in error for error in result.errors))
        self.assertTrue(any("'open'" in error for error in result.errors))
        self.assertTrue(any("'close'" in error for error in result.errors))
        self.assertTrue(any("'volume'" in error and "invalid" in error for error in result.errors))
        self.assertTrue(any("'volume'" in error and "negative" in error for error in result.errors))

    def test_validate_accepts_valid_dataframe(self):
        df = pd.DataFrame(
            {
                "timestamp": ["2024-01-01"],
                "open": ["1"],
                "high": ["2"],
                "low": ["0.5"],
                "close": ["1.5"],
                "volume": ["10"],
                "symbol": ["BTCUSDT"],
            }
        )

        result = self.cleaner.validate(df)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.errors, [])


if __name__ == "__main__":
    unittest.main()
