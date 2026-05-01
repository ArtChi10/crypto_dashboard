import unittest

import pandas as pd

from mlcore.evaluation.walk_forward import WalkForwardValidationService


class WalkForwardValidationServiceTests(unittest.TestCase):
    def test_split_creates_default_step_folds(self):
        df = self._make_dataset(row_count=30)

        folds = WalkForwardValidationService().split(df, train_window=10, test_window=5)

        self.assertEqual(len(folds), 4)
        self.assertEqual([fold.fold_id for fold in folds], [1, 2, 3, 4])
        for fold in folds:
            self.assertEqual(len(fold.train), 10)
            self.assertEqual(len(fold.test), 5)
            self.assertLess(fold.train["timestamp"].max(), fold.test["timestamp"].min())
            self.assertEqual(fold.train_start, fold.train["timestamp"].iloc[0])
            self.assertEqual(fold.train_end, fold.train["timestamp"].iloc[-1])
            self.assertEqual(fold.test_start, fold.test["timestamp"].iloc[0])
            self.assertEqual(fold.test_end, fold.test["timestamp"].iloc[-1])

    def test_split_respects_custom_step(self):
        df = self._make_dataset(row_count=25)

        folds = WalkForwardValidationService().split(
            df,
            train_window=8,
            test_window=4,
            step=3,
        )

        self.assertEqual(len(folds), 5)
        self.assertEqual(folds[0].train["value"].tolist(), list(range(8)))
        self.assertEqual(folds[1].train["value"].tolist(), list(range(3, 11)))
        self.assertEqual(folds[-1].test["value"].tolist(), list(range(20, 24)))

    def test_split_sorts_by_timestamp_without_shuffle(self):
        df = self._make_dataset(row_count=12).sort_values("timestamp", ascending=False)

        folds = WalkForwardValidationService().split(df, train_window=6, test_window=3)

        self.assertEqual(folds[0].train["value"].tolist(), list(range(6)))
        self.assertEqual(folds[0].test["value"].tolist(), list(range(6, 9)))

    def test_split_uses_custom_timestamp_column(self):
        df = self._make_dataset(row_count=12).rename(columns={"timestamp": "time"})

        folds = WalkForwardValidationService().split(
            df,
            train_window=6,
            test_window=3,
            timestamp_col="time",
        )

        self.assertEqual(len(folds), 2)
        self.assertLess(folds[0].train["time"].max(), folds[0].test["time"].min())

    def test_split_returns_copies_with_reset_indexes(self):
        df = self._make_dataset(row_count=12)

        fold = WalkForwardValidationService().split(df, train_window=6, test_window=3)[0]
        fold.train.loc[0, "value"] = 999

        self.assertEqual(df.loc[0, "value"], 0)
        self.assertEqual(fold.train.index.tolist(), list(range(6)))
        self.assertEqual(fold.test.index.tolist(), list(range(3)))

    def test_split_requires_timestamp_column(self):
        df = pd.DataFrame({"value": range(12), "target": [0, 1] * 6})

        with self.assertRaisesRegex(ValueError, "Missing required columns: timestamp"):
            WalkForwardValidationService().split(df, train_window=6, test_window=3)

    def test_split_requires_positive_windows_and_step(self):
        df = self._make_dataset(row_count=12)
        service = WalkForwardValidationService()

        with self.assertRaisesRegex(ValueError, "train_window"):
            service.split(df, train_window=0, test_window=3)
        with self.assertRaisesRegex(ValueError, "test_window"):
            service.split(df, train_window=6, test_window=0)
        with self.assertRaisesRegex(ValueError, "step"):
            service.split(df, train_window=6, test_window=3, step=0)

    def test_split_rejects_boolean_window_values(self):
        df = self._make_dataset(row_count=12)

        with self.assertRaisesRegex(ValueError, "train_window"):
            WalkForwardValidationService().split(df, train_window=True, test_window=3)

    def test_split_requires_dataset_large_enough_for_one_fold(self):
        df = self._make_dataset(row_count=8)

        with self.assertRaisesRegex(ValueError, "at least one fold"):
            WalkForwardValidationService().split(df, train_window=6, test_window=3)

    @staticmethod
    def _make_dataset(row_count):
        return pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=row_count, freq="h"),
                "value": range(row_count),
                "target": [i % 2 for i in range(row_count)],
            }
        )


if __name__ == "__main__":
    unittest.main()
