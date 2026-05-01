# Crypto Dashboard

Crypto Dashboard is a Django-based research/MVP application for running and
tracking ML pipeline experiments on cryptocurrency OHLCV data.

The project is not a trading bot and is not production-ready trading software.
It is a reproducible research pipeline with UI, CLI entry points, saved
artifacts, metrics, and reports.

## MVP Status

- CSV pipeline: implemented via `/upload/` and `manage.py run_csv_pipeline`.
- Binance pipeline: implemented via `/binance/` and `manage.py run_binance_pipeline`.
- Dataset artifacts: implemented for raw, processed, and final datasets.
- Model artifacts: implemented for LogisticRegression baseline and CatBoost.
- Metrics: implemented for binary classification snapshots.
- Reports: implemented for target distribution, metrics comparison, and CatBoost
  feature importance PNG reports.
- Run detail page: implemented with artifact links, metric summaries, and inline
  PNG report display.
- Research layer: started with a report skeleton. Walk-forward validation,
  stability analysis, ablation study, and stronger out-of-sample analysis are
  still future work.

## Caution

High metrics on a short historical period do not prove market predictability or
profitable behavior. Treat results as experiment outputs that need stronger
validation, broader time ranges, walk-forward testing, and careful research
review before drawing conclusions.

## Main Entry Points

- Dashboard: `/`
- Binance pipeline form: `/binance/`
- CSV upload form: `/upload/`
- Runs list: `/runs/`
- Run detail: `/runs/<id>/`
- Admin: `/admin/`

## Documentation

- [Current usage guide](docs/current_usage_guide.md)
- [Beginner code explanation](docs/beginner_code_explanation.md)
- [Research report skeleton](docs/research_report.md)
