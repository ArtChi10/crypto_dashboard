from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib
import pandas as pd

from mlcore.evaluation.stability import PeriodStabilityAnalysisService

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


@dataclass(frozen=True)
class PeriodStabilityReportResult:
    table_path: Path
    plot_path: Path | None = None


class TargetDistributionReportService:
    TARGET_COLUMN = "target"

    def build(self, final_df_or_target: Any, path: str | Path) -> Path:
        target = self._target_series(final_df_or_target)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        counts = target.value_counts().to_dict()
        labels = ["0", "1"]
        values = [int(counts.get(0, 0)), int(counts.get(1, 0))]

        figure, axis = plt.subplots(figsize=(5, 3.2))
        axis.bar(labels, values, color=["#175cd3", "#17663a"])
        axis.set_title("Target distribution")
        axis.set_xlabel("target")
        axis.set_ylabel("count")
        axis.bar_label(axis.containers[0], padding=3)
        axis.margins(y=0.18)
        figure.tight_layout()
        figure.savefig(path, format="png", dpi=120)
        plt.close(figure)

        return path

    @classmethod
    def _target_series(cls, final_df_or_target: Any) -> pd.Series:
        if isinstance(final_df_or_target, pd.Series):
            return final_df_or_target

        if cls.TARGET_COLUMN not in final_df_or_target.columns:
            raise ValueError(f"Missing required columns: {cls.TARGET_COLUMN}")

        return final_df_or_target[cls.TARGET_COLUMN]


class MetricsComparisonReportService:
    METRIC_NAMES = ("accuracy", "precision", "recall", "f1", "roc_auc")
    MODEL_ORDER = ("baseline", "catboost")
    MODEL_COLORS = {
        "baseline": "#175cd3",
        "catboost": "#17663a",
    }

    def build(self, metrics_by_model: dict[str, dict[str, Any]], path: str | Path) -> Path:
        models = self._available_models(metrics_by_model)
        if not models:
            raise ValueError("metrics_by_model must contain at least one model.")

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        x_positions = list(range(len(self.METRIC_NAMES)))
        bar_width = 0.72 / len(models)
        max_value = 1.0

        figure, axis = plt.subplots(figsize=(7.2, 3.8))
        for model_index, model_name in enumerate(models):
            values, missing_flags = self._metric_values(metrics_by_model[model_name])
            max_value = max(max_value, *values)
            offset = (model_index - (len(models) - 1) / 2) * bar_width
            bars = axis.bar(
                [position + offset for position in x_positions],
                values,
                width=bar_width,
                label=model_name,
                color=self.MODEL_COLORS.get(model_name),
            )
            for bar, missing in zip(bars, missing_flags, strict=True):
                if missing:
                    axis.text(
                        bar.get_x() + bar.get_width() / 2,
                        0.03,
                        "N/A",
                        ha="center",
                        va="bottom",
                        fontsize=8,
                        rotation=90,
                    )

        axis.set_title("Model metrics comparison")
        axis.set_ylabel("score")
        axis.set_xticks(x_positions, self.METRIC_NAMES)
        axis.set_ylim(0, max(1.0, max_value * 1.15))
        axis.grid(axis="y", color="#d9dee7", linewidth=0.8, alpha=0.8)
        axis.legend()
        figure.tight_layout()
        figure.savefig(path, format="png", dpi=120)
        plt.close(figure)

        return path

    @classmethod
    def _available_models(cls, metrics_by_model: dict[str, dict[str, Any]]) -> list[str]:
        ordered_models = [
            model_name
            for model_name in cls.MODEL_ORDER
            if model_name in metrics_by_model and metrics_by_model[model_name] is not None
        ]
        extra_models = sorted(
            model_name
            for model_name, metrics in metrics_by_model.items()
            if model_name not in cls.MODEL_ORDER and metrics is not None
        )
        return ordered_models + extra_models

    @classmethod
    def _metric_values(cls, metrics: dict[str, Any]) -> tuple[list[float], list[bool]]:
        values = []
        missing_flags = []
        for metric_name in cls.METRIC_NAMES:
            value = metrics.get(metric_name)
            if value is None:
                values.append(0.0)
                missing_flags.append(True)
            else:
                values.append(float(value))
                missing_flags.append(False)
        return values, missing_flags


