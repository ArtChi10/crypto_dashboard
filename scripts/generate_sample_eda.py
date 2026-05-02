from __future__ import annotations

from pathlib import Path

import pandas as pd
from matplotlib.figure import Figure

from mlcore.features.feature_builder import FeatureBuilder
from mlcore.preprocessing.data_cleaner import DataCleaner
from mlcore.targets.target_builder import TargetBuilder

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PATH = ROOT / "data" / "samples" / "sample_ohlcv.csv"
OUTPUT_DIR = ROOT / "docs" / "assets" / "eda"


def build_final_dataset(raw_df: pd.DataFrame, horizon: int = 3) -> pd.DataFrame:
    cleaned = DataCleaner().clean(raw_df)
    features = FeatureBuilder().build(cleaned)
    return TargetBuilder().build(features, horizon=horizon)


def save_close_plot(df: pd.DataFrame, path: Path) -> None:
    fig = Figure(figsize=(10, 4))
    ax = fig.subplots()
    ax.plot(df["timestamp"], df["close"], linewidth=1.8, color="#2563eb")
    ax.set_title("Sample close price")
    ax.set_xlabel("Timestamp")
    ax.set_ylabel("Close")
    ax.grid(alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=140)


def save_returns_plot(df: pd.DataFrame, path: Path) -> None:
    returns = df["close"].pct_change().dropna()
    fig = Figure(figsize=(8, 4))
    ax = fig.subplots()
    ax.hist(returns, bins=30, color="#059669", edgecolor="white")
    ax.set_title("Sample close-to-close returns distribution")
    ax.set_xlabel("Return")
    ax.set_ylabel("Count")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=140)


def save_target_plot(final_df: pd.DataFrame, path: Path) -> None:
    counts = final_df["target"].value_counts().sort_index()
    labels = [str(int(label)) for label in counts.index]

    fig = Figure(figsize=(6, 4))
    ax = fig.subplots()
    bars = ax.bar(labels, counts.values, color=["#64748b", "#dc2626"])
    ax.set_title("Target distribution after feature/target pipeline")
    ax.set_xlabel("Target")
    ax.set_ylabel("Rows")
    ax.grid(axis="y", alpha=0.25)
    ax.bar_label(bars)
    fig.tight_layout()
    fig.savefig(path, dpi=140)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    raw_df = pd.read_csv(SAMPLE_PATH)
    raw_df["timestamp"] = pd.to_datetime(raw_df["timestamp"])
    for column in ("open", "high", "low", "close", "volume"):
        raw_df[column] = pd.to_numeric(raw_df[column])

    final_df = build_final_dataset(raw_df)

    save_close_plot(raw_df, OUTPUT_DIR / "sample_close.png")
    save_returns_plot(raw_df, OUTPUT_DIR / "sample_returns_distribution.png")
    save_target_plot(final_df, OUTPUT_DIR / "sample_target_distribution.png")

    print(f"rows={len(raw_df)}")
    print(f"columns={list(raw_df.columns)}")
    print(f"timestamp_min={raw_df['timestamp'].min()}")
    print(f"timestamp_max={raw_df['timestamp'].max()}")
    print(f"symbols={raw_df['symbol'].nunique()}")
    print(f"missing={raw_df.isna().sum().to_dict()}")
    print("numeric_summary=")
    print(raw_df[["open", "high", "low", "close", "volume"]].describe().round(4).to_string())
    print("returns_summary=")
    print(raw_df["close"].pct_change().dropna().describe().round(6).to_string())
    print(f"final_rows={len(final_df)}")
    print(f"target_counts={final_df['target'].value_counts().sort_index().to_dict()}")
    print(f"plots_dir={OUTPUT_DIR.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
