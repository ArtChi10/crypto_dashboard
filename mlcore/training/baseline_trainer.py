from __future__ import annotations

from typing import Any

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


class BaselineTrainer:
    EXCLUDED_FEATURE_COLUMNS = frozenset({"target", "timestamp", "symbol"})

    def train(
        self,
        x_train: pd.DataFrame,
        y_train: Any,
        x_valid: pd.DataFrame | None = None,
        y_valid: Any | None = None,
    ) -> Pipeline:
        self._validate_y_train(y_train)
        feature_columns = self.get_feature_columns(x_train)
        if not feature_columns:
            raise ValueError("x_train must contain at least one numeric feature column.")

        self.feature_columns_ = feature_columns
        model = self._build_pipeline()
        model.fit(x_train[feature_columns], y_train)

        return model

    def get_feature_columns(self, df: pd.DataFrame) -> list[str]:
        numeric_columns = df.select_dtypes(include="number").columns
        return [column for column in numeric_columns if column not in self.EXCLUDED_FEATURE_COLUMNS]

    @staticmethod
    def _validate_y_train(y_train: Any) -> None:
        if pd.Series(y_train).nunique(dropna=True) < 2:
            raise ValueError("y_train must contain at least two classes.")

    @staticmethod
    def _build_pipeline() -> Pipeline:
        return Pipeline(
            steps=[
                ("standard_scaler", StandardScaler()),
                (
                    "logistic_regression",
                    LogisticRegression(
                        max_iter=1000,
                        random_state=42,
                        class_weight=None,
                    ),
                ),
            ]
        )
