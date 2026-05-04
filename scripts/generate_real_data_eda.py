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

from mlcore.features import FeatureBuilder  # noqa: E402
from mlcore.preprocessing import DataCleaner  # noqa: E402
from mlcore.targets import TargetBuilder  # noqa: E402

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

NUMERIC_COLUMNS = ("open", "high", "low", "close", "volume")
REQUIRED_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume", "symbol")


def main() -> int:
    args = _parse_args()
    dataset_path = Path(args.dataset)
    manifest_path = Path(args.manifest)
    output_doc = Path(args.output_doc)
    output_dir = Path(args.output_dir)
    horizons = _parse_horizons(args.horizons)

    dataset = _load_dataset(dataset_path)
    manifest = _load_manifest(manifest_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    prepared_dataset = _prepare_dataset_for_eda(dataset)
    returns = _close_returns(prepared_dataset)
    quality = _data_quality(prepared_dataset, manifest)
    numeric_summary = _numeric_summary(prepared_dataset)
    returns_summary = _series_summary(returns)
    target_balance = _target_balance_by_horizon(prepared_dataset, horizons)

    plot_paths = _build_plots(
        dataset=prepared_dataset,
        returns=returns,
        target_balance=target_balance,
        output_dir=output_dir,
    )
    _write_report(
        output_doc=output_doc,
        manifest=manifest,
        dataset=prepared_dataset,
        quality=quality,
        numeric_summary=numeric_summary,
        returns_summary=returns_summary,
        target_balance=target_balance,
        plot_paths=plot_paths,
        command_args=args,
    )

    print(f"Saved EDA report: {output_doc}")
    print(f"Saved plots: {output_dir}")
    print(f"Rows: {len(prepared_dataset)}")
    print(f"Horizons: {', '.join(str(horizon) for horizon in horizons)}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an EDA report for a frozen real Binance OHLCV dataset.",
    )
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-doc", default="docs/real_data_eda.md")
    parser.add_argument("--output-dir", default="docs/assets/real_data_eda")
    parser.add_argument("--horizons", default="1,3,6,12")
    return parser.parse_args()


def _parse_horizons(raw_value: str) -> list[int]:
    horizons = []
    for item in str(raw_value).split(","):
        item = item.strip()
        if not item:
            continue
        horizon = int(item)
        if horizon < 1:
            raise ValueError("horizons must contain positive integers.")
        horizons.append(horizon)
    if not horizons:
        raise ValueError("horizons must contain at least one value.")
    return horizons


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


def _prepare_dataset_for_eda(dataset: pd.DataFrame) -> pd.DataFrame:
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in dataset.columns]
    if missing_columns:
        raise ValueError(f"Dataset is missing required columns: {', '.join(missing_columns)}")

    prepared = dataset.copy()
    prepared["timestamp"] = pd.to_datetime(prepared["timestamp"], errors="coerce")
    for column in NUMERIC_COLUMNS:
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
    return prepared.sort_values(["symbol", "timestamp"], kind="mergesort").reset_index(drop=True)


def _close_returns(dataset: pd.DataFrame) -> pd.Series:
    returns = dataset.groupby("symbol", sort=False)["close"].pct_change()
    return returns.dropna()


def _data_quality(dataset: pd.DataFrame, manifest: dict[str, Any]) -> dict[str, Any]:
    timestamp = pd.to_datetime(dataset["timestamp"], errors="coerce")
    interval_delta = _interval_to_timedelta(str(manifest.get("interval", "")))
    duplicate_timestamps = int(dataset.duplicated(subset=["symbol", "timestamp"]).sum())
    gap_count = None
    expected_rows = None

    if interval_delta is not None and not timestamp.dropna().empty:
        gap_count = 0
        for _, symbol_frame in dataset.dropna(subset=["timestamp"]).groupby("symbol", sort=False):
            diffs = symbol_frame["timestamp"].sort_values().diff().dropna()
            gap_count += int((diffs != interval_delta).sum())
        timestamp_min = timestamp.min()
        timestamp_max = timestamp.max()
        expected_rows = int((timestamp_max - timestamp_min) / interval_delta) + 1

    return {
        "missing_values": {
            column: int(value) for column, value in dataset.isna().sum().to_dict().items()
        },
        "duplicate_timestamps": duplicate_timestamps,
        "expected_rows": expected_rows,
        "actual_rows": int(len(dataset)),
        "time_gap_count": gap_count,
    }


def _interval_to_timedelta(interval: str) -> pd.Timedelta | None:
    units = {"m": "minutes", "h": "hours", "d": "days"}
    if len(interval) < 2:
        return None
    try:
        amount = int(interval[:-1])
    except ValueError:
        return None
    unit = units.get(interval[-1])
    if unit is None:
        return None
    return pd.Timedelta(**{unit: amount})


def _numeric_summary(dataset: pd.DataFrame) -> pd.DataFrame:
    return dataset.loc[:, list(NUMERIC_COLUMNS)].agg(["min", "max", "mean", "std"]).T


