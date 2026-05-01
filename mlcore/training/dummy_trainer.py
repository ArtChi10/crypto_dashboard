from __future__ import annotations

from typing import Any

import pandas as pd
from sklearn.dummy import DummyClassifier


class DummyBaselineTrainer:
    EXCLUDED_FEATURE_COLUMNS = frozenset({"target", "timestamp", "symbol"})

    def __init__(
        self,
        strategy: str = "most_frequent",
        random_state: int = 42,
        **model_params: Any,
    ) -> None:
        self.strategy = strategy
        self.random_state = random_state
        self.model_params = model_params

    def train(
        self,
        x_train: pd.DataFrame,
        y_train: Any,
        x_valid: pd.DataFrame | None = None,
        y_valid: Any | None = None,
    ) -> DummyClassifier:
        self._validate_y_train(y_train)
        feature_columns = self.get_feature_columns(x_train)
        if not feature_columns:
            raise ValueError("x_train must contain at least one numeric feature column.")

        self.feature_columns_ = feature_columns
        model = self._build_model()
        model.fit(x_train[feature_columns], y_train)

        return model

    def get_feature_columns(self, df: pd.DataFrame) -> list[str]:
        numeric_columns = df.select_dtypes(include="number").columns
        return [column for column in numeric_columns if column not in self.EXCLUDED_FEATURE_COLUMNS]

    @staticmethod
    def _validate_y_train(y_train: Any) -> None:
        if pd.Series(y_train).dropna().empty:
            raise ValueError("y_train must contain at least one class.")

    def _build_model(self) -> DummyClassifier:
        return DummyClassifier(
            strategy=self.strategy,
            random_state=self.random_state,
            **self.model_params,
        )
