import unittest

import pandas as pd

from mlcore.training import SplitService


class SplitServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = SplitService()

    def test_split_returns_non_empty_time_ordered_parts(self):
        df = self._make_frame(row_count=20)
        df = df.iloc[[7, 1, 19, 0, 3, 11, 4, 18, 9, 2, 12, 5, 10, 6, 17, 8, 13, 14, 15, 16]]

        train, valid, test = self.service.split(
            df,
            train_size=0.60,
            valid_size=0.20,
            test_size=0.20,
        )

        self.assertEqual((len(train), len(valid), len(test)), (12, 4, 4))
        self.assertTrue(train["timestamp"].max() <= valid["timestamp"].min())
        self.assertTrue(valid["timestamp"].max() <= test["timestamp"].min())
        self.assertEqual(list(train.index), list(range(len(train))))
        self.assertEqual(list(valid.index), list(range(len(valid))))
        self.assertEqual(list(test.index), list(range(len(test))))

    def test_default_split_sizes(self):
        df = self._make_frame(row_count=100)

        train, valid, test = self.service.split(df)

        self.assertEqual((len(train), len(valid), len(test)), (70, 15, 15))

    def test_split_raises_for_invalid_sizes(self):
        df = self._make_frame(row_count=20)

        invalid_size_sets = (
            (0.70, 0.15, 0.20),
            (0.0, 0.50, 0.50),
            (0.70, -0.10, 0.40),
            (True, 0.20, 0.80),
            (0.70, "0.15", 0.15),
        )
        for sizes in invalid_size_sets:
            with self.subTest(sizes=sizes):
                with self.assertRaises(ValueError):
                    self.service.split(df, *sizes)

    def test_split_raises_for_too_small_dataset(self):
        df = self._make_frame(row_count=5)

        with self.assertRaisesRegex(ValueError, "too small"):
            self.service.split(df)

    def test_split_raises_for_missing_timestamp(self):
        df = self._make_frame(row_count=20).drop(columns=["timestamp"])

        with self.assertRaisesRegex(ValueError, "Missing required columns: timestamp"):
            self.service.split(df)

    def test_split_raises_for_invalid_timestamp_values(self):
        df = self._make_frame(row_count=20)
        df["timestamp"] = df["timestamp"].astype(str)
        df.loc[3, "timestamp"] = "not-a-date"

        with self.assertRaisesRegex(ValueError, "timestamp"):
            self.service.split(df)

    def test_split_returns_copies(self):
        df = self._make_frame(row_count=20)

        train, _, _ = self.service.split(df, train_size=0.60, valid_size=0.20, test_size=0.20)
        train.loc[0, "feature"] = 999

        self.assertNotEqual(df.loc[0, "feature"], 999)

    @staticmethod
    def _make_frame(row_count: int) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=row_count, freq="h"),
                "feature": range(row_count),
                "target": [index % 2 for index in range(row_count)],
            }
        )


if __name__ == "__main__":
    unittest.main()
