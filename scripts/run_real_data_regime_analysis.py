from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _avoid_windows_platform_wmi_hang() -> None:
    if sys.platform != "win32":
        return
    try:
        import platform
    except ImportError:
        return

    if not hasattr(platform, "_wmi_query"):
        return

    def _raise_oserror(*args: Any, **kwargs: Any) -> None:
        raise OSError("Windows WMI probe disabled for reproducible script startup.")

    platform._wmi_query = _raise_oserror


_avoid_windows_platform_wmi_hang()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib  # noqa: E402
import pandas as pd  # noqa: E402

from mlcore.evaluation.regime import RegimeAnalysisService  # noqa: E402
from mlcore.evaluation.walk_forward import WalkForwardValidationService  # noqa: E402
from mlcore.features import FeatureBuilder  # noqa: E402
from mlcore.preprocessing import DataCleaner  # noqa: E402
from mlcore.targets import TargetBuilder  # noqa: E402
from mlcore.training.baseline_trainer import BaselineTrainer  # noqa: E402
from mlcore.training.catboost_trainer import CatBoostTrainer  # noqa: E402
from mlcore.training.dummy_trainer import DummyBaselineTrainer  # noqa: E402

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

METRIC_COLUMNS = (
    "rows",
    "positive_rate",
    "accuracy",
    "precision",
    "recall",
    "f1",
    "roc_auc",
    "false_positive_count",
    "false_negative_count",
)
DIAGNOSTIC_FEATURE_EXCLUSIONS = frozenset(
    {
        "volatility_regime",
        "trend_return",
        "trend_regime",
    }
)
TRAINER_FACTORIES = {
    "dummy": DummyBaselineTrainer,
    "baseline": BaselineTrainer,
    "catboost": lambda: CatBoostTrainer(
        iterations=20,
        depth=4,
        learning_rate=0.1,
        verbose=False,
    ),
}


