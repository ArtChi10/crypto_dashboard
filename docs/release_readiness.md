# Release Readiness Summary

## 1. Status

| Item | Status |
| --- | --- |
| Current version | MVP research dashboard |
| Ready for local demo | Yes |
| Ready for production trading | No |

This document summarizes the current project state. It is a readiness snapshot
for local demonstration and reproducible research workflow review, not a
production release note.

## 2. Implemented Capabilities

Implemented capabilities:

- CSV pipeline through UI and CLI;
- Binance pipeline through UI and CLI;
- committed synthetic sample dataset for offline demo;
- dataset preparation with raw, processed, and final artifacts;
- model training for dummy baseline, LogisticRegression baseline, and CatBoost;
- binary classification metrics and confusion matrices;
- report artifacts:
  - target distribution;
  - metrics comparison;
  - feature importance;
  - period stability table;
  - period stability plot;
- run detail page with artifact links, metric summaries, report images, and
  stability preview;
- research tools:
  - period stability analysis;
  - walk-forward validation;
  - walk-forward evaluation command;
  - feature ablation command;
- environment-based Django settings with `.env.example`;
- local Docker Compose stack with Django, PostgreSQL, static collection, and
  persistent media volume;
- production-oriented Docker Compose files for HTTP server deployment with
  Django, PostgreSQL, Caddy, and persistent volumes;
- GitHub Actions CI for checks and tests.

## 3. Verification Snapshot

Latest local verification commands:

```powershell
.crypto\Scripts\python.exe manage.py check
.crypto\Scripts\python.exe -m ruff check .
.crypto\Scripts\python.exe -m ruff format --check .
.crypto\Scripts\python.exe -m unittest discover
```

Latest known local results:

| Check | Result |
| --- | --- |
| Django system check | Passed |
| Ruff check | Passed |
| Ruff format check | Passed |
| Unit tests | Passed |
| Git status | Clean |
| CI workflow | Configured |
| Docker Compose local stack | Configured |
| Production Compose config | Configured |

CI is configured in `.github/workflows/ci.yml` for `push` and `pull_request`
events. It runs Django check, Ruff check, Ruff format check, and unittest
discovery on Python 3.12.

## 4. Reproducible Demo Paths

Offline sample dataset command:

```powershell
.crypto\Scripts\python.exe manage.py run_csv_pipeline --csv data/samples/sample_ohlcv.csv --symbol BTCUSDT --interval 1h --start-date 2024-01-01 --end-date 2024-01-10 --target-horizon 3
```

Binance UI path:

```text
http://127.0.0.1:8000/binance/
```

Research evaluation command:

```powershell
.crypto\Scripts\python.exe manage.py run_research_evaluation --dataset tmp_research_check/final.parquet --output-dir tmp_research_check/out --trainer dummy --run-walk-forward --run-ablation --train-window 40 --test-window 20
```

The offline sample dataset is synthetic and deterministic. It is intended for
smoke checks and local reproducibility, not market-performance claims.

## 5. Public Documentation

Current public documentation:

- [`README.md`](../README.md);
- [`docs/current_usage_guide.md`](current_usage_guide.md);
- [`docs/research_report.md`](research_report.md);
- [`docs/model_card.md`](model_card.md);
- [`docs/eda_sample_dataset.md`](eda_sample_dataset.md);
- [`docs/experiment_summary_sample.md`](experiment_summary_sample.md);
- [`docs/final_regression_checklist.md`](final_regression_checklist.md);
- [`docs/storage_architecture.md`](storage_architecture.md);
- [`docs/beginner_code_explanation.md`](beginner_code_explanation.md).

## 6. Known Limitations

Known limitations:

- UI pipeline execution is synchronous;
- local `.crypto` workflow uses SQLite metadata unless `DATABASE_URL` is set;
- Docker local stack uses PostgreSQL;
- production-oriented compose files are present, but HTTPS is not configured
  yet;
- datasets, models, and reports use local filesystem or Docker volume storage;
- no HTTPS setup is included;
- no live trading, order execution, portfolio allocation, or monitoring;
- no transaction costs, fees, spreads, slippage, or latency modeling;
- metrics are research signals and pipeline checks, not profitability claims;
- Binance workflows depend on network access and Binance API availability;
- walk-forward and ablation tools are currently offline utilities, not
  first-class dashboard reports.

## 7. Future Work

Potential future work:

- richer real-market experiments across symbols, intervals, horizons, and
  calendar periods;
- model calibration and probability quality analysis;
- confidence intervals or metric variance across folds;
- drift monitoring and data quality alerts;
- dashboard integration for walk-forward and ablation outputs;
- server deployment packaging if needed;
- optional background task queue for longer runs.
