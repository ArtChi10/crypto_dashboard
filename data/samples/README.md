# Sample OHLCV Dataset

`sample_ohlcv.csv` is a small deterministic synthetic OHLCV dataset for offline
demo and smoke-check runs.

It is intentionally committed to git so the project can be exercised without
Binance/network access. The file uses the same schema expected by the CSV
pipeline:

- `timestamp`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `symbol`

The close series is non-monotonic so target generation can produce both classes
for short-horizon binary classification. This dataset is not real market data
and must not be used for claims about market predictability or model quality.
