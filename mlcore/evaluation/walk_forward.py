from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral

import pandas as pd


@dataclass(frozen=True)
class WalkForwardFold:
    fold_id: int
    train: pd.DataFrame
    test: pd.DataFrame
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


class WalkForwardValidationService:
    def split(
        self,
        df: pd.DataFrame,
        train_window: int,
        test_window: int,
        step: int | None = None,
        timestamp_col: str = "timestamp",
    ) -> list[WalkForwardFold]:
        train_window = self._validate_positive_int("train_window", train_window)
        test_window = self._validate_positive_int("test_window", test_window)
        if step is None:
            step = test_window
        step = self._validate_positive_int("step", step)

        sorted_df = self._sorted_dataframe(df, timestamp_col=timestamp_col)
        if len(sorted_df) < train_window + test_window:
            raise ValueError("dataset must be large enough for at least one fold.")

        folds = []
        fold_id = 1
        start = 0
        while start + train_window + test_window <= len(sorted_df):
            train_start_index = start
            train_end_index = start + train_window
            test_end_index = train_end_index + test_window

            train_df = sorted_df.iloc[train_start_index:train_end_index].copy()
            test_df = sorted_df.iloc[train_end_index:test_end_index].copy()
            folds.append(
                WalkForwardFold(
                    fold_id=fold_id,
                    train=train_df.reset_index(drop=True),
                    test=test_df.reset_index(drop=True),
                    train_start=train_df[timestamp_col].iloc[0],
                    train_end=train_df[timestamp_col].iloc[-1],
                    test_start=test_df[timestamp_col].iloc[0],
                    test_end=test_df[timestamp_col].iloc[-1],
                )
            )
            fold_id += 1
            start += step

        return folds

    @staticmethod
    def _validate_positive_int(name: str, value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, Integral):
            raise ValueError(f"{name} must be a positive integer.")
        normalized = int(value)
        if normalized < 1:
            raise ValueError(f"{name} must be a positive integer.")
        return normalized

    @staticmethod
    def _sorted_dataframe(df: pd.DataFrame, timestamp_col: str) -> pd.DataFrame:
        if timestamp_col not in df.columns:
            raise ValueError(f"Missing required columns: {timestamp_col}")

        sorted_df = df.copy()
        sorted_df[timestamp_col] = pd.to_datetime(sorted_df[timestamp_col])
        return sorted_df.sort_values(timestamp_col).reset_index(drop=True)