def _series_summary(series: pd.Series) -> dict[str, float | int | None]:
    if series.empty:
        return {"count": 0, "min": None, "max": None, "mean": None, "std": None}
    return {
        "count": int(series.count()),
        "min": float(series.min()),
        "max": float(series.max()),
        "mean": float(series.mean()),
        "std": float(series.std()),
    }


def _target_balance_by_horizon(dataset: pd.DataFrame, horizons: list[int]) -> pd.DataFrame:
    rows = []
    for horizon in horizons:
        cleaned = DataCleaner().clean(dataset)
        features = FeatureBuilder().build(cleaned)
        final = TargetBuilder().build(features, horizon=horizon)
        target_counts = final["target"].value_counts().to_dict()
        target_0_count = int(target_counts.get(0, 0))
        target_1_count = int(target_counts.get(1, 0))
        final_rows = int(len(final))
        positive_rate = target_1_count / final_rows if final_rows else 0.0
        rows.append(
            {
                "horizon": horizon,
                "final_rows": final_rows,
                "target_0_count": target_0_count,
                "target_1_count": target_1_count,
                "positive_rate": positive_rate,
            }
        )
    return pd.DataFrame(rows)


def _build_plots(
    dataset: pd.DataFrame,
    returns: pd.Series,
    target_balance: pd.DataFrame,
    output_dir: Path,
) -> dict[str, Path]:
    plots = {
        "close": output_dir / "real_close.png",
        "returns": output_dir / "real_returns_distribution.png",
        "volume": output_dir / "real_volume.png",
        "target_balance": output_dir / "real_target_balance_by_horizon.png",
        "volatility": output_dir / "real_volatility_rolling.png",
    }
    _plot_close(dataset, plots["close"])
    _plot_returns(returns, plots["returns"])
    _plot_volume(dataset, plots["volume"])
    _plot_target_balance(target_balance, plots["target_balance"])
    _plot_volatility(dataset, plots["volatility"])
    return plots


def _plot_close(dataset: pd.DataFrame, path: Path) -> None:
    figure, axis = plt.subplots(figsize=(9, 4.2))
    axis.plot(dataset["timestamp"], dataset["close"], color="#175cd3", linewidth=1.5)
    axis.set_title("Close price")
    axis.set_xlabel("timestamp")
    axis.set_ylabel("close")
    axis.grid(axis="y", color="#d9dee7", linewidth=0.8, alpha=0.8)
    _save_figure(figure, path)


def _plot_returns(returns: pd.Series, path: Path) -> None:
    figure, axis = plt.subplots(figsize=(7.2, 4.0))
    axis.hist(returns * 100, bins=40, color="#175cd3", edgecolor="#ffffff")
    axis.set_title("Close returns distribution")
    axis.set_xlabel("return, %")
    axis.set_ylabel("count")
    axis.grid(axis="y", color="#d9dee7", linewidth=0.8, alpha=0.8)
    _save_figure(figure, path)


def _plot_volume(dataset: pd.DataFrame, path: Path) -> None:
    figure, axis = plt.subplots(figsize=(9, 4.2))
    axis.plot(dataset["timestamp"], dataset["volume"], color="#17663a", linewidth=1.2)
    axis.set_title("Volume")
    axis.set_xlabel("timestamp")
    axis.set_ylabel("volume")
    axis.grid(axis="y", color="#d9dee7", linewidth=0.8, alpha=0.8)
    _save_figure(figure, path)


def _plot_target_balance(target_balance: pd.DataFrame, path: Path) -> None:
    figure, axis = plt.subplots(figsize=(7.2, 4.0))
    x_positions = range(len(target_balance))
    axis.bar(
        [position - 0.18 for position in x_positions],
        target_balance["target_0_count"],
        width=0.36,
        color="#667085",
        label="target 0",
    )
    axis.bar(
        [position + 0.18 for position in x_positions],
        target_balance["target_1_count"],
        width=0.36,
        color="#175cd3",
        label="target 1",
    )
    axis.set_title("Target balance by horizon")
    axis.set_xlabel("horizon")
    axis.set_ylabel("rows")
    axis.set_xticks(list(x_positions), [str(value) for value in target_balance["horizon"]])
    axis.legend()
    axis.grid(axis="y", color="#d9dee7", linewidth=0.8, alpha=0.8)
    _save_figure(figure, path)


def _plot_volatility(dataset: pd.DataFrame, path: Path) -> None:
    returns = dataset.groupby("symbol", sort=False)["close"].pct_change()
    volatility = returns.rolling(window=24, min_periods=24).std() * 100
    figure, axis = plt.subplots(figsize=(9, 4.2))
    axis.plot(dataset["timestamp"], volatility, color="#b42318", linewidth=1.2)
    axis.set_title("Rolling 24-candle return volatility")
    axis.set_xlabel("timestamp")
    axis.set_ylabel("volatility, %")
    axis.grid(axis="y", color="#d9dee7", linewidth=0.8, alpha=0.8)
    _save_figure(figure, path)


