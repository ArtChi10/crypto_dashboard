from __future__ import annotations

from typing import Any

import pandas as pd

from mlcore.evaluation.evaluator import Evaluator


class RegimeAnalysisService:
    METRIC_COLUMNS = ("accuracy", "precision", "recall", "f1", "roc_auc")

    def __init__(self, evaluator: Evaluator | None = None) -> None:
        self.evaluator = evaluator or Evaluator()

    def add_regime_labels(
        self,
        df: pd.DataFrame,
        timestamp_col: str = "timestamp",
        close_col: str = "close",
        volatility_col: str = "volatility_14",
        trend_window: int = 24,
        trend_threshold: float = 0.01,
    ) -> pd.DataFrame:
        if timestamp_col not in df.columns:
            raise ValueError(f"Missing required columns: {timestamp_col}")
        if close_col not in df.columns:
            raise ValueError(f"Missing required columns: {close_col}")
        if trend_window < 1:
            raise ValueError("trend_window must be at least 1.")
        if trend_threshold < 0:
            raise ValueError("trend_threshold must be non-negative.")

        labeled = df.copy()
        labeled[timestamp_col] = pd.to_datetime(labeled[timestamp_col])
        labeled = labeled.sort_values(timestamp_col).reset_index(drop=True)

        if volatility_col in labeled.columns:
            volatility_values = pd.to_numeric(labeled[volatility_col], errors="coerce")
        else:
            close_values = pd.to_numeric(labeled[close_col], errors="coerce")
            volatility_values = close_values.pct_change().rolling(14).std()
        labeled["volatility_regime"] = self._volatility_regimes(volatility_values)

        close_values = pd.to_numeric(labeled[close_col], errors="coerce")
        trend_return = close_values.pct_change(periods=trend_window)
        labeled["trend_return"] = trend_return
        labeled["trend_regime"] = self._trend_regimes(
            trend_return,
            threshold=trend_threshold,
        )
        return labeled

    def evaluate_by_regime(
        self,
        predictions_df: pd.DataFrame,
        regime_col: str,
        target_col: str = "y_true",
        prediction_col: str = "y_pred",
        probability_col: str = "y_proba",
    ) -> pd.DataFrame:
        required_columns = {regime_col, target_col, prediction_col}
        missing_columns = sorted(required_columns - set(predictions_df.columns))
        if missing_columns:
            raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

        rows = []
        for regime_name, group in predictions_df.groupby(regime_col, dropna=False):
            if group.empty:
                continue

            y_true = group[target_col]
            y_pred = group[prediction_col]
            y_proba = None
            if probability_col in group.columns:
                proba_values = pd.to_numeric(group[probability_col], errors="coerce")
                if proba_values.notna().any():
                    y_proba = proba_values

            metrics = self.evaluator.evaluate_predictions(y_true, y_pred, y_proba)
            confusion = metrics["confusion_matrix"]
            rows.append(
                {
                    "regime": str(regime_name),
                    "rows": int(len(group)),
                    "positive_rate": float(pd.to_numeric(y_true, errors="coerce").mean()),
                    "accuracy": metrics["accuracy"],
                    "precision": metrics["precision"],
                    "recall": metrics["recall"],
                    "f1": metrics["f1"],
                    "roc_auc": metrics["roc_auc"],
                    "false_positive_count": int(confusion[0][1]),
                    "false_negative_count": int(confusion[1][0]),
                }
            )
        return pd.DataFrame(rows).sort_values("regime").reset_index(drop=True)

    @staticmethod
    def _volatility_regimes(values: pd.Series) -> pd.Series:
        numeric_values = pd.to_numeric(values, errors="coerce")
        valid_values = numeric_values.dropna()
        if valid_values.empty:
            return pd.Series(["unknown_volatility"] * len(values), index=values.index)

        low_threshold = valid_values.quantile(1 / 3)
        high_threshold = valid_values.quantile(2 / 3)

        def label(value: Any) -> str:
            if pd.isna(value):
                return "unknown_volatility"
            if value <= low_threshold:
                return "low_volatility"
            if value >= high_threshold:
                return "high_volatility"
            return "medium_volatility"

        return numeric_values.map(label)

    @staticmethod
    def _trend_regimes(values: pd.Series, threshold: float) -> pd.Series:
        numeric_values = pd.to_numeric(values, errors="coerce")

        def label(value: Any) -> str:
            if pd.isna(value):
                return "unknown_trend"
            if value > threshold:
                return "uptrend"
            if value < -threshold:
                return "downtrend"
            return "sideways"

        return numeric_values.map(label)
