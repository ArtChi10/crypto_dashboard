from __future__ import annotations

from numbers import Integral

import pandas as pd


class TargetBuilder:
    REQUIRED_COLUMNS = ("timestamp", "close", "symbol")

    def build(self, df: pd.DataFrame, horizon: int = 3) -> pd.DataFrame:
        self._validate_horizon(horizon)
        self._raise_for_missing_columns(df)

        result = df.copy()
        result = result.sort_values(["symbol", "timestamp"], kind="mergesort")
        by_symbol = result.groupby("symbol", sort=False, group_keys=False)

        future_close = by_symbol["close"].shift(-horizon)
        result["target"] = (future_close > result["close"]).astype(int)
        result = result.loc[future_close.notna()]

        return result.reset_index(drop=True)

    @classmethod
    def _raise_for_missing_columns(cls, df: pd.DataFrame) -> None:
        missing_columns = [column for column in cls.REQUIRED_COLUMNS if column not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

    @staticmethod
    def _validate_horizon(horizon: int) -> None:
        if isinstance(horizon, bool) or not isinstance(horizon, Integral):
            raise ValueError("horizon must be an integer greater than or equal to 1")
        if horizon < 1:
            raise ValueError("horizon must be an integer greater than or equal to 1")