def _save_figure(figure: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.autofmt_xdate()
    figure.tight_layout()
    figure.savefig(path, format="png", dpi=120)
    plt.close(figure)


def _write_report(
    output_doc: Path,
    manifest: dict[str, Any],
    dataset: pd.DataFrame,
    quality: dict[str, Any],
    numeric_summary: pd.DataFrame,
    returns_summary: dict[str, Any],
    target_balance: pd.DataFrame,
    plot_paths: dict[str, Path],
    command_args: argparse.Namespace,
) -> None:
    output_doc.parent.mkdir(parents=True, exist_ok=True)
    symbol = manifest.get("symbol", "unknown")
    interval = manifest.get("interval", "unknown")
    title = f"Real Data EDA: Binance {symbol} {interval}"

    markdown = [
        f"# {title}",
        "",
        "## Purpose",
        "",
        "This report documents a frozen real Binance OHLCV dataset before using it for",
        "research benchmarks. The goal is descriptive data inspection, not a trading or",
        "profitability claim.",
        "",
        "## Dataset Manifest",
        "",
        _manifest_table(manifest),
        "",
        "The dataset file itself is stored locally under `data/real/`, which is ignored",
        "by git. The manifest records the frozen input parameters and SHA256 hash.",
        "",
        "## Schema And Data Quality",
        "",
        _quality_table(dataset, quality),
        "",
        "## Price And Volume Overview",
        "",
        f"![Close price]({_relative_markdown_path(plot_paths['close'], output_doc)})",
        "",
        f"![Volume]({_relative_markdown_path(plot_paths['volume'], output_doc)})",
        "",
        _dataframe_to_markdown(numeric_summary.reset_index().rename(columns={"index": "column"})),
        "",
        "## Returns Distribution",
        "",
        f"![Returns distribution]({_relative_markdown_path(plot_paths['returns'], output_doc)})",
        "",
        _dict_to_markdown_table(returns_summary),
        "",
        "## Target Balance By Horizon",
        "",
        f"![Target balance]({_relative_markdown_path(plot_paths['target_balance'], output_doc)})",
        "",
        _dataframe_to_markdown(_format_target_balance(target_balance)),
        "",
        "## Volatility Overview",
        "",
        f"![Rolling volatility]({_relative_markdown_path(plot_paths['volatility'], output_doc)})",
        "",
        "The volatility plot shows a rolling 24-candle standard deviation of close",
        "returns. It is a descriptive diagnostic for the selected period only.",
        "",
        "## Leakage Notes",
        "",
        "Target balance is computed by the same `DataCleaner`, `FeatureBuilder`, and",
        "`TargetBuilder` path used by the pipeline. The future close used to create the",
        "binary target is not kept as a model feature. Timestamp, symbol, and target are",
        "not intended to be training features.",
        "",
        "## Limitations",
        "",
        "- This is one symbol, interval, and period.",
        "- Market behavior is non-stationary; descriptive distributions can change.",
        "- Target balance depends on the selected horizon and date range.",
        "- No fees, slippage, execution constraints, or live monitoring are modeled.",
        "- This EDA does not prove market predictability or trading profitability.",
        "",
        "## Reproducibility",
        "",
        "Regenerate this report with:",
        "",
        "```powershell",
        _reproducibility_command(command_args),
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
        ("duplicate_timestamps", manifest.get("duplicate_timestamps")),
        ("created_at_utc", manifest.get("created_at_utc")),
    ]
    return _rows_to_markdown_table(["field", "value"], rows)


def _quality_table(dataset: pd.DataFrame, quality: dict[str, Any]) -> str:
    rows = [
        ("rows", quality["actual_rows"]),
        ("columns", ", ".join(dataset.columns)),
        ("expected_rows", _format_optional(quality["expected_rows"])),
        ("time_gap_count", _format_optional(quality["time_gap_count"])),
        ("duplicate_timestamps", quality["duplicate_timestamps"]),
    ]
    for column, value in quality["missing_values"].items():
        rows.append((f"missing_{column}", value))
    return _rows_to_markdown_table(["check", "value"], rows)


def _format_target_balance(target_balance: pd.DataFrame) -> pd.DataFrame:
    result = target_balance.copy()
    result["positive_rate"] = result["positive_rate"].map(lambda value: f"{value:.4f}")
    return result


def _dict_to_markdown_table(values: dict[str, Any]) -> str:
    return _rows_to_markdown_table(["metric", "value"], values.items())


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


def _format_optional(value: Any) -> str:
    return "-" if value is None else str(value)


def _format_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        if pd.isna(value):
            return "-"
        return f"{value:.6f}"
    return str(value)


def _relative_markdown_path(path: Path, output_doc: Path) -> str:
    return path.resolve().relative_to(output_doc.parent.resolve()).as_posix()


def _reproducibility_command(args: argparse.Namespace) -> str:
    return (
        ".crypto\\Scripts\\python.exe scripts\\generate_real_data_eda.py "
        f"--dataset {args.dataset} "
        f"--manifest {args.manifest} "
        f"--output-doc {args.output_doc} "
        f"--output-dir {args.output_dir} "
        f"--horizons {args.horizons}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
