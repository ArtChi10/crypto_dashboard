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

from mlcore.evaluation.error_analysis import PredictionErrorAnalysisService  # noqa: E402
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
SUMMARY_COLUMNS = (
    "total_rows",
    "correct_count",
    "error_count",
    "error_rate",
    "true_positive_count",
    "true_negative_count",
    "false_positive_count",
    "false_negative_count",
    "false_positive_rate",
    "false_negative_rate",
    "avg_confidence_correct",
    "avg_confidence_wrong",
)
PREDICTION_EXPORT_COLUMNS = (
    "timestamp",
    "fold_id",
    "close",
    "y_true",
    "y_pred",
    "y_proba",
    "confidence",
    "error_type",
    "is_error",
    "volatility_regime",
    "trend_return",
    "trend_regime",
)


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

    error_service = PredictionErrorAnalysisService()
    error_predictions = error_service.add_error_labels(predictions)
    summary = pd.DataFrame([error_service.summarize_errors(error_predictions)])
    high_confidence_errors = error_service.high_confidence_errors(
        error_predictions,
        top_n=args.top_n,
    )
    probability_bins = error_service.summarize_by_probability_bins(error_predictions)
    error_by_volatility = _error_rate_by_group(error_predictions, "volatility_regime")
    error_by_trend = _error_rate_by_group(error_predictions, "trend_regime")

    output_paths = _write_outputs(
        output_dir=output_dir,
        trainer_name=args.trainer,
        error_predictions=error_predictions,
        summary=summary,
        high_confidence_errors=high_confidence_errors,
        probability_bins=probability_bins,
    )
    plot_paths = _build_plots(
        output_dir=output_dir,
        error_predictions=error_predictions,
        probability_bins=probability_bins,
        error_by_volatility=error_by_volatility,
        error_by_trend=error_by_trend,
    )
    _write_report(
        output_doc=output_doc,
        manifest=manifest,
        final_dataset=final_dataset,
        error_predictions=error_predictions,
        summary=summary,
        high_confidence_errors=high_confidence_errors,
        probability_bins=probability_bins,
        error_by_volatility=error_by_volatility,
        error_by_trend=error_by_trend,
        fold_errors=fold_errors,
        output_paths=output_paths,
        plot_paths=plot_paths,
        args=args,
    )

    summary_row = summary.iloc[0]
    print(f"Saved error analysis report: {output_doc}")
    print(f"Saved error outputs: {output_dir}")
    print(f"Final rows: {len(final_dataset)}")
    print(f"Prediction rows: {len(error_predictions)}")
    print(f"Folds: {error_predictions['fold_id'].nunique()}")
    print(f"Error rate: {_format_float(summary_row['error_rate'])}")
    print(f"False positives: {summary_row['false_positive_count']}")
    print(f"False negatives: {summary_row['false_negative_count']}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run error diagnostics on walk-forward predictions.",
    )
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-doc", default="docs/real_data_error_analysis.md")
    parser.add_argument("--output-dir", default="docs/assets/real_data_error_analysis")
    parser.add_argument("--trainer", choices=sorted(TRAINER_FACTORIES), default="baseline")
    parser.add_argument("--target-horizon", type=int, default=3)
    parser.add_argument("--train-window", type=int, default=120)
    parser.add_argument("--test-window", type=int, default=24)
    parser.add_argument("--step", type=int, default=24)
    parser.add_argument("--trend-window", type=int, default=24)
    parser.add_argument("--trend-threshold", type=float, default=0.01)
    parser.add_argument("--top-n", type=int, default=10)
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


def _error_rate_by_group(predictions: pd.DataFrame, group_col: str) -> pd.DataFrame:
    rows = []
    for group_name, group in predictions.groupby(group_col, dropna=False):
        row_count = int(len(group))
        error_count = int(group["is_error"].sum())
        rows.append(
            {
                "group": str(group_name),
                "rows": row_count,
                "correct_count": row_count - error_count,
                "error_count": error_count,
                "error_rate": float(error_count / row_count) if row_count else None,
                "false_positive_count": int((group["error_type"] == "false_positive").sum()),
                "false_negative_count": int((group["error_type"] == "false_negative").sum()),
            }
        )
    return pd.DataFrame(rows).sort_values("group").reset_index(drop=True)


