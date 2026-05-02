from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral
from typing import Any

import pandas as pd

from mlcore.evaluation.evaluator import Evaluator


@dataclass(frozen=True)
class WalkForwardFold:
    fold_id: int
    train: pd.DataFrame
    test: pd.DataFrame
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


class WalkForwardValidationService:
    def split(
        self,
        df: pd.DataFrame,
        train_window: int,
        test_window: int,
        step: int | None = None,
        timestamp_col: str = "timestamp",
    ) -> list[WalkForwardFold]:
        train_window = self._validate_positive_int("train_window", train_window)
        test_window = self._validate_positive_int("test_window", test_window)
        if step is None:
            step = test_window
        step = self._validate_positive_int("step", step)

        sorted_df = self._sorted_dataframe(df, timestamp_col=timestamp_col)
        if len(sorted_df) < train_window + test_window:
            raise ValueError("dataset must be large enough for at least one fold.")

        folds = []
        fold_id = 1
        start = 0
        while start + train_window + test_window <= len(sorted_df):
            train_start_index = start
            train_end_index = start + train_window
            test_end_index = train_end_index + test_window

            train_df = sorted_df.iloc[train_start_index:train_end_index].copy()
            test_df = sorted_df.iloc[train_end_index:test_end_index].copy()
            folds.append(
                WalkForwardFold(
                    fold_id=fold_id,
                    train=train_df.reset_index(drop=True),
                    test=test_df.reset_index(drop=True),
                    train_start=train_df[timestamp_col].iloc[0],
                    train_end=train_df[timestamp_col].iloc[-1],
                    test_start=test_df[timestamp_col].iloc[0],
                    test_end=test_df[timestamp_col].iloc[-1],
                )
            )
            fold_id += 1
            start += step

        return folds

    @staticmethod
    def _validate_positive_int(name: str, value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, Integral):
            raise ValueError(f"{name} must be a positive integer.")
        normalized = int(value)
        if normalized < 1:
            raise ValueError(f"{name} must be a positive integer.")
        return normalized

    @staticmethod
    def _sorted_dataframe(df: pd.DataFrame, timestamp_col: str) -> pd.DataFrame:
        if timestamp_col not in df.columns:
            raise ValueError(f"Missing required columns: {timestamp_col}")

        sorted_df = df.copy()
        sorted_df[timestamp_col] = pd.to_datetime(sorted_df[timestamp_col])
        return sorted_df.sort_values(timestamp_col).reset_index(drop=True)


class WalkForwardEvaluationService:
    EXCLUDED_FEATURE_COLUMNS = frozenset({"target", "timestamp", "symbol"})
    METRIC_COLUMNS = ("accuracy", "precision", "recall", "f1", "roc_auc")

    def __init__(
        self,
        validation_service: WalkForwardValidationService | None = None,
        evaluator: Evaluator | None = None,
    ) -> None:
        self.validation_service = validation_service or WalkForwardValidationService()
        self.evaluator = evaluator or Evaluator()

    def evaluate(
        self,
        trainer: Any,
        df: pd.DataFrame,
        train_window: int,
        test_window: int,
        step: int | None = None,
        target_col: str = "target",
        timestamp_col: str = "timestamp",
        raise_on_error: bool = False,
    ) -> pd.DataFrame:
        self._validate_target_column(df, target_col=target_col)
        folds = self.validation_service.split(
            df,
            train_window=train_window,
            test_window=test_window,
            step=step,
            timestamp_col=timestamp_col,
        )

        rows = []
        for fold in folds:
            base_row = self._base_row(fold)
            try:
                metrics = self._evaluate_fold(
                    trainer=trainer,
                    fold=fold,
                    target_col=target_col,
                    timestamp_col=timestamp_col,
                )
                rows.append({**base_row, **metrics, "error_message": None})
            except Exception as exc:
                if raise_on_error:
                    raise
                rows.append({**base_row, **self._empty_metrics(), "error_message": str(exc)})

        return pd.DataFrame(rows)

    def _evaluate_fold(
        self,
        trainer: Any,
        fold: WalkForwardFold,
        target_col: str,
        timestamp_col: str,
    ) -> dict[str, Any]:
        feature_columns = self._feature_columns(
            trainer=trainer,
            df=fold.train,
            target_col=target_col,
            timestamp_col=timestamp_col,
        )
        if not feature_columns:
            raise ValueError("fold train data must contain at least one numeric feature column.")

        x_train = fold.train[feature_columns]
        y_train = fold.train[target_col]
        x_test = fold.test[feature_columns]
        y_test = fold.test[target_col]

        model = trainer.train(x_train, y_train)
        y_pred = model.predict(x_test)
        y_proba = None
        if hasattr(model, "predict_proba"):
            y_proba = model.predict_proba(x_test)

        metrics = self.evaluator.evaluate_predictions(y_test, y_pred, y_proba)
        return {column: metrics[column] for column in self.METRIC_COLUMNS}

    @classmethod
    def _feature_columns(
        cls,
        trainer: Any,
        df: pd.DataFrame,
        target_col: str,
        timestamp_col: str,
    ) -> list[str]:
        if hasattr(trainer, "get_feature_columns"):
            return list(trainer.get_feature_columns(df))

        excluded_columns = cls.EXCLUDED_FEATURE_COLUMNS | {target_col, timestamp_col}
        numeric_columns = df.select_dtypes(include="number").columns
        return [column for column in numeric_columns if column not in excluded_columns]

    @staticmethod
    def _base_row(fold: WalkForwardFold) -> dict[str, Any]:
        return {
            "fold_id": fold.fold_id,
            "train_start": fold.train_start,
            "train_end": fold.train_end,
            "test_start": fold.test_start,
            "test_end": fold.test_end,
            "train_rows": len(fold.train),
            "test_rows": len(fold.test),
        }

    @classmethod
    def _empty_metrics(cls) -> dict[str, None]:
        return {column: None for column in cls.METRIC_COLUMNS}

    @staticmethod
    def _validate_target_column(df: pd.DataFrame, target_col: str) -> None:
        if target_col not in df.columns:
            raise ValueError(f"Missing required columns: {target_col}")
