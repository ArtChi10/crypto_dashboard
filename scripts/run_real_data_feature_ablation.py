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

from mlcore.evaluation.ablation import FeatureAblationService  # noqa: E402
from mlcore.features import FeatureBuilder  # noqa: E402
from mlcore.preprocessing import DataCleaner  # noqa: E402
from mlcore.targets import TargetBuilder  # noqa: E402
from mlcore.training.baseline_trainer import BaselineTrainer  # noqa: E402
from mlcore.training.catboost_trainer import CatBoostTrainer  # noqa: E402
from mlcore.training.dummy_trainer import DummyBaselineTrainer  # noqa: E402

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

METRIC_COLUMNS = ("accuracy", "precision", "recall", "f1", "roc_auc")
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
    train_df, test_df = _time_split(final_dataset, train_ratio=args.train_ratio)
    result = FeatureAblationService().evaluate_groups(
        TRAINER_FACTORIES[args.trainer],
        train_df,
        test_df,
        mode=args.mode,
    )
    result = _annotate_result(result, mode=args.mode)

    output_paths = _write_outputs(
        output_dir=output_dir,
        trainer_name=args.trainer,
        mode=args.mode,
        result=result,
    )
    plot_paths = _build_plots(output_dir=output_dir, result=result)
    _write_report(
        output_doc=output_doc,
        manifest=manifest,
        final_dataset=final_dataset,
        train_df=train_df,
        test_df=test_df,
        result=result,
        output_paths=output_paths,
        plot_paths=plot_paths,
        args=args,
    )

    best_experiment = _best_experiment_by_metric(result, "f1")
    print(f"Saved feature ablation report: {output_doc}")
    print(f"Saved feature ablation outputs: {output_dir}")
    print(f"Final rows: {len(final_dataset)}")
    print(f"Train rows: {len(train_df)}")
    print(f"Test rows: {len(test_df)}")
    print(f"Experiments: {len(result)}")
    print(f"Best experiment by f1: {best_experiment}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run feature ablation on a frozen real Binance dataset.",
    )
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-doc", default="docs/real_data_feature_ablation.md")
    parser.add_argument("--output-dir", default="docs/assets/real_data_feature_ablation")
    parser.add_argument("--trainer", choices=sorted(TRAINER_FACTORIES), default="baseline")
    parser.add_argument("--target-horizon", type=int, default=3)
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument(
        "--mode",
        choices=("drop_groups", "only_groups"),
        default="drop_groups",
    )
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


