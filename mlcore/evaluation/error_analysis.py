from __future__ import annotations

from typing import Any

import pandas as pd


class PredictionErrorAnalysisService:
    ERROR_TYPES = {
        (0, 0): "true_negative",
        (0, 1): "false_positive",
        (1, 0): "false_negative",
        (1, 1): "true_positive",
    }

    def add_error_labels(
        self,
        predictions_df: pd.DataFrame,
        target_col: str = "y_true",
        prediction_col: str = "y_pred",
        probability_col: str = "y_proba",
    ) -> pd.DataFrame:
        self._validate_columns(predictions_df, [target_col, prediction_col])

        labeled = predictions_df.copy()
        y_true = pd.to_numeric(labeled[target_col], errors="coerce")
        y_pred = pd.to_numeric(labeled[prediction_col], errors="coerce")

        labeled["error_type"] = [
            self.ERROR_TYPES.get((int(true_value), int(pred_value)), "unknown")
            if not pd.isna(true_value) and not pd.isna(pred_value)
            else "unknown"
            for true_value, pred_value in zip(y_true, y_pred, strict=False)
        ]
        labeled["is_error"] = labeled["error_type"].isin({"false_positive", "false_negative"})
        labeled["confidence"] = self._confidence(
            labeled,
            y_pred=y_pred,
            probability_col=probability_col,
        )
        return labeled

    def summarize_errors(self, predictions_df: pd.DataFrame) -> dict[str, Any]:
        labeled = self._ensure_error_labels(predictions_df)
        total_rows = int(len(labeled))
        error_count = int(labeled["is_error"].sum())
        correct_count = total_rows - error_count
        true_positive = self._count_type(labeled, "true_positive")
        true_negative = self._count_type(labeled, "true_negative")
        false_positive = self._count_type(labeled, "false_positive")
        false_negative = self._count_type(labeled, "false_negative")

        actual_negative = true_negative + false_positive
        actual_positive = true_positive + false_negative
        confidence = pd.to_numeric(labeled["confidence"], errors="coerce")

        return {
            "total_rows": total_rows,
            "correct_count": correct_count,
            "error_count": error_count,
            "error_rate": self._safe_rate(error_count, total_rows),
            "true_positive_count": true_positive,
            "true_negative_count": true_negative,
            "false_positive_count": false_positive,
            "false_negative_count": false_negative,
            "false_positive_rate": self._safe_rate(false_positive, actual_negative),
            "false_negative_rate": self._safe_rate(false_negative, actual_positive),
            "avg_confidence_correct": self._mean_or_none(confidence[~labeled["is_error"]]),
            "avg_confidence_wrong": self._mean_or_none(confidence[labeled["is_error"]]),
        }

    def high_confidence_errors(
        self,
        predictions_df: pd.DataFrame,
        top_n: int = 10,
    ) -> pd.DataFrame:
        if top_n < 1:
            raise ValueError("top_n must be at least 1.")
        labeled = self._ensure_error_labels(predictions_df)
        errors = labeled[labeled["is_error"]].copy()
        confidence = pd.to_numeric(errors["confidence"], errors="coerce")
        errors = errors.assign(confidence=confidence).dropna(subset=["confidence"])
        return errors.sort_values("confidence", ascending=False).head(top_n).reset_index(drop=True)

    def summarize_by_probability_bins(
        self,
        predictions_df: pd.DataFrame,
        bins: int = 5,
    ) -> pd.DataFrame:
        if bins < 1:
            raise ValueError("bins must be at least 1.")

        labeled = self._ensure_error_labels(predictions_df)
        confidence = pd.to_numeric(labeled["confidence"], errors="coerce")
        if confidence.dropna().empty:
            return pd.DataFrame(
                columns=["confidence_bin", "rows", "correct_count", "error_count", "error_rate"]
            )

        bin_edges = [0.5 + index * (0.5 / bins) for index in range(bins + 1)]
        bin_edges[-1] = 1.0000001
        labels = [
            f"{bin_edges[index]:.1f}-{min(bin_edges[index + 1], 1.0):.1f}" for index in range(bins)
        ]
        binned = labeled.copy()
        binned["confidence"] = confidence
        binned = binned.dropna(subset=["confidence"])
        binned["confidence_bin"] = pd.cut(
            binned["confidence"],
            bins=bin_edges,
            labels=labels,
            include_lowest=True,
            right=False,
        )

        rows = []
        for bin_label, group in binned.groupby("confidence_bin", observed=False):
            if group.empty:
                continue
            error_count = int(group["is_error"].sum())
            row_count = int(len(group))
            rows.append(
                {
                    "confidence_bin": str(bin_label),
                    "rows": row_count,
                    "correct_count": row_count - error_count,
                    "error_count": error_count,
                    "error_rate": self._safe_rate(error_count, row_count),
                }
            )
        return pd.DataFrame(rows)

    @staticmethod
    def _validate_columns(df: pd.DataFrame, columns: list[str]) -> None:
        missing_columns = sorted(set(columns) - set(df.columns))
        if missing_columns:
            raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

    def _ensure_error_labels(self, predictions_df: pd.DataFrame) -> pd.DataFrame:
        required_columns = {"error_type", "is_error", "confidence"}
        if required_columns.issubset(predictions_df.columns):
            return predictions_df.copy()
        return self.add_error_labels(predictions_df)

    @staticmethod
    def _confidence(
        labeled: pd.DataFrame,
        y_pred: pd.Series,
        probability_col: str,
    ) -> pd.Series:
        if probability_col not in labeled.columns:
            return pd.Series([None] * len(labeled), index=labeled.index, dtype="object")

        y_proba = pd.to_numeric(labeled[probability_col], errors="coerce")
        return pd.Series(
            [
                probability
                if pred_value == 1
                else 1 - probability
                if pred_value == 0 and not pd.isna(probability)
                else None
                for pred_value, probability in zip(y_pred, y_proba, strict=False)
            ],
            index=labeled.index,
        )

    @staticmethod
    def _count_type(labeled: pd.DataFrame, error_type: str) -> int:
        return int((labeled["error_type"] == error_type).sum())

    @staticmethod
    def _safe_rate(numerator: int, denominator: int) -> float | None:
        if denominator == 0:
            return None
        return float(numerator / denominator)

    @staticmethod
    def _mean_or_none(values: pd.Series) -> float | None:
        clean_values = pd.to_numeric(values, errors="coerce").dropna()
        if clean_values.empty:
            return None
        return float(clean_values.mean())
