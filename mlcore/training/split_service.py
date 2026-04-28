from __future__ import annotations

from math import isclose
from numbers import Real

import pandas as pd


class SplitService:
    TIMESTAMP_COLUMN = "timestamp"
    _SIZE_TOLERANCE = 1e-8

    def split(
        self,
        df: pd.DataFrame,
        train_size: float = 0.70,
        valid_size: float = 0.15,
        test_size: float = 0.15,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        self._raise_for_missing_columns(df)
        self._validate_sizes(train_size, valid_size, test_size)

        sorted_df = self._sort_by_timestamp(df)
        train_end, valid_end = self._split_boundaries(
            len(sorted_df),
            train_size,
            valid_size,
        )

        train = sorted_df.iloc[:train_end].copy().reset_index(drop=True)
        valid = sorted_df.iloc[train_end:valid_end].copy().reset_index(drop=True)
        test = sorted_df.iloc[valid_end:].copy().reset_index(drop=True)

        return train, valid, test

    @classmethod
    def _raise_for_missing_columns(cls, df: pd.DataFrame) -> None:
        if cls.TIMESTAMP_COLUMN not in df.columns:
            raise ValueError(f"Missing required columns: {cls.TIMESTAMP_COLUMN}")

    @classmethod
    def _sort_by_timestamp(cls, df: pd.DataFrame) -> pd.DataFrame:
        timestamps = pd.to_datetime(
            df[cls.TIMESTAMP_COLUMN],
            errors="coerce",
            format="mixed",
        )
        invalid_timestamps = int(timestamps.isna().sum())
        if invalid_timestamps:
            raise ValueError(
                f"Column 'timestamp' contains {invalid_timestamps} invalid or empty value(s)."
            )

        sort_key = "__split_timestamp_sort_key"
        sorted_df = df.assign(**{sort_key: timestamps})
        sorted_df = sorted_df.sort_values(sort_key, kind="mergesort")
        return sorted_df.drop(columns=[sort_key])

    @classmethod
    def _validate_sizes(
        cls,
        train_size: float,
        valid_size: float,
        test_size: float,
    ) -> None:
        sizes = {
            "train_size": train_size,
            "valid_size": valid_size,
            "test_size": test_size,
        }
        for name, value in sizes.items():
            if isinstance(value, bool) or not isinstance(value, Real):
                raise ValueError(f"{name} must be a positive number less than 1.")
            if value <= 0 or value >= 1:
                raise ValueError(f"{name} must be a positive number less than 1.")

        total = train_size + valid_size + test_size
        if not isclose(total, 1.0, rel_tol=0.0, abs_tol=cls._SIZE_TOLERANCE):
            raise ValueError("train_size + valid_size + test_size must be equal to 1.")

    @staticmethod
    def _split_boundaries(
        row_count: int,
        train_size: float,
        valid_size: float,
    ) -> tuple[int, int]:
        if row_count < 3:
            raise ValueError("Dataset must contain enough rows for train, valid, and test splits.")

        train_count = int(row_count * train_size)
        valid_count = int(row_count * valid_size)
        test_count = row_count - train_count - valid_count

        if min(train_count, valid_count, test_count) < 1:
            raise ValueError("Dataset is too small for non-empty train, valid, and test splits.")

        return train_count, train_count + valid_count
