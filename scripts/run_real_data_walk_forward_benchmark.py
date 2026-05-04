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

from mlcore.evaluation.walk_forward import WalkForwardEvaluationService  # noqa: E402
from mlcore.features import FeatureBuilder  # noqa: E402
from mlcore.preprocessing import DataCleaner  # noqa: E402
from mlcore.targets import TargetBuilder  # noqa: E402
from mlcore.training.baseline_trainer import BaselineTrainer  # noqa: E402
from mlcore.training.catboost_trainer import CatBoostTrainer  # noqa: E402
from mlcore.training.dummy_trainer import DummyBaselineTrainer  # noqa: E402

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

METRIC_COLUMNS = ("accuracy", "precision", "recall", "f1", "roc_auc")
SUMMARY_COLUMNS = (
    "trainer",
    "folds_total",
    "folds_failed",
    "folds_success",
    "accuracy_mean",
    "accuracy_std",
    "f1_mean",
    "f1_std",
    "roc_auc_mean",
    "roc_auc_std",
    "precision_mean",
    "recall_mean",
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
    trainers = _parse_trainers(args.trainers)

    raw_dataset = _load_dataset(dataset_path)
    manifest = _load_manifest(manifest_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    final_dataset = _build_final_dataset(raw_dataset, horizon=args.target_horizon)
    fold_results = _run_benchmarks(
        final_dataset=final_dataset,
        trainers=trainers,
        train_window=args.train_window,
        test_window=args.test_window,
        step=args.step,
        output_dir=output_dir,
    )
    summary = _summary_table(fold_results)
    plot_paths = _build_plots(fold_results, summary, output_dir)
    _write_report(
        output_doc=output_doc,
        manifest=manifest,
        final_dataset=final_dataset,
        fold_results=fold_results,
        summary=summary,
        plot_paths=plot_paths,
        args=args,
    )

    print(f"Saved benchmark report: {output_doc}")
    print(f"Saved benchmark outputs: {output_dir}")
    print(f"Final rows: {len(final_dataset)}")
    for trainer_name, result in fold_results.items():
        failed = _failed_mask(result).sum()
        print(f"{trainer_name}: folds={len(result)}, failed={failed}")
    best_model = _best_model_by_mean_f1(summary)
    print(f"Best model by mean f1: {best_model}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a walk-forward benchmark on a frozen real Binance dataset.",
    )
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-doc", default="docs/real_data_walk_forward_benchmark.md")
    parser.add_argument("--output-dir", default="docs/assets/real_data_walk_forward")
    parser.add_argument("--target-horizon", type=int, default=3)
    parser.add_argument("--train-window", type=int, default=120)
    parser.add_argument("--test-window", type=int, default=24)
    parser.add_argument("--step", type=int, default=24)
    parser.add_argument("--trainers", default="dummy,baseline,catboost")
    return parser.parse_args()


def _parse_trainers(raw_value: str) -> list[str]:
    trainers = []
    for item in str(raw_value).split(","):
        trainer = item.strip().lower()
        if not trainer:
            continue
        if trainer not in TRAINER_FACTORIES:
            raise ValueError(
                f"Unknown trainer: {trainer}. Available trainers: "
                f"{', '.join(sorted(TRAINER_FACTORIES))}"
            )
        trainers.append(trainer)
    if not trainers:
        raise ValueError("trainers must contain at least one trainer.")
    return trainers


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


def _run_benchmarks(
    final_dataset: pd.DataFrame,
    trainers: list[str],
    train_window: int,
    test_window: int,
    step: int,
    output_dir: Path,
) -> dict[str, pd.DataFrame]:
    evaluator = WalkForwardEvaluationService()
    results = {}
    for trainer_name in trainers:
        result = evaluator.evaluate(
            TRAINER_FACTORIES[trainer_name](),
            final_dataset,
            train_window=train_window,
            test_window=test_window,
            step=step,
            target_col="target",
            raise_on_error=False,
        )
        result.insert(0, "trainer", trainer_name)
        result.to_csv(output_dir / f"walk_forward_{trainer_name}.csv", index=False)
        results[trainer_name] = result
    return results


def _summary_table(fold_results: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for trainer_name, result in fold_results.items():
        failed_mask = _failed_mask(result)
        row = {
            "trainer": trainer_name,
            "folds_total": int(len(result)),
            "folds_failed": int(failed_mask.sum()),
            "folds_success": int((~failed_mask).sum()),
        }
        for metric_name in METRIC_COLUMNS:
            metric_values = pd.to_numeric(result[metric_name], errors="coerce").dropna()
            row[f"{metric_name}_mean"] = (
                float(metric_values.mean()) if not metric_values.empty else None
            )
            if metric_name in {"accuracy", "f1", "roc_auc"}:
                row[f"{metric_name}_std"] = (
                    float(metric_values.std()) if len(metric_values) > 1 else None
                )
        rows.append(row)
    return pd.DataFrame(rows).loc[:, list(SUMMARY_COLUMNS)]


def _failed_mask(result: pd.DataFrame) -> pd.Series:
    errors = result.get("error_message")
    if errors is None:
        return pd.Series([False] * len(result), index=result.index)
    return errors.fillna("").astype(str).str.len() > 0


def _build_plots(
    fold_results: dict[str, pd.DataFrame],
    summary: pd.DataFrame,
    output_dir: Path,
) -> dict[str, Path]:
    plot_paths = {
        "f1": output_dir / "walk_forward_f1_by_fold.png",
        "roc_auc": output_dir / "walk_forward_roc_auc_by_fold.png",
        "summary": output_dir / "walk_forward_summary.png",
    }
    _plot_metric_by_fold(fold_results, "f1", plot_paths["f1"])
    _plot_metric_by_fold(fold_results, "roc_auc", plot_paths["roc_auc"])
    _plot_summary(summary, plot_paths["summary"])
    return plot_paths


def _plot_metric_by_fold(
    fold_results: dict[str, pd.DataFrame],
    metric_name: str,
    path: Path,
) -> None:
    figure, axis = plt.subplots(figsize=(8.5, 4.2))
    plotted = False
    for trainer_name, result in fold_results.items():
        metric_values = pd.to_numeric(result[metric_name], errors="coerce")
        metric_frame = pd.DataFrame(
            {
                "fold_id": result["fold_id"],
                metric_name: metric_values,
            }
        ).dropna()
        if metric_frame.empty:
            continue
        axis.plot(
            metric_frame["fold_id"],
            metric_frame[metric_name],
            marker="o",
            linewidth=1.8,
            label=trainer_name,
        )
        plotted = True

    axis.set_title(f"Walk-forward {metric_name} by fold")
    axis.set_xlabel("fold")
    axis.set_ylabel(metric_name)
    axis.set_ylim(0, 1.05)
    axis.grid(axis="y", color="#d9dee7", linewidth=0.8, alpha=0.8)
    if plotted:
        axis.legend()
    else:
        axis.text(0.5, 0.5, "No successful folds", ha="center", va="center")
    _save_figure(figure, path)


def _plot_summary(summary: pd.DataFrame, path: Path) -> None:
    figure, axis = plt.subplots(figsize=(8.5, 4.2))
    x_positions = list(range(len(summary)))
    bar_width = 0.34
    axis.bar(
        [position - bar_width / 2 for position in x_positions],
        pd.to_numeric(summary["f1_mean"], errors="coerce").fillna(0),
        width=bar_width,
        label="mean f1",
        color="#175cd3",
    )
    axis.bar(
        [position + bar_width / 2 for position in x_positions],
        pd.to_numeric(summary["roc_auc_mean"], errors="coerce").fillna(0),
        width=bar_width,
        label="mean roc_auc",
        color="#17663a",
    )
    axis.set_title("Walk-forward summary")
    axis.set_xlabel("trainer")
    axis.set_ylabel("score")
    axis.set_xticks(x_positions, summary["trainer"].tolist())
    axis.set_ylim(0, 1.05)
    axis.grid(axis="y", color="#d9dee7", linewidth=0.8, alpha=0.8)
    axis.legend()
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
    fold_results: dict[str, pd.DataFrame],
    summary: pd.DataFrame,
    plot_paths: dict[str, Path],
    args: argparse.Namespace,
) -> None:
    output_doc.parent.mkdir(parents=True, exist_ok=True)
    markdown = [
        "# Real Data Walk-Forward Benchmark",
        "",
        "## Purpose",
        "",
        "This report records a first walk-forward benchmark on a frozen real Binance",
        "OHLCV dataset. It compares directional classification metrics across",
        "sequential time folds. The goal is signal stability inspection, not a",
        "trading or profitability claim.",
        "",
        "## Dataset",
        "",
        _manifest_table(manifest),
        "",
        f"Final feature/target rows after pipeline preparation: `{len(final_dataset)}`.",
        "",
        "## Feature/Target Pipeline",
        "",
        "- `DataCleaner` validates and sorts OHLCV rows.",
        "- `FeatureBuilder` creates returns, moving averages, volatility, volume, and",
        "  candle-shape features.",
        f"- `TargetBuilder(horizon={args.target_horizon})` creates `target = 1` when",
        "  `close(t+horizon) > close(t)`.",
        "- Timestamp, symbol, and target are excluded from model features.",
        "",
        "## Walk-Forward Setup",
        "",
        _rows_to_markdown_table(
            ["parameter", "value"],
            [
                ("target_horizon", args.target_horizon),
                ("train_window", args.train_window),
                ("test_window", args.test_window),
                ("step", args.step),
                ("random_shuffle", "no"),
                ("test_fold_tuning", "no"),
            ],
        ),
        "",
        "Each fold trains on an earlier chronological window and evaluates on the",
        "following test window. One-class folds can fail for non-dummy models; failed",
        "folds are counted and kept in the CSV outputs.",
        "",
        "## Models",
        "",
        "- `dummy`: `DummyClassifier` majority-class baseline.",
        "- `baseline`: LogisticRegression with StandardScaler.",
        "- `catboost`: CatBoostClassifier with lightweight research parameters",
        "  (`iterations=20`, `depth=4`, `learning_rate=0.1`).",
        "",
        "## Summary Results",
        "",
        f"![Walk-forward summary]({_relative_markdown_path(plot_paths['summary'], output_doc)})",
        "",
        _dataframe_to_markdown(_format_summary(summary)),
        "",
        "## Fold-Level Results",
        "",
        f"![F1 by fold]({_relative_markdown_path(plot_paths['f1'], output_doc)})",
        "",
        f"![ROC AUC by fold]({_relative_markdown_path(plot_paths['roc_auc'], output_doc)})",
        "",
        _fold_level_sections(fold_results, output_doc),
        "",
        "## Interpretation",
        "",
        _interpretation(summary),
        "",
        "The benchmark should be interpreted as a stability check, not as evidence of",
        "deployable market edge.",
        "",
        "## Limitations",
        "",
        "- This benchmark uses one frozen symbol, interval, and date range.",
        "- The smoke dataset is short; fold counts are limited.",
        "- Classification metrics do not include fees, slippage, position sizing, or",
        "  execution constraints.",
        "- No hyperparameter tuning is performed inside this script.",
        "- Market behavior is non-stationary, so these metrics can degrade on other",
        "  periods.",
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


def _format_summary(summary: pd.DataFrame) -> pd.DataFrame:
    formatted = summary.copy()
    metric_columns = [
        column
        for column in formatted.columns
        if column.endswith("_mean") or column.endswith("_std")
    ]
    for column in metric_columns:
        formatted[column] = formatted[column].map(_format_float)
    return formatted


def _fold_level_sections(fold_results: dict[str, pd.DataFrame], output_doc: Path) -> str:
    sections = []
    for trainer_name, result in fold_results.items():
        csv_path = (
            output_doc.parent
            / "assets"
            / "real_data_walk_forward"
            / (f"walk_forward_{trainer_name}.csv")
        )
        preview_columns = [
            "fold_id",
            "train_start",
            "test_start",
            "accuracy",
            "precision",
            "recall",
            "f1",
            "roc_auc",
            "error_message",
        ]
        sections.extend(
            [
                f"### {trainer_name}",
                "",
                f"CSV output: [`{csv_path.name}`]({_relative_markdown_path(csv_path, output_doc)})",
                "",
                _dataframe_to_markdown(result.loc[:, preview_columns]),
                "",
            ]
        )
    return "\n".join(sections).strip()


def _interpretation(summary: pd.DataFrame) -> str:
    best_model = _best_model_by_mean_f1(summary)
    if best_model == "-":
        return "No successful folds produced a valid mean F1 score."

    best_row = summary.loc[summary["trainer"] == best_model].iloc[0]
    best_f1 = _format_float(best_row["f1_mean"])
    best_roc_auc = _format_float(best_row["roc_auc_mean"])
    return (
        f"By mean F1, the strongest trainer in this run is `{best_model}` "
        f"(mean F1 `{best_f1}`, mean ROC AUC `{best_roc_auc}`). "
        "This comparison is descriptive and should be re-run on longer frozen "
        "periods before drawing stronger conclusions."
    )


def _best_model_by_mean_f1(summary: pd.DataFrame) -> str:
    values = pd.to_numeric(summary["f1_mean"], errors="coerce")
    if values.dropna().empty:
        return "-"
    return str(summary.loc[values.idxmax(), "trainer"])


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
        ".crypto\\Scripts\\python.exe scripts\\run_real_data_walk_forward_benchmark.py "
        f"--dataset {args.dataset} "
        f"--manifest {args.manifest} "
        f"--output-doc {args.output_doc} "
        f"--output-dir {args.output_dir} "
        f"--target-horizon {args.target_horizon} "
        f"--train-window {args.train_window} "
        f"--test-window {args.test_window} "
        f"--step {args.step} "
        f"--trainers {args.trainers}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