def _write_outputs(
    output_dir: Path,
    trainer_name: str,
    error_predictions: pd.DataFrame,
    summary: pd.DataFrame,
    high_confidence_errors: pd.DataFrame,
    probability_bins: pd.DataFrame,
) -> dict[str, Path]:
    output_paths = {
        "predictions": output_dir / f"error_predictions_{trainer_name}.csv",
        "summary": output_dir / f"error_summary_{trainer_name}.csv",
        "high_confidence": output_dir / f"high_confidence_errors_{trainer_name}.csv",
        "probability_bins": output_dir / f"probability_bin_errors_{trainer_name}.csv",
    }
    error_predictions.loc[:, list(PREDICTION_EXPORT_COLUMNS)].to_csv(
        output_paths["predictions"],
        index=False,
    )
    summary.to_csv(output_paths["summary"], index=False)
    high_confidence_columns = [
        column for column in PREDICTION_EXPORT_COLUMNS if column in high_confidence_errors.columns
    ]
    high_confidence_errors.loc[:, high_confidence_columns].to_csv(
        output_paths["high_confidence"],
        index=False,
    )
    probability_bins.to_csv(output_paths["probability_bins"], index=False)
    return output_paths


def _build_plots(
    output_dir: Path,
    error_predictions: pd.DataFrame,
    probability_bins: pd.DataFrame,
    error_by_volatility: pd.DataFrame,
    error_by_trend: pd.DataFrame,
) -> dict[str, Path]:
    plot_paths = {
        "error_type_counts": output_dir / "error_type_counts.png",
        "error_rate_by_confidence": output_dir / "error_rate_by_confidence.png",
        "error_rate_by_volatility": output_dir / "error_rate_by_volatility.png",
        "error_rate_by_trend": output_dir / "error_rate_by_trend.png",
    }
    _plot_error_type_counts(error_predictions, plot_paths["error_type_counts"])
    _plot_error_rate_by_confidence(
        probability_bins,
        plot_paths["error_rate_by_confidence"],
    )
    _plot_error_rate_by_group(
        error_by_volatility,
        title="Error rate by volatility regime",
        path=plot_paths["error_rate_by_volatility"],
    )
    _plot_error_rate_by_group(
        error_by_trend,
        title="Error rate by trend regime",
        path=plot_paths["error_rate_by_trend"],
    )
    return plot_paths


def _plot_error_type_counts(predictions: pd.DataFrame, path: Path) -> None:
    figure, axis = plt.subplots(figsize=(8.5, 4.2))
    counts = predictions["error_type"].value_counts().sort_index()
    if counts.empty:
        axis.text(0.5, 0.5, "No predictions", ha="center", va="center")
    else:
        axis.bar(counts.index, counts.values, color="#175cd3", alpha=0.86)
    axis.set_title("Prediction error type counts")
    axis.set_xlabel("error type")
    axis.set_ylabel("rows")
    axis.tick_params(axis="x", rotation=20)
    axis.grid(axis="y", color="#d9dee7", linewidth=0.8, alpha=0.8)
    _save_figure(figure, path)


def _plot_error_rate_by_confidence(probability_bins: pd.DataFrame, path: Path) -> None:
    figure, axis = plt.subplots(figsize=(8.5, 4.2))
    if probability_bins.empty:
        axis.text(0.5, 0.5, "No confidence values", ha="center", va="center")
    else:
        metric_frame = probability_bins.copy()
        metric_frame["error_rate"] = pd.to_numeric(
            metric_frame["error_rate"],
            errors="coerce",
        ).fillna(0)
        axis.bar(
            metric_frame["confidence_bin"],
            metric_frame["error_rate"],
            color="#d92d20",
            alpha=0.86,
        )
    axis.set_title("Error rate by confidence bin")
    axis.set_xlabel("confidence")
    axis.set_ylabel("error rate")
    axis.set_ylim(0, 1.05)
    axis.grid(axis="y", color="#d9dee7", linewidth=0.8, alpha=0.8)
    _save_figure(figure, path)


