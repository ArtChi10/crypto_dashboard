from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mlcore.loaders.binance_loader import BinanceMarketDataProvider  # noqa: E402


def main() -> int:
    args = _parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset_stem = _dataset_stem(
        symbol=args.symbol,
        interval=args.interval,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    dataset_path = output_dir / f"{dataset_stem}.parquet"
    manifest_path = output_dir / f"{dataset_stem}.manifest.json"

    provider = BinanceMarketDataProvider()
    dataset = provider.get_ohlcv(
        symbol=args.symbol,
        interval=args.interval,
        start=args.start_date,
        end=args.end_date,
    )
    dataset.to_parquet(dataset_path, index=False)

    file_sha256 = _sha256_file(dataset_path)
    manifest = _build_manifest(
        dataset=dataset,
        dataset_path=dataset_path,
        file_sha256=file_sha256,
        symbol=args.symbol,
        interval=args.interval,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Saved dataset: {dataset_path}")
    print(f"Saved manifest: {manifest_path}")
    print(f"Rows: {manifest['rows']}")
    print(f"SHA256: {file_sha256}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze Binance Spot OHLCV candles into an ignored parquet dataset.",
    )
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--interval", default="1h")
    parser.add_argument("--start-date", default="2025-01-01")
    parser.add_argument("--end-date", default="2025-07-01")
    parser.add_argument("--output-dir", default="data/real")
    return parser.parse_args()


def _dataset_stem(symbol: str, interval: str, start_date: str, end_date: str) -> str:
    return (
        "binance_"
        f"{_safe_token(symbol.upper())}_"
        f"{_safe_token(interval)}_"
        f"{_safe_token(start_date)}_"
        f"{_safe_token(end_date)}"
    )


def _safe_token(value: str) -> str:
    text = str(value).strip()
    return "".join(
        character if character.isalnum() or character in {"-", "_"} else "-" for character in text
    )


def _build_manifest(
    dataset,
    dataset_path: Path,
    file_sha256: str,
    symbol: str,
    interval: str,
    start_date: str,
    end_date: str,
) -> dict[str, object]:
    timestamp = dataset["timestamp"] if "timestamp" in dataset.columns else None
    timestamp_min = (
        timestamp.min().isoformat() if timestamp is not None and not dataset.empty else None
    )
    timestamp_max = (
        timestamp.max().isoformat() if timestamp is not None and not dataset.empty else None
    )
    duplicate_timestamps = (
        int(dataset["timestamp"].duplicated().sum()) if "timestamp" in dataset.columns else 0
    )

    return {
        "source": "binance_spot_klines",
        "symbol": symbol.upper(),
        "interval": interval,
        "start_date": start_date,
        "end_date": end_date,
        "file_path": dataset_path.as_posix(),
        "file_sha256": file_sha256,
        "rows": int(len(dataset)),
        "columns": list(dataset.columns),
        "timestamp_min": timestamp_min,
        "timestamp_max": timestamp_max,
        "missing_values": {
            column: int(value) for column, value in dataset.isna().sum().to_dict().items()
        },
        "duplicate_timestamps": duplicate_timestamps,
        "created_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
