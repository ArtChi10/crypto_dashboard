from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

from mlcore.features import FeatureBuilder
from mlcore.preprocessing import DataCleaner


class ForecastReplayService:
    OUTPUT_COLUMNS = (
        "timestamp",
        "close",
        "future_close",
        "actual_direction",
        "predicted_direction",
        "predicted_probability",
        "is_correct",
    )
    FORBIDDEN_FEATURE_COLUMNS = frozenset(
        {
            "future_close",
            "actual_direction",
            "predicted_direction",
            "predicted_probability",
            "is_correct",
            "target",
            "timestamp",
            "symbol",
        }
    )
    _IS_FUTURE_COLUMN = "__forecast_replay_is_future"

    def __init__(
        self,
        data_cleaner: DataCleaner | None = None,
        feature_builder: FeatureBuilder | None = None,
    ) -> None:
        self.data_cleaner = data_cleaner or DataCleaner()
        self.feature_builder = feature_builder or FeatureBuilder()

    def build_replay(
        self,
        history_df: pd.DataFrame,
        future_df: pd.DataFrame,
        model: Any,
        feature_columns: Sequence[str],
        horizon: int = 3,
        replay_steps: int = 5,
    ) -> pd.DataFrame:
        horizon = self._validate_positive_int("horizon", horizon)
        replay_steps = self._validate_positive_int("replay_steps", replay_steps)
        feature_columns = self._validate_feature_columns(feature_columns)

        features = self._feature_frame(history_df, future_df, horizon=horizon)
        replay_rows = (
            features.loc[features[self._IS_FUTURE_COLUMN] & features["future_close"].notna(),]
            .head(replay_steps)
            .copy()
        )

        if replay_rows.empty:
            return pd.DataFrame(columns=self.OUTPUT_COLUMNS)

        self._raise_for_missing_features(replay_rows, feature_columns)
        x_replay = replay_rows.loc[:, feature_columns]
        predictions = self._predicted_directions(model.predict(x_replay), len(replay_rows))
        probabilities = self._predicted_probabilities(model, x_replay, len(replay_rows))

        actual_directions = (replay_rows["future_close"] > replay_rows["close"]).astype(int)
        result = pd.DataFrame(
            {
                "timestamp": replay_rows["timestamp"].to_numpy(),
                "close": replay_rows["close"].astype(float).to_numpy(),
                "future_close": replay_rows["future_close"].astype(float).to_numpy(),
                "actual_direction": actual_directions.to_numpy(),
                "predicted_direction": predictions,
                "predicted_probability": probabilities,
            }
        )
        result["is_correct"] = result["predicted_direction"] == result["actual_direction"]

        return result.loc[:, self.OUTPUT_COLUMNS]

    def _feature_frame(
        self,
        history_df: pd.DataFrame,
        future_df: pd.DataFrame,
        horizon: int,
    ) -> pd.DataFrame:
        if history_df.empty:
            raise ValueError("history_df must not be empty.")
        if future_df.empty:
            raise ValueError("future_df must not be empty.")

        history = history_df.copy()
        future = future_df.copy()
        history[self._IS_FUTURE_COLUMN] = False
        future[self._IS_FUTURE_COLUMN] = True

        combined = pd.concat([history, future], ignore_index=True)
        cleaned = self.data_cleaner.clean(combined)
        features = self.feature_builder.build(cleaned)
        features["future_close"] = features.groupby("symbol", sort=False)["close"].shift(-horizon)
        return features.reset_index(drop=True)

    @classmethod
    def _validate_feature_columns(cls, feature_columns: Sequence[str]) -> list[str]:
        normalized = [str(column) for column in feature_columns]
        if not normalized:
            raise ValueError("feature_columns must contain at least one column.")

        forbidden_columns = sorted(set(normalized) & cls.FORBIDDEN_FEATURE_COLUMNS)
        if forbidden_columns:
            raise ValueError(
                "feature_columns must not contain leakage columns: " + ", ".join(forbidden_columns)
            )
        return normalized

    @staticmethod
    def _validate_positive_int(name: str, value: int) -> int:
        if isinstance(value, bool):
            raise ValueError(f"{name} must be a positive integer.")
        try:
            normalized = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be a positive integer.") from exc
        if normalized < 1:
            raise ValueError(f"{name} must be a positive integer.")
        return normalized

    @staticmethod
    def _raise_for_missing_features(df: pd.DataFrame, feature_columns: list[str]) -> None:
        missing_columns = [column for column in feature_columns if column not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required feature columns: {', '.join(missing_columns)}")

    @staticmethod
    def _predicted_directions(predictions: Any, expected_length: int) -> list[int]:
        values = np.asarray(predictions).reshape(-1)
        if len(values) != expected_length:
            raise ValueError("model predictions length does not match replay rows.")
        return [int(value) for value in values]

    @classmethod
    def _predicted_probabilities(
        cls,
        model: Any,
        x_replay: pd.DataFrame,
        expected_length: int,
    ) -> list[float | None]:
        if not hasattr(model, "predict_proba"):
            return [None] * expected_length

        probabilities = np.asarray(model.predict_proba(x_replay))
        if probabilities.ndim == 2:
            if probabilities.shape[1] < 2:
                return [None] * expected_length
            values = probabilities[:, 1]
        else:
            values = probabilities.reshape(-1)

        if len(values) != expected_length:
            raise ValueError("model probabilities length does not match replay rows.")

        return [cls._optional_float(value) for value in values]

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if pd.isna(value):
            return None
        return float(value)