def _time_split(df: pd.DataFrame, train_ratio: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not 0 < train_ratio < 1:
        raise ValueError("train_ratio must be between 0 and 1.")
    if "timestamp" not in df.columns:
        raise ValueError("Dataset is missing timestamp column required for ablation split.")

    sorted_df = df.copy()
    sorted_df["timestamp"] = pd.to_datetime(sorted_df["timestamp"])
    sorted_df = sorted_df.sort_values("timestamp").reset_index(drop=True)
    split_index = int(len(sorted_df) * train_ratio)
    if split_index < 1 or split_index >= len(sorted_df):
        raise ValueError("Dataset must be large enough for non-empty train and test splits.")
    return (
        sorted_df.iloc[:split_index].reset_index(drop=True),
        sorted_df.iloc[split_index:].reset_index(drop=True),
    )


def _annotate_result(result: pd.DataFrame, mode: str) -> pd.DataFrame:
    annotated = result.copy()
    annotated.insert(1, "mode", mode)
    if mode == "drop_groups":
        feature_group = annotated["excluded_group"].fillna("all_features")
    else:
        feature_group = annotated["experiment"]
    annotated.insert(2, "feature_group", feature_group)
    return annotated


def _write_outputs(
    output_dir: Path,
    trainer_name: str,
    mode: str,
    result: pd.DataFrame,
) -> dict[str, Path]:
    output_path = output_dir / f"feature_ablation_{trainer_name}_{mode}.csv"
    result.to_csv(output_path, index=False)
    return {"ablation_csv": output_path}


def _build_plots(output_dir: Path, result: pd.DataFrame) -> dict[str, Path]:
    plot_paths = {
        "f1": output_dir / "feature_ablation_f1.png",
        "roc_auc": output_dir / "feature_ablation_roc_auc.png",
        "accuracy": output_dir / "feature_ablation_accuracy.png",
    }
    _plot_metric(result, "f1", plot_paths["f1"])
    _plot_metric(result, "roc_auc", plot_paths["roc_auc"])
    _plot_metric(result, "accuracy", plot_paths["accuracy"])
    return plot_paths


def _plot_metric(result: pd.DataFrame, metric_name: str, path: Path) -> None:
    figure, axis = plt.subplots(figsize=(9.5, 4.8))
    metric_frame = result.loc[:, ["experiment", metric_name, "error_message"]].copy()
    metric_frame[metric_name] = pd.to_numeric(metric_frame[metric_name], errors="coerce")
    metric_frame = metric_frame[metric_frame["error_message"].isna()]
    metric_frame = metric_frame.dropna(subset=[metric_name])

    if metric_frame.empty:
        axis.text(0.5, 0.5, f"No {metric_name} values", ha="center", va="center")
    else:
        axis.bar(metric_frame["experiment"], metric_frame[metric_name], color="#175cd3")
    axis.set_title(f"Feature ablation {metric_name}")
    axis.set_xlabel("experiment")
    axis.set_ylabel(metric_name)
    axis.set_ylim(0, 1.05)
    axis.tick_params(axis="x", rotation=25)
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
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    result: pd.DataFrame,
    output_paths: dict[str, Path],
    plot_paths: dict[str, Path],
    args: argparse.Namespace,
) -> None:
    output_doc.parent.mkdir(parents=True, exist_ok=True)
    path_refs = _markdown_paths(output_doc, output_paths | plot_paths)
    markdown = [
        "# Real Data Feature Ablation",
        "",
        "## Purpose",
        "",
        "This report checks which engineered OHLCV feature groups contribute most to",
        "directional classification metrics on a frozen real Binance dataset.",
        "Feature ablation is diagnostic feature analysis, not a trading strategy.",
        "",
        "## Dataset",
        "",
        _manifest_table(manifest),
        "",
        f"Final feature/target rows after pipeline preparation: `{len(final_dataset)}`.",
        "",
        "## Feature Groups",
        "",
        _feature_groups_markdown(),
        "",
        "## Setup",
        "",
        _rows_to_markdown_table(
            ["parameter", "value"],
            [
                ("trainer", args.trainer),
                ("target_horizon", args.target_horizon),
                ("train_ratio", args.train_ratio),
                ("train_rows", len(train_df)),
                ("test_rows", len(test_df)),
                ("mode", args.mode),
                ("random_shuffle", "no"),
            ],
        ),
        "",
        "The split is chronological. The first segment is train data and the later",
        "segment is test data. No random shuffle is used.",
        "",
        "## Results",
        "",
        f"CSV output: [`{output_paths['ablation_csv'].name}`]({path_refs['ablation_csv']})",
        "",
        f"![Feature ablation F1]({path_refs['f1']})",
        "",
        f"![Feature ablation ROC AUC]({path_refs['roc_auc']})",
        "",
        f"![Feature ablation accuracy]({path_refs['accuracy']})",
        "",
        _dataframe_to_markdown(_format_result(result)),
        "",
        "## Interpretation",
        "",
        _interpretation(result, args.mode),
        "",
        "Feature importance and ablation answer different questions: feature",
        "importance ranks model usage, while ablation checks what happens when groups",
        "are removed or isolated.",
        "",
        "## Limitations",
        "",
        "- This report uses one frozen symbol, interval, and date range.",
        "- The smoke dataset is short.",
        "- The ablation setup uses one chronological split, not walk-forward folds.",
        "- Removing a group can help or hurt depending on the selected period.",
        "- Metrics are directional classification metrics only.",
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


def _feature_groups_markdown() -> str:
    rows = [
        (group_name, ", ".join(columns))
        for group_name, columns in FeatureAblationService.DEFAULT_FEATURE_GROUPS.items()
    ]
    return _rows_to_markdown_table(["feature_group", "columns"], rows)


def _interpretation(result: pd.DataFrame, mode: str) -> str:
    best_experiment = _best_experiment_by_metric(result, "f1")
    best_row = result.loc[result["experiment"] == best_experiment].iloc[0]
    best_f1 = _format_float(best_row["f1"])
    lines = [
        f"The strongest experiment by F1 in this smoke run is `{best_experiment}` "
        f"with F1 `{best_f1}`.",
    ]
    if mode == "drop_groups" and "all_features" in result["experiment"].values:
        baseline_row = result.loc[result["experiment"] == "all_features"].iloc[0]
        baseline_f1 = pd.to_numeric(pd.Series([baseline_row["f1"]]), errors="coerce").iloc[0]
        comparisons = []
        for _, row in result.iterrows():
            if row["experiment"] == "all_features" or pd.isna(row["f1"]):
                continue
            delta = float(row["f1"] - baseline_f1)
            comparisons.append((row["experiment"], delta))
        if comparisons:
            comparisons.sort(key=lambda item: item[1], reverse=True)
            top_delta = comparisons[0]
            lines.append(
                f"The largest F1 delta versus all features is `{top_delta[0]}` "
                f"with delta `{_format_float(top_delta[1])}`."
            )
    lines.append(
        "These comparisons are diagnostic and should be re-run on longer frozen "
        "periods and walk-forward splits before drawing stronger conclusions."
    )
    return "\n\n".join(lines)


def _best_experiment_by_metric(result: pd.DataFrame, metric_name: str) -> str:
    metric_values = pd.to_numeric(result[metric_name], errors="coerce")
    if metric_values.dropna().empty:
        return "-"
    return str(result.loc[metric_values.idxmax(), "experiment"])


def _format_result(result: pd.DataFrame) -> pd.DataFrame:
    formatted = result.copy()
    for column in METRIC_COLUMNS:
        if column in formatted.columns:
            formatted[column] = formatted[column].map(_format_float)
    return formatted


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


def _markdown_paths(output_doc: Path, paths: dict[str, Path]) -> dict[str, str]:
    return {
        key: path.resolve().relative_to(output_doc.parent.resolve()).as_posix()
        for key, path in paths.items()
    }


def _reproducibility_command(args: argparse.Namespace) -> str:
    return (
        ".crypto\\Scripts\\python.exe scripts\\run_real_data_feature_ablation.py "
        f"--dataset {args.dataset} "
        f"--manifest {args.manifest} "
        f"--output-doc {args.output_doc} "
        f"--output-dir {args.output_dir} "
        f"--trainer {args.trainer} "
        f"--target-horizon {args.target_horizon} "
        f"--train-ratio {args.train_ratio} "
        f"--mode {args.mode}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
