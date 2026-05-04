# Real Data Dataset Manifest

This document describes how to freeze a real Binance OHLCV dataset for local
research benchmarks.

The project can fetch Binance data live through the UI and CLI, but larger
research runs should not depend on a fresh network request every time. A frozen
dataset gives each experiment a stable input file, a recorded date range, and a
SHA256 checksum that can be checked later.

## Storage Policy

Frozen real datasets are written to:

```text
data/real/
```

This folder is ignored by git. Real market datasets can become large, can be
recreated from Binance, and should not be mixed with the small committed
synthetic sample dataset under `data/samples/`.

## Recommended Benchmark Dataset

The recommended first real-data benchmark is:

```text
symbol: BTCUSDT
interval: 1h
start_date: 2025-01-01
end_date: 2025-07-01
source: Binance Spot klines
```

This is real market data for research benchmarking. It is not evidence of
trading profitability and does not prove that a model can predict live market
behavior.

## Freeze Command

Run from the repository root:

```powershell
.crypto\Scripts\python.exe scripts\freeze_binance_dataset.py --symbol BTCUSDT --interval 1h --start-date 2025-01-01 --end-date 2025-07-01 --output-dir data\real
```

For a shorter smoke check:

```powershell
.crypto\Scripts\python.exe scripts\freeze_binance_dataset.py --symbol BTCUSDT --interval 1h --start-date 2025-01-01 --end-date 2025-01-10 --output-dir data\real
```

The script writes:

```text
data/real/binance_BTCUSDT_1h_2025-01-01_2025-07-01.parquet
data/real/binance_BTCUSDT_1h_2025-01-01_2025-07-01.manifest.json
```

It also prints:

```text
Saved dataset: ...
Saved manifest: ...
Rows: ...
SHA256: ...
```

## Manifest Fields

Each manifest JSON contains:

```json
{
  "source": "binance_spot_klines",
  "symbol": "BTCUSDT",
  "interval": "1h",
  "start_date": "2025-01-01",
  "end_date": "2025-07-01",
  "file_path": "data/real/binance_BTCUSDT_1h_2025-01-01_2025-07-01.parquet",
  "file_sha256": "...",
  "rows": 0,
  "columns": [],
  "timestamp_min": "...",
  "timestamp_max": "...",
  "missing_values": {},
  "duplicate_timestamps": 0,
  "created_at_utc": "..."
}
```

Field meanings:

- `source`: data source identifier.
- `symbol`, `interval`, `start_date`, `end_date`: request parameters.
- `file_path`: local ignored parquet path.
- `file_sha256`: SHA256 hash of the saved parquet file.
- `rows`, `columns`: saved dataset shape.
- `timestamp_min`, `timestamp_max`: actual timestamp range in the saved file.
- `missing_values`: per-column missing value counts.
- `duplicate_timestamps`: repeated timestamp count.
- `created_at_utc`: manifest creation timestamp in UTC.

## Verification

Confirm the frozen outputs stay local:

```powershell
git check-ignore -v data\real\
git status --short
```

`git status --short` should not show generated parquet or manifest files from
`data/real/`.
