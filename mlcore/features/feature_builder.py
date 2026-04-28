from __future__ import annotations

import pandas as pd


class FeatureBuilder:
    REQUIRED_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume", "symbol")
    FEATURE_COLUMNS = (
        "return_1",
        "return_3",
        "return_6",
        "return_12",
        "ma_7",
        "ma_14",
        "ema_7",
        "ema_30",
        "volatility_7",
        "volatility_14",
        "volume_change",
        "volume_ma_7",
        "candle_body",
        "candle_range",
    )

    def build(self, df: pd.DataFrame) -> pd.DataFrame:
        self._raise_for_missing_columns(df)

        features = df.copy()
        features = features.sort_values(["symbol", "timestamp"], kind="mergesort")
        by_symbol = features.groupby("symbol", sort=False, group_keys=False)

        for period in (1, 3, 6, 12):
            previous_close = by_symbol["close"].shift(period)
            features[f"return_{period}"] = (features["close"] / previous_close) - 1

        for window in (7, 14):
            features[f"ma_{window}"] = by_symbol["close"].transform(
                lambda values, window=window: values.rolling(
                    window=window,
                    min_periods=window,
                ).mean()
            )

        for span in (7, 30):
            features[f"ema_{span}"] = by_symbol["close"].transform(
                lambda values, span=span: values.ewm(span=span, adjust=False).mean()
            )

        return_1_by_symbol = features.groupby("symbol", sort=False, group_keys=False)["return_1"]
        for window in (7, 14):
            features[f"volatility_{window}"] = return_1_by_symbol.transform(
                lambda values, window=window: values.rolling(
                    window=window,
                    min_periods=window,
                ).std()
            )

        previous_volume = by_symbol["volume"].shift(1)
        features["volume_change"] = (features["volume"] / previous_volume) - 1
        features["volume_ma_7"] = by_symbol["volume"].transform(
            lambda values: values.rolling(window=7, min_periods=7).mean()
        )
        features["candle_body"] = features["close"] - features["open"]
        features["candle_range"] = features["high"] - features["low"]

        features = features.dropna(subset=self.FEATURE_COLUMNS)
        return features.reset_index(drop=True)

    @classmethod
    def _raise_for_missing_columns(cls, df: pd.DataFrame) -> None:
        missing_columns = [column for column in cls.REQUIRED_COLUMNS if column not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")