def _plot_error_rate_by_group(metrics: pd.DataFrame, title: str, path: Path) -> None:
    figure, axis = plt.subplots(figsize=(8.5, 4.2))
    if metrics.empty:
        axis.text(0.5, 0.5, "No group metrics", ha="center", va="center")
    else:
        metric_frame = metrics.copy()
        metric_frame["error_rate"] = pd.to_numeric(
            metric_frame["error_rate"],
            errors="coerce",
        ).fillna(0)
        axis.bar(metric_frame["group"], metric_frame["error_rate"], color="#f79009")
    axis.set_title(title)
    axis.set_xlabel("group")
    axis.set_ylabel("error rate")
    axis.set_ylim(0, 1.05)
    axis.tick_params(axis="x", rotation=20)
    axis.grid(axis="y", color="#d9dee7", linewidth=0.8, alpha=0.8)
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
    error_predictions: pd.DataFrame,
    summary: pd.DataFrame,
    high_confidence_errors: pd.DataFrame,
    probability_bins: pd.DataFrame,
    error_by_volatility: pd.DataFrame,
    error_by_trend: pd.DataFrame,
    fold_errors: list[dict[str, Any]],
    output_paths: dict[str, Path],
    plot_paths: dict[str, Path],
    args: argparse.Namespace,
) -> None:
    output_doc.parent.mkdir(parents=True, exist_ok=True)
    path_refs = _markdown_paths(output_doc, output_paths | plot_paths)
    markdown = [
        "# Real Data Error Analysis",
        "",
        "## Purpose",
        "",
        "This report inspects false positives, false negatives, correct predictions,",
        "model confidence, and regime-specific error rates for walk-forward test",
        "fold predictions. It is diagnostic analysis, not a trading strategy.",
        "",
        "## Dataset",
        "",
        _manifest_table(manifest),
        "",
        f"Final feature/target rows after pipeline preparation: `{len(final_dataset)}`.",
        f"Walk-forward prediction rows used for error analysis: `{len(error_predictions)}`.",
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
                ("folds_with_predictions", error_predictions["fold_id"].nunique()),
                ("fold_errors", len(fold_errors)),
                ("trend_window", args.trend_window),
                ("trend_threshold", args.trend_threshold),
                ("top_n", args.top_n),
                ("random_shuffle", "no"),
            ],
        ),
        "",
        "## Error Type Summary",
        "",
        "Definitions:",
        "",
        "- `false_positive`: model predicted `up`, actual direction was `down`.",
        "- `false_negative`: model predicted `down`, actual direction was `up`.",
        "- `true_positive`: model predicted `up`, actual direction was `up`.",
        "- `true_negative`: model predicted `down`, actual direction was `down`.",
        "",
        f"Summary CSV: [`{output_paths['summary'].name}`]({path_refs['summary']})",
        "",
        f"![Error type counts]({path_refs['error_type_counts']})",
        "",
        _dataframe_to_markdown(_format_summary(summary)),
        "",
        "## High-Confidence Errors",
        "",
        "High-confidence mistakes are useful model-risk examples because the model",
        "was confident while still wrong.",
        "",
        f"CSV output: [`{output_paths['high_confidence'].name}`]({path_refs['high_confidence']})",
        "",
        _dataframe_to_markdown(_format_predictions_preview(high_confidence_errors)),
        "",
        "## Error Rate By Confidence",
        "",
        f"CSV output: [`{output_paths['probability_bins'].name}`]({path_refs['probability_bins']})",
        "",
        f"![Error rate by confidence]({path_refs['error_rate_by_confidence']})",
        "",
        _dataframe_to_markdown(_format_probability_bins(probability_bins)),
        "",
        "## Error Rate By Volatility Regime",
        "",
        f"![Error rate by volatility]({path_refs['error_rate_by_volatility']})",
        "",
        _dataframe_to_markdown(_format_group_errors(error_by_volatility)),
        "",
        "## Error Rate By Trend Regime",
        "",
        f"![Error rate by trend]({path_refs['error_rate_by_trend']})",
        "",
        _dataframe_to_markdown(_format_group_errors(error_by_trend)),
        "",
        "## Interpretation",
        "",
        _interpretation(summary, high_confidence_errors),
        "",
        "## Limitations",
        "",
        "- The smoke dataset is short and has few folds.",
        "- Confidence comes from classifier probability output, not calibrated odds.",
        "- Regime thresholds are heuristic diagnostics.",
        "- The target is directional classification only.",
        "- No fees, slippage, sizing, or execution constraints are modeled.",
        "- This report does not imply profitability or deployable market edge.",
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


