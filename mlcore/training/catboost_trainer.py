from __future__ import annotations

from typing import Any

import pandas as pd
from catboost import CatBoostClassifier


class CatBoostTrainer:
    DEFAULT_MODEL_PARAMS = {
        "iterations": 100,
        "learning_rate": 0.05,
        "depth": 6,
        "loss_function": "Logloss",
        "eval_metric": "AUC",
        "random_seed": 42,
        "verbose": False,
        "allow_writing_files": False,
    }
    EXCLUDED_FEATURE_COLUMNS = frozenset({"target", "timestamp", "symbol"})

    def __init__(self, **model_params: Any):
        self.model_params = self.DEFAULT_MODEL_PARAMS | model_params

    def train(
        self,
        x_train: pd.DataFrame,
        y_train: Any,
        x_valid: pd.DataFrame | None = None,
        y_valid: Any | None = None,
    ) -> CatBoostClassifier:
        self._validate_y_train(y_train)
        feature_columns = self.get_feature_columns(x_train)
        if not feature_columns:
            raise ValueError("x_train must contain at least one numeric feature column.")

        self.feature_columns_ = feature_columns
        model = CatBoostClassifier(**self.model_params)
        fit_params = {}
        if x_valid is not None or y_valid is not None:
            if x_valid is None or y_valid is None:
                raise ValueError("x_valid and y_valid must be provided together.")
            fit_params["eval_set"] = (x_valid[feature_columns], y_valid)

        model.fit(x_train[feature_columns], y_train, **fit_params)
        return model

    def get_feature_columns(self, df: pd.DataFrame) -> list[str]:
        numeric_columns = df.select_dtypes(include="number").columns
        return [column for column in numeric_columns if column not in self.EXCLUDED_FEATURE_COLUMNS]

    @staticmethod
    def _validate_y_train(y_train: Any) -> None:
        if pd.Series(y_train).nunique(dropna=True) < 2:
            raise ValueError("y_train must contain at least two classes.")
