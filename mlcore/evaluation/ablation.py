from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

import pandas as pd

from mlcore.evaluation.evaluator import Evaluator


class FeatureAblationService:
    DEFAULT_FEATURE_GROUPS: dict[str, tuple[str, ...]] = {
        "price_raw": ("open", "high", "low", "close"),
        "returns": ("return_1", "return_3", "return_6", "return_12"),
        "moving_average": ("ma_7", "ma_14", "ema_7", "ema_30"),
        "volatility": ("volatility_7", "volatility_14"),
        "volume": ("volume", "volume_change", "volume_ma_7"),
        "candle": ("candle_body", "candle_range"),
    }
    EXCLUDED_FEATURE_COLUMNS = frozenset({"target", "timestamp", "symbol"})
    METRIC_COLUMNS = ("accuracy", "precision", "recall", "f1", "roc_auc")
    RESULT_COLUMNS = (
        "experiment",
        "included_feature_count",
        "excluded_group",
        "accuracy",
        "precision",
        "recall",
        "f1",
        "roc_auc",
        "error_message",
    )

    def __init__(self, evaluator: Evaluator | None = None) -> None:
        self.evaluator = evaluator or Evaluator()

    def evaluate_groups(
        self,
        trainer_factory: Callable[[], Any],
        train_df: pd.DataFrame,
        test_df: pd.DataFrame,
        target_col: str = "target",
        feature_groups: Mapping[str, Sequence[str]] | None = None,
        mode: str = "drop_groups",
        raise_on_error: bool = False,
    ) -> pd.DataFrame:
        self._validate_inputs(
            trainer_factory=trainer_factory,
            train_df=train_df,
            test_df=test_df,
            target_col=target_col,
            mode=mode,
        )
        groups = self._normalize_feature_groups(feature_groups)
        all_features = self._all_feature_columns(train_df, test_df, target_col=target_col)

        rows = []
        for experiment, selected_features, excluded_group, setup_error in self._experiment_specs(
            mode=mode,
            groups=groups,
            all_features=all_features,
        ):
            if setup_error is not None:
                rows.append(
                    self._error_row(
                        experiment=experiment,
                        included_feature_count=0,
                        excluded_group=excluded_group,
                        error_message=setup_error,
                    )
                )
                continue

            try:
                metrics = self._evaluate_experiment(
                    trainer_factory=trainer_factory,
                    train_df=train_df,
                    test_df=test_df,
                    target_col=target_col,
                    feature_columns=selected_features,
                )
                rows.append(
                    self._success_row(
                        experiment=experiment,
                        included_feature_count=len(selected_features),
                        excluded_group=excluded_group,
                        metrics=metrics,
                    )
                )
            except Exception as exc:
                if raise_on_error:
                    raise
                rows.append(
                    self._error_row(
                        experiment=experiment,
                        included_feature_count=len(selected_features),
                        excluded_group=excluded_group,
                        error_message=str(exc),
                    )
                )

        return pd.DataFrame(rows, columns=self.RESULT_COLUMNS)

    def _evaluate_experiment(
        self,
        trainer_factory: Callable[[], Any],
        train_df: pd.DataFrame,
        test_df: pd.DataFrame,
        target_col: str,
        feature_columns: list[str],
    ) -> dict[str, Any]:
        if not feature_columns:
            raise ValueError("experiment must contain at least one feature column.")

        trainer = trainer_factory()
        model = trainer.train(train_df[feature_columns], train_df[target_col])
        y_pred = model.predict(test_df[feature_columns])
        y_proba = None
        if hasattr(model, "predict_proba"):
            y_proba = model.predict_proba(test_df[feature_columns])

        metrics = self.evaluator.evaluate_predictions(test_df[target_col], y_pred, y_proba)
        return {column: metrics[column] for column in self.METRIC_COLUMNS}

    @classmethod
    def _experiment_specs(
        cls,
        mode: str,
        groups: dict[str, tuple[str, ...]],
        all_features: list[str],
    ) -> list[tuple[str, list[str], str | None, str | None]]:
        if mode == "only_groups":
            return [
                cls._only_group_spec(
                    group_name=group_name,
                    group_columns=cls._available_group_columns(group_columns, all_features),
                )
                for group_name, group_columns in groups.items()
            ]

        specs = [
            (
                "all_features",
                all_features,
                None,
                None if all_features else "No numeric feature columns are available.",
            )
        ]
        specs.extend(
            cls._drop_group_spec(
                group_name=group_name,
                group_columns=cls._available_group_columns(group_columns, all_features),
                all_features=all_features,
            )
            for group_name, group_columns in groups.items()
        )
        return specs

    @staticmethod
    def _only_group_spec(
        group_name: str,
        group_columns: list[str],
    ) -> tuple[str, list[str], str | None, str | None]:
        if not group_columns:
            return (
                group_name,
                [],
                None,
                f"No available feature columns for group: {group_name}.",
            )
        return (group_name, group_columns, None, None)

    @staticmethod
    def _drop_group_spec(
        group_name: str,
        group_columns: list[str],
        all_features: list[str],
    ) -> tuple[str, list[str], str | None, str | None]:
        experiment = f"without_{group_name}"
        if not group_columns:
            return (
                experiment,
                [],
                group_name,
                f"No available feature columns for group: {group_name}.",
            )

        selected_features = [column for column in all_features if column not in group_columns]
        if not selected_features:
            return (
                experiment,
                [],
                group_name,
                f"Experiment {experiment} has no included feature columns.",
            )
        return (experiment, selected_features, group_name, None)

    @classmethod
    def _all_feature_columns(
        cls,
        train_df: pd.DataFrame,
        test_df: pd.DataFrame,
        target_col: str,
    ) -> list[str]:
        excluded_columns = cls.EXCLUDED_FEATURE_COLUMNS | {target_col}
        train_numeric = train_df.select_dtypes(include="number").columns
        test_columns = set(test_df.columns)
        return [
            column
            for column in train_numeric
            if column in test_columns and column not in excluded_columns
        ]

    @staticmethod
    def _available_group_columns(
        group_columns: Sequence[str],
        all_features: list[str],
    ) -> list[str]:
        all_feature_set = set(all_features)
        return [column for column in group_columns if column in all_feature_set]

    @classmethod
    def _success_row(
        cls,
        experiment: str,
        included_feature_count: int,
        excluded_group: str | None,
        metrics: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "experiment": experiment,
            "included_feature_count": included_feature_count,
            "excluded_group": excluded_group,
            **{column: metrics[column] for column in cls.METRIC_COLUMNS},
            "error_message": None,
        }

    @classmethod
    def _error_row(
        cls,
        experiment: str,
        included_feature_count: int,
        excluded_group: str | None,
        error_message: str,
    ) -> dict[str, Any]:
        return {
            "experiment": experiment,
            "included_feature_count": included_feature_count,
            "excluded_group": excluded_group,
            **cls._empty_metrics(),
            "error_message": error_message,
        }

    @classmethod
    def _empty_metrics(cls) -> dict[str, None]:
        return {column: None for column in cls.METRIC_COLUMNS}

    @classmethod
    def _normalize_feature_groups(
        cls,
        feature_groups: Mapping[str, Sequence[str]] | None,
    ) -> dict[str, tuple[str, ...]]:
        groups = feature_groups or cls.DEFAULT_FEATURE_GROUPS
        return {group_name: tuple(columns) for group_name, columns in groups.items()}

    @staticmethod
    def _validate_inputs(
        trainer_factory: Callable[[], Any],
        train_df: pd.DataFrame,
        test_df: pd.DataFrame,
        target_col: str,
        mode: str,
    ) -> None:
        if not callable(trainer_factory):
            raise ValueError("trainer_factory must be callable.")
        if target_col not in train_df.columns or target_col not in test_df.columns:
            raise ValueError(f"Missing required columns: {target_col}")
        if train_df.empty:
            raise ValueError("train_df must not be empty.")
        if test_df.empty:
            raise ValueError("test_df must not be empty.")
        if mode not in {"drop_groups", "only_groups"}:
            raise ValueError("mode must be either 'drop_groups' or 'only_groups'.")