def _markdown_paths(output_doc: Path, paths: dict[str, Path]) -> dict[str, str]:
    return {
        key: path.resolve().relative_to(output_doc.parent.resolve()).as_posix()
        for key, path in paths.items()
    }


def _format_summary(summary: pd.DataFrame) -> pd.DataFrame:
    formatted = summary.copy()
    for column in SUMMARY_COLUMNS:
        if column in formatted.columns:
            if column.endswith("_count") or column == "total_rows":
                formatted[column] = formatted[column].map(_format_int)
            else:
                formatted[column] = formatted[column].map(_format_float)
    return formatted


def _format_predictions_preview(predictions: pd.DataFrame) -> pd.DataFrame:
    preview_columns = [
        "timestamp",
        "fold_id",
        "close",
        "y_true",
        "y_pred",
        "y_proba",
        "confidence",
        "error_type",
        "volatility_regime",
        "trend_regime",
    ]
    if predictions.empty:
        return pd.DataFrame(columns=preview_columns)
    preview = predictions.loc[
        :,
        [column for column in preview_columns if column in predictions.columns],
    ].copy()
    for column in ["close", "y_proba", "confidence"]:
        if column in preview.columns:
            preview[column] = preview[column].map(_format_float)
    return preview


def _format_probability_bins(probability_bins: pd.DataFrame) -> pd.DataFrame:
    formatted = probability_bins.copy()
    for column in ["rows", "correct_count", "error_count"]:
        if column in formatted.columns:
            formatted[column] = formatted[column].map(_format_int)
    if "error_rate" in formatted.columns:
        formatted["error_rate"] = formatted["error_rate"].map(_format_float)
    return formatted


def _format_group_errors(metrics: pd.DataFrame) -> pd.DataFrame:
    formatted = metrics.copy()
    for column in [
        "rows",
        "correct_count",
        "error_count",
        "false_positive_count",
        "false_negative_count",
    ]:
        if column in formatted.columns:
            formatted[column] = formatted[column].map(_format_int)
    if "error_rate" in formatted.columns:
        formatted["error_rate"] = formatted["error_rate"].map(_format_float)
    return formatted


def _interpretation(summary: pd.DataFrame, high_confidence_errors: pd.DataFrame) -> str:
    row = summary.iloc[0]
    lines = [
        f"The smoke run produced `{_format_int(row['error_count'])}` errors out of "
        f"`{_format_int(row['total_rows'])}` predictions "
        f"(error rate `{_format_float(row['error_rate'])}`).",
        f"False positives: `{_format_int(row['false_positive_count'])}`; "
        f"false negatives: `{_format_int(row['false_negative_count'])}`.",
    ]
    if not high_confidence_errors.empty:
        top_error = high_confidence_errors.iloc[0]
        lines.append(
            "The most confident mistake in this run has confidence "
            f"`{_format_float(top_error['confidence'])}` and type "
            f"`{top_error['error_type']}`."
        )
    lines.append(
        "These examples are useful for model-risk inspection and should be re-run "
        "on longer frozen periods before drawing stronger conclusions."
    )
    return "\n\n".join(lines)


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


def _reproducibility_command(args: argparse.Namespace) -> str:
    return (
        ".crypto\\Scripts\\python.exe scripts\\run_real_data_error_analysis.py "
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
        f"--trend-threshold {args.trend_threshold} "
        f"--top-n {args.top_n}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
