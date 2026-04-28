from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    errors: list[str]


class DataCleaner:
    REQUIRED_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume", "symbol")
    NUMERIC_COLUMNS = ("open", "high", "low", "close", "volume")

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        self._raise_for_missing_columns(df)

        cleaned = df.copy()
        cleaned["timestamp"] = pd.to_datetime(
            cleaned["timestamp"],
            errors="coerce",
            format="mixed",
        )
        for column in self.NUMERIC_COLUMNS:
            cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")

        cleaned = cleaned.dropna(subset=["timestamp", "close"])
        cleaned = cleaned.drop_duplicates(subset=["symbol", "timestamp"])
        cleaned = cleaned.sort_values(["symbol", "timestamp"], kind="mergesort")
        cleaned = cleaned.loc[~(cleaned["volume"] < 0)]

        return cleaned.reset_index(drop=True)

    def validate(self, df: pd.DataFrame) -> ValidationResult:
        errors: list[str] = []
        missing_columns = self._missing_columns(df)
        if missing_columns:
            errors.append(f"Missing required columns: {', '.join(missing_columns)}")
            return ValidationResult(is_valid=False, errors=errors)

        timestamps = pd.to_datetime(df["timestamp"], errors="coerce", format="mixed")
        invalid_timestamps = int(timestamps.isna().sum())
        if invalid_timestamps:
            errors.append(
                f"Column 'timestamp' contains {invalid_timestamps} invalid or empty value(s)."
            )

        for column in self.NUMERIC_COLUMNS:
            numeric_values = pd.to_numeric(df[column], errors="coerce")
            invalid_values = int(numeric_values.isna().sum())
            if invalid_values:
                errors.append(
                    f"Column '{column}' contains {invalid_values} invalid or empty "
                    "numeric value(s)."
                )

            if column == "volume":
                negative_values = int((numeric_values < 0).sum())
                if negative_values:
                    errors.append(f"Column 'volume' contains {negative_values} negative value(s).")

        return ValidationResult(is_valid=not errors, errors=errors)

    @classmethod
    def _raise_for_missing_columns(cls, df: pd.DataFrame) -> None:
        missing_columns = cls._missing_columns(df)
        if missing_columns:
            raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

    @classmethod
    def _missing_columns(cls, df: pd.DataFrame) -> list[str]:
        return [column for column in cls.REQUIRED_COLUMNS if column not in df.columns]