class PeriodStabilityReportService:
    PLOT_METRICS = ("accuracy", "f1", "roc_auc")

    def __init__(
        self,
        analysis_service: PeriodStabilityAnalysisService | None = None,
    ) -> None:
        self.analysis_service = analysis_service or PeriodStabilityAnalysisService()

    def build(
        self,
        predictions_by_model: dict[str, pd.DataFrame],
        path_csv: str | Path,
        path_png: str | Path | None = None,
        period: str = "D",
    ) -> PeriodStabilityReportResult:
        if not predictions_by_model:
            raise ValueError("predictions_by_model must contain at least one model.")

        stability_df = self._stability_frame(predictions_by_model, period=period)
        if stability_df.empty:
            raise ValueError("stability analysis produced no rows.")

        table_path = Path(path_csv)
        table_path.parent.mkdir(parents=True, exist_ok=True)
        stability_df.to_csv(table_path, index=False)

        plot_path = None
        if path_png is not None:
            plot_path = Path(path_png)
            plot_path.parent.mkdir(parents=True, exist_ok=True)
            self._build_plot(stability_df, plot_path)

        return PeriodStabilityReportResult(table_path=table_path, plot_path=plot_path)

    def _stability_frame(
        self,
        predictions_by_model: dict[str, pd.DataFrame],
        period: str,
    ) -> pd.DataFrame:
        frames = []
        for model_name, predictions in predictions_by_model.items():
            if predictions is None or predictions.empty:
                continue

            stability_df = self.analysis_service.analyze_predictions(
                predictions,
                period=period,
            )
            if stability_df.empty:
                continue

            stability_df.insert(0, "model_type", model_name)
            frames.append(stability_df)

        if not frames:
            return pd.DataFrame()

        return pd.concat(frames, ignore_index=True)

    def _build_plot(self, stability_df: pd.DataFrame, path: Path) -> None:
        figure, axis = plt.subplots(figsize=(8, 4.2))
        plotted = False
        for model_name, model_df in stability_df.groupby("model_type", sort=True):
            model_df = model_df.sort_values("period_start")
            x_values = pd.to_datetime(model_df["period_start"])
            for metric_name in self.PLOT_METRICS:
                metric_values = pd.to_numeric(model_df[metric_name], errors="coerce")
                metric_df = pd.DataFrame({"x": x_values, "y": metric_values}).dropna()
                if metric_df.empty:
                    continue
                axis.plot(
                    metric_df["x"],
                    metric_df["y"],
                    marker="o",
                    linewidth=1.8,
                    label=f"{model_name} {metric_name}",
                )
                plotted = True

        axis.set_title("Period stability")
        axis.set_xlabel("period")
        axis.set_ylabel("score")
        axis.set_ylim(0, 1.05)
        axis.grid(axis="y", color="#d9dee7", linewidth=0.8, alpha=0.8)
        if plotted:
            axis.legend(fontsize=8)
        else:
            axis.text(0.5, 0.5, "No plottable metrics", ha="center", va="center")
        figure.autofmt_xdate()
        figure.tight_layout()
        figure.savefig(path, format="png", dpi=120)
        plt.close(figure)


class FeatureImportanceReportService:
    def build(
        self,
        feature_names: list[str],
        importances: Any,
        path: str | Path,
        top_n: int = 20,
    ) -> Path:
        feature_importances = self._feature_importances(feature_names, importances, top_n=top_n)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        labels = [feature_name for feature_name, _ in feature_importances]
        values = [importance for _, importance in feature_importances]
        y_positions = list(range(len(labels)))

        figure_height = max(3.2, 0.34 * len(labels) + 1.2)
        figure, axis = plt.subplots(figsize=(7.2, figure_height))
        axis.barh(y_positions, values, color="#175cd3")
        axis.set_yticks(y_positions, labels)
        axis.invert_yaxis()
        axis.set_title("CatBoost feature importance")
        axis.set_xlabel("importance")
        axis.grid(axis="x", color="#d9dee7", linewidth=0.8, alpha=0.8)
        axis.margins(x=0.12)
        axis.bar_label(axis.containers[0], fmt="%.2f", padding=3)
        figure.tight_layout()
        figure.savefig(path, format="png", dpi=120)
        plt.close(figure)

        return path

    @staticmethod
    def _feature_importances(
        feature_names: list[str],
        importances: Any,
        top_n: int,
    ) -> list[tuple[str, float]]:
        values = [float(importance) for importance in list(importances)]
        if not feature_names or not values:
            raise ValueError("feature_names and importances must not be empty.")
        if len(feature_names) != len(values):
            raise ValueError("feature_names and importances must have the same length.")
        if top_n < 1:
            raise ValueError("top_n must be greater than or equal to 1.")

        feature_importances = sorted(
            zip(feature_names, values, strict=True),
            key=lambda item: item[1],
            reverse=True,
        )
        return feature_importances[:top_n]