def main() -> int:
    args = _parse_args()
    dataset_path = Path(args.dataset)
    manifest_path = Path(args.manifest)
    output_doc = Path(args.output_doc)
    output_dir = Path(args.output_dir)

    raw_dataset = _load_dataset(dataset_path)
    manifest = _load_manifest(manifest_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    final_dataset = _build_final_dataset(raw_dataset, horizon=args.target_horizon)
    regime_service = RegimeAnalysisService()
    labeled_dataset = regime_service.add_regime_labels(
        final_dataset,
        trend_window=args.trend_window,
        trend_threshold=args.trend_threshold,
    )
    predictions, fold_errors = _collect_walk_forward_predictions(
        labeled_dataset,
        trainer_name=args.trainer,
        train_window=args.train_window,
        test_window=args.test_window,
        step=args.step,
    )
    if predictions.empty:
        raise ValueError("No walk-forward predictions were created.")

    volatility_metrics = regime_service.evaluate_by_regime(
        predictions,
        regime_col="volatility_regime",
    )
    trend_metrics = regime_service.evaluate_by_regime(
        predictions,
        regime_col="trend_regime",
    )
    output_paths = _write_outputs(
        output_dir=output_dir,
        trainer_name=args.trainer,
        predictions=predictions,
        volatility_metrics=volatility_metrics,
        trend_metrics=trend_metrics,
    )
    plot_paths = _build_plots(
        output_dir=output_dir,
        volatility_metrics=volatility_metrics,
        trend_metrics=trend_metrics,
    )
    _write_report(
        output_doc=output_doc,
        manifest=manifest,
        final_dataset=final_dataset,
        predictions=predictions,
        volatility_metrics=volatility_metrics,
        trend_metrics=trend_metrics,
        fold_errors=fold_errors,
        output_paths=output_paths,
        plot_paths=plot_paths,
        args=args,
    )

    print(f"Saved regime analysis report: {output_doc}")
    print(f"Saved regime outputs: {output_dir}")
    print(f"Final rows: {len(final_dataset)}")
    print(f"Prediction rows: {len(predictions)}")
    print(f"Folds: {predictions['fold_id'].nunique()}")
    print(
        "Volatility regimes: "
        f"{', '.join(sorted(predictions['volatility_regime'].dropna().unique()))}"
    )
    print(f"Trend regimes: {', '.join(sorted(predictions['trend_regime'].dropna().unique()))}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run regime diagnostics on a frozen real Binance dataset.",
    )
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-doc", default="docs/real_data_regime_analysis.md")
    parser.add_argument("--output-dir", default="docs/assets/real_data_regime_analysis")
    parser.add_argument("--trainer", choices=sorted(TRAINER_FACTORIES), default="baseline")
    parser.add_argument("--target-horizon", type=int, default=3)
    parser.add_argument("--train-window", type=int, default=120)
    parser.add_argument("--test-window", type=int, default=24)
    parser.add_argument("--step", type=int, default=24)
    parser.add_argument("--trend-window", type=int, default=24)
    parser.add_argument("--trend-threshold", type=float, default=0.01)
    return parser.parse_args()


def _load_dataset(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Dataset not found: {path}")
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    raise ValueError("Dataset must be a .parquet or .csv file.")


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Manifest not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _build_final_dataset(raw_dataset: pd.DataFrame, horizon: int) -> pd.DataFrame:
    cleaned = DataCleaner().clean(raw_dataset)
    features = FeatureBuilder().build(cleaned)
    final = TargetBuilder().build(features, horizon=horizon)
    return final.sort_values("timestamp", kind="mergesort").reset_index(drop=True)


def _collect_walk_forward_predictions(
    final_dataset: pd.DataFrame,
    trainer_name: str,
    train_window: int,
    test_window: int,
    step: int,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    folds = WalkForwardValidationService().split(
        final_dataset,
        train_window=train_window,
        test_window=test_window,
        step=step,
        timestamp_col="timestamp",
    )
    prediction_frames = []
    fold_errors = []
    for fold in folds:
        trainer = TRAINER_FACTORIES[trainer_name]()
        try:
            feature_columns = _feature_columns(trainer, fold.train)
            if not feature_columns:
                raise ValueError(
                    "fold train data must contain at least one numeric feature column."
                )

            x_train = fold.train[feature_columns]
            y_train = fold.train["target"]
            x_test = fold.test[feature_columns]
            model = trainer.train(x_train, y_train)
            y_pred = model.predict(x_test)
            y_proba = _positive_class_scores(model, x_test)

            prediction_frame = fold.test.loc[
                :,
                [
                    "timestamp",
                    "close",
                    "target",
                    "volatility_regime",
                    "trend_return",
                    "trend_regime",
                ],
            ].copy()
            prediction_frame["fold_id"] = fold.fold_id
            prediction_frame["y_true"] = prediction_frame.pop("target")
            prediction_frame["y_pred"] = pd.Series(y_pred, index=prediction_frame.index)
            prediction_frame["y_proba"] = y_proba
            prediction_frame["is_correct"] = prediction_frame["y_true"].astype(
                int
            ) == prediction_frame["y_pred"].astype(int)
            prediction_frames.append(prediction_frame)
        except Exception as exc:
            fold_errors.append(
                {
                    "fold_id": fold.fold_id,
                    "train_start": fold.train_start,
                    "test_start": fold.test_start,
                    "error_message": str(exc),
                }
            )

    if not prediction_frames:
        return pd.DataFrame(), fold_errors
    return pd.concat(prediction_frames, ignore_index=True), fold_errors


def _feature_columns(trainer: Any, df: pd.DataFrame) -> list[str]:
    if hasattr(trainer, "get_feature_columns"):
        return [
            column
            for column in trainer.get_feature_columns(df)
            if column not in DIAGNOSTIC_FEATURE_EXCLUSIONS
        ]

    excluded_columns = {"target", "timestamp", "symbol"} | DIAGNOSTIC_FEATURE_EXCLUSIONS
    numeric_columns = df.select_dtypes(include="number").columns
    return [column for column in numeric_columns if column not in excluded_columns]


def _positive_class_scores(model: Any, x_test: pd.DataFrame) -> Any | None:
    if not hasattr(model, "predict_proba"):
        return None
    scores = model.predict_proba(x_test)
    score_frame = pd.DataFrame(scores)
    if score_frame.shape[1] < 2:
        return None
    return score_frame.iloc[:, 1].to_numpy()


def _write_outputs(
    output_dir: Path,
    trainer_name: str,
    predictions: pd.DataFrame,
    volatility_metrics: pd.DataFrame,
    trend_metrics: pd.DataFrame,
) -> dict[str, Path]:
    output_paths = {
        "predictions": output_dir / f"regime_predictions_{trainer_name}.csv",
        "volatility_metrics": output_dir / f"regime_metrics_by_volatility_{trainer_name}.csv",
        "trend_metrics": output_dir / f"regime_metrics_by_trend_{trainer_name}.csv",
    }
    predictions.to_csv(output_paths["predictions"], index=False)
    volatility_metrics.to_csv(output_paths["volatility_metrics"], index=False)
    trend_metrics.to_csv(output_paths["trend_metrics"], index=False)
    return output_paths


def _build_plots(
    output_dir: Path,
    volatility_metrics: pd.DataFrame,
    trend_metrics: pd.DataFrame,
) -> dict[str, Path]:
    plot_paths = {
        "f1_by_volatility": output_dir / "regime_f1_by_volatility.png",
        "f1_by_trend": output_dir / "regime_f1_by_trend.png",
        "error_counts": output_dir / "regime_error_counts.png",
    }
    _plot_f1_by_regime(
        volatility_metrics,
        title="F1 by volatility regime",
        path=plot_paths["f1_by_volatility"],
    )
    _plot_f1_by_regime(
        trend_metrics,
        title="F1 by trend regime",
        path=plot_paths["f1_by_trend"],
    )
    _plot_error_counts(
        volatility_metrics=volatility_metrics,
        trend_metrics=trend_metrics,
        path=plot_paths["error_counts"],
    )
    return plot_paths


def _plot_f1_by_regime(metrics: pd.DataFrame, title: str, path: Path) -> None:
    figure, axis = plt.subplots(figsize=(8.5, 4.2))
    if metrics.empty:
        axis.text(0.5, 0.5, "No regime metrics", ha="center", va="center")
    else:
        metric_frame = metrics.copy()
        metric_frame["f1"] = pd.to_numeric(metric_frame["f1"], errors="coerce").fillna(0)
        axis.bar(metric_frame["regime"], metric_frame["f1"], color="#175cd3", alpha=0.86)
    axis.set_title(title)
    axis.set_xlabel("regime")
    axis.set_ylabel("f1")
    axis.set_ylim(0, 1.05)
    axis.tick_params(axis="x", rotation=20)
    axis.grid(axis="y", color="#d9dee7", linewidth=0.8, alpha=0.8)
    _save_figure(figure, path)


def _plot_error_counts(
    volatility_metrics: pd.DataFrame,
    trend_metrics: pd.DataFrame,
    path: Path,
) -> None:
    figure, axes = plt.subplots(nrows=1, ncols=2, figsize=(11, 4.2), sharey=True)
    for axis, metrics, title in [
        (axes[0], volatility_metrics, "Volatility regimes"),
        (axes[1], trend_metrics, "Trend regimes"),
    ]:
        if metrics.empty:
            axis.text(0.5, 0.5, "No errors", ha="center", va="center")
            continue
        metric_frame = metrics.copy()
        false_positive = pd.to_numeric(
            metric_frame["false_positive_count"],
            errors="coerce",
        ).fillna(0)
        false_negative = pd.to_numeric(
            metric_frame["false_negative_count"],
            errors="coerce",
        ).fillna(0)
        axis.bar(metric_frame["regime"], false_positive, label="false positive", color="#d92d20")
        axis.bar(
            metric_frame["regime"],
            false_negative,
            bottom=false_positive,
            label="false negative",
            color="#f79009",
        )
        axis.set_title(title)
        axis.set_xlabel("regime")
        axis.tick_params(axis="x", rotation=20)
        axis.grid(axis="y", color="#d9dee7", linewidth=0.8, alpha=0.8)
    axes[0].set_ylabel("error count")
    axes[1].legend()
    _save_figure(figure, path)


def _save_figure(figure: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(path, format="png", dpi=120)
    plt.close(figure)


def _write_report(
    output_doc: Path,
    manifest: dict[str, Any],
    final_dataset: pd.DataFrame,
    predictions: pd.DataFrame,
    volatility_metrics: pd.DataFrame,
    trend_metrics: pd.DataFrame,
    fold_errors: list[dict[str, Any]],
    output_paths: dict[str, Path],
    plot_paths: dict[str, Path],
    args: argparse.Namespace,
) -> None:
    output_doc.parent.mkdir(parents=True, exist_ok=True)
    volatility_metrics_path = _relative_markdown_path(
        output_paths["volatility_metrics"],
        output_doc,
    )
    trend_metrics_path = _relative_markdown_path(
        output_paths["trend_metrics"],
        output_doc,
    )
    predictions_path = _relative_markdown_path(output_paths["predictions"], output_doc)
    f1_by_volatility_path = _relative_markdown_path(
        plot_paths["f1_by_volatility"],
        output_doc,
    )
    f1_by_trend_path = _relative_markdown_path(plot_paths["f1_by_trend"], output_doc)
    error_counts_path = _relative_markdown_path(plot_paths["error_counts"], output_doc)
    markdown = [
        "# Real Data Regime Analysis",
        "",
        "## Purpose",
        "",
        "This report checks where a walk-forward directional classifier performs",
        "better or worse across simple volatility and trend regimes. It is",
        "diagnostic error analysis, not a market strategy or trading claim.",
        "",
        "## Dataset",
        "",
        _manifest_table(manifest),
        "",
        f"Final feature/target rows after pipeline preparation: `{len(final_dataset)}`.",
        f"Walk-forward prediction rows used for regime analysis: `{len(predictions)}`.",
        "",
        "## Walk-Forward Setup",
        "",
        _rows_to_markdown_table(
            ["parameter", "value"],
            [
                ("trainer", args.trainer),
                ("target_horizon", args.target_horizon),
                ("train_window", args.train_window),
                ("test_window", args.test_window),
                ("step", args.step),
                ("folds_with_predictions", predictions["fold_id"].nunique()),
                ("fold_errors", len(fold_errors)),
                ("random_shuffle", "no"),
            ],
        ),
        "",
        "## Regime Definitions",
        "",
        "- Volatility regimes use `volatility_14` when available and split valid",
        "  values into low/medium/high buckets by 33% and 66% quantiles.",
        f"- Trend regimes use `close.pct_change({args.trend_window})`.",
        f"- `trend_return > {args.trend_threshold}` is `uptrend`.",
        f"- `trend_return < -{args.trend_threshold}` is `downtrend`.",
        "- Values between the thresholds are `sideways`; missing values are labeled",
        "  as unknown regimes.",
        "",
        "## Metrics By Volatility Regime",
        "",
        f"CSV output: [`{output_paths['volatility_metrics'].name}`]({volatility_metrics_path})",
        "",
        f"![F1 by volatility regime]({f1_by_volatility_path})",
        "",
        _dataframe_to_markdown(_format_metrics(volatility_metrics)),
        "",
        "## Metrics By Trend Regime",
        "",
        f"CSV output: [`{output_paths['trend_metrics'].name}`]({trend_metrics_path})",
        "",
        f"![F1 by trend regime]({f1_by_trend_path})",
        "",
        _dataframe_to_markdown(_format_metrics(trend_metrics)),
        "",
        "## Error Analysis",
        "",
        f"Predictions CSV: [`{output_paths['predictions'].name}`]({predictions_path})",
        "",
        f"![Error counts by regime]({error_counts_path})",
        "",
        "False positives and false negatives are counted inside each regime bucket.",
        "Small regime buckets can make these counts noisy.",
        "",
        "## Interpretation",
        "",
        _interpretation(volatility_metrics, trend_metrics),
        "",
        "## Limitations",
        "",
        "- Regime labels are simple diagnostics, not market-state truth.",
        "- Trend thresholds are heuristic and should be varied in future runs.",
        "- The smoke dataset is short, so some regime buckets have low row counts.",
        "- Metrics by regime do not include fees, slippage, execution constraints,",
        "  or position sizing.",
        "- Results do not imply profitability or deployable market edge.",
        "",
        "## Reproducibility",
        "",
        "Regenerate this report with:",
        "",
        "```powershell",
        _reproducibility_command(args),
        "```",
        "",
    ]
    output_doc.write_text("\n".join(markdown), encoding="utf-8")


def _manifest_table(manifest: dict[str, Any]) -> str:
    rows = [
        ("source", manifest.get("source")),
        ("symbol", manifest.get("symbol")),
        ("interval", manifest.get("interval")),
        ("start_date", manifest.get("start_date")),
        ("end_date", manifest.get("end_date")),
        ("file_path", manifest.get("file_path")),
        ("file_sha256", manifest.get("file_sha256")),
        ("rows", manifest.get("rows")),
        ("timestamp_min", manifest.get("timestamp_min")),
        ("timestamp_max", manifest.get("timestamp_max")),
    ]
    return _rows_to_markdown_table(["field", "value"], rows)


def _format_metrics(metrics: pd.DataFrame) -> pd.DataFrame:
    formatted = metrics.copy()
    for column in METRIC_COLUMNS:
        if column in formatted.columns:
            if column in {"rows", "false_positive_count", "false_negative_count"}:
                formatted[column] = formatted[column].map(_format_int)
            else:
                formatted[column] = formatted[column].map(_format_float)
    return formatted


def _interpretation(volatility_metrics: pd.DataFrame, trend_metrics: pd.DataFrame) -> str:
    lines = []
    best_volatility = _best_regime(volatility_metrics)
    best_trend = _best_regime(trend_metrics)
    if best_volatility:
        lines.append(
            f"The strongest volatility bucket by F1 in this smoke run is "
            f"`{best_volatility[0]}` with F1 `{_format_float(best_volatility[1])}`."
        )
    if best_trend:
        lines.append(
            f"The strongest trend bucket by F1 in this smoke run is "
            f"`{best_trend[0]}` with F1 `{_format_float(best_trend[1])}`."
        )
    lines.append(
        "These comparisons are diagnostic and should be re-run on longer frozen periods "
        "before drawing stronger conclusions."
    )
    return "\n\n".join(lines)


def _best_regime(metrics: pd.DataFrame) -> tuple[str, float] | None:
    if metrics.empty or "f1" not in metrics.columns:
        return None
    f1_values = pd.to_numeric(metrics["f1"], errors="coerce")
    if f1_values.dropna().empty:
        return None
    row = metrics.loc[f1_values.idxmax()]
    return str(row["regime"]), float(row["f1"])


def _dataframe_to_markdown(df: pd.DataFrame) -> str:
    formatted = df.copy()
    for column in formatted.columns:
        formatted[column] = formatted[column].map(_format_value)
    headers = list(formatted.columns)
    rows = [tuple(row) for row in formatted.itertuples(index=False, name=None)]
    return _rows_to_markdown_table(headers, rows)


def _rows_to_markdown_table(headers: list[str], rows) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_format_value(value) for value in row) + " |")
    return "\n".join(lines)


def _format_float(value: Any) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):.4f}"


def _format_int(value: Any) -> str:
    if value is None or pd.isna(value):
        return "-"
    return str(int(value))


def _format_value(value: Any) -> str:
    if value is None or pd.isna(value):
        return "-"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _relative_markdown_path(path: Path, output_doc: Path) -> str:
    return path.resolve().relative_to(output_doc.parent.resolve()).as_posix()


def _reproducibility_command(args: argparse.Namespace) -> str:
    return (
        ".crypto\\Scripts\\python.exe scripts\\run_real_data_regime_analysis.py "
        f"--dataset {args.dataset} "
        f"--manifest {args.manifest} "
        f"--output-doc {args.output_doc} "
        f"--output-dir {args.output_dir} "
        f"--trainer {args.trainer} "
        f"--target-horizon {args.target_horizon} "
        f"--train-window {args.train_window} "
        f"--test-window {args.test_window} "
        f"--step {args.step} "
        f"--trend-window {args.trend_window} "
        f"--trend-threshold {args.trend_threshold}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
