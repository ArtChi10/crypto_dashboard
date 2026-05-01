from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from mlcore.evaluation.evaluator import Evaluator


@dataclass(frozen=True)
class PeriodStabilityRow:
    period_start: pd.Timestamp
    period_end: pd.Timestamp
    rows: int
    positive_rate: float
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class PeriodStabilityAnalysisService:
    REQUIRED_COLUMNS = frozenset({"timestamp", "y_true", "y_pred"})
    PROBA_COLUMN = "y_proba"

    def __init__(self, evaluator: Evaluator | None = None) -> None:
        self.evaluator = evaluator or Evaluator()

    def analyze_predictions(
        self,
        df: pd.DataFrame,
        period: str = "D",
        min_rows: int = 1,
    ) -> pd.DataFrame:
        if min_rows < 1:
            raise ValueError("min_rows must be greater than or equal to 1.")

        working_df = self._prepare_dataframe(df)
        rows = []
        for _, period_df in working_df.groupby(
            pd.Grouper(key="timestamp", freq=period),
            sort=True,
        ):
            if len(period_df) < min_rows:
                continue
            rows.append(self._analyze_period(period_df).as_dict())

        result = pd.DataFrame(rows, columns=self._result_columns())
        if "roc_auc" in result.columns:
            result["roc_auc"] = result["roc_auc"].astype(object)
            result.loc[result["roc_auc"].isna(), "roc_auc"] = None
        return result

    def _analyze_period(self, period_df: pd.DataFrame) -> PeriodStabilityRow:
        y_proba = None
        if self.PROBA_COLUMN in period_df.columns:
            y_proba = period_df[self.PROBA_COLUMN]

        metrics = self.evaluator.evaluate_predictions(
            period_df["y_true"],
            period_df["y_pred"],
            y_proba,
        )

        return PeriodStabilityRow(
            period_start=period_df["timestamp"].min(),
            period_end=period_df["timestamp"].max(),
            rows=len(period_df),
            positive_rate=float(period_df["y_true"].mean()),
            accuracy=metrics["accuracy"],
            precision=metrics["precision"],
            recall=metrics["recall"],
            f1=metrics["f1"],
            roc_auc=metrics["roc_auc"],
        )

    @classmethod
    def _prepare_dataframe(cls, df: pd.DataFrame) -> pd.DataFrame:
        missing_columns = sorted(cls.REQUIRED_COLUMNS - set(df.columns))
        if missing_columns:
            missing = ", ".join(missing_columns)
            raise ValueError(f"Missing required columns: {missing}")

        working_df = df.copy()
        working_df["timestamp"] = pd.to_datetime(working_df["timestamp"])
        return working_df.sort_values("timestamp").reset_index(drop=True)

    @staticmethod
    def _result_columns() -> list[str]:
        return [
            "period_start",
            "period_end",
            "rows",
            "positive_rate",
            "accuracy",
            "precision",
            "recall",
            "f1",
            "roc_auc",
        ]
