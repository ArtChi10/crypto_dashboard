# Reproducible ML Research Platform for Crypto Price Movement Classification

Django-based research dashboard for running reproducible ML pipelines on
Binance or CSV OHLCV data. The project prepares datasets, trains baseline and
main models, saves local artifacts, records metadata, and provides research
utilities for time-aware model evaluation.

This is a standalone pet/research ML project, not a trading product.

## What This Project Is / Is Not

This project is:

- a reproducible ML pipeline for OHLCV-based binary classification;
- a Django research dashboard for running and inspecting experiments;
- a local experiment tracking system with SQLite metadata and file artifacts;
- a playground for leakage-aware validation, baselines, reports, and research
  checks.

This project is not:

- a trading bot;
- financial advice;
- a production trading system;
- a claim that short-term crypto prices are reliably predictable.

## Features

- CSV raw OHLCV ingestion through UI and CLI.
- Binance Spot OHLCV ingestion through UI and CLI.
- Raw, processed, and final dataset artifacts.
- DummyClassifier naive baseline.
- LogisticRegression baseline with `StandardScaler`.
- CatBoostClassifier main model.
- Binary classification metrics: accuracy, precision, recall, f1, roc_auc, and
  confusion matrix.
- Generated reports:
  - target distribution;
  - metrics comparison;
  - CatBoost feature importance;
  - period stability table and plot.
- Run detail page with artifact links, metric summaries, inline PNG reports, and
  stability table preview.
- Research utilities:
  - period stability analysis;
  - walk-forward fold generation;
  - walk-forward evaluation CLI;
  - feature ablation CLI.

## Screenshots

Dashboard overview:

![Dashboard](docs/assets/screenshots/dashboard.png)

Binance pipeline form:

![Binance pipeline form](docs/assets/screenshots/binance_form.png)

Run detail metrics and stability preview:

![Run detail metrics](docs/assets/screenshots/run_detail_metrics.png)

Run detail report gallery:

![Run detail reports](docs/assets/screenshots/run_detail_reports.png)

## Architecture Overview

```mermaid
flowchart LR
    UI["Django UI / CLI commands"]
    UseCases["Application use cases"]
    MLCore["mlcore services"]
    Repos["Repositories"]
    Media["media/ artifacts"]
    DB["SQLite metadata"]

    UI --> UseCases
    UseCases --> MLCore
    MLCore --> Repos
    Repos --> Media
    UseCases --> DB
```

The core design separates Django orchestration from ML logic:

- Django views and management commands handle forms, CLI arguments, redirects,
  and user-facing flow.
- Use cases coordinate complete actions such as CSV upload, Binance pipeline
  runs, and `PipelineRun` execution.
- `mlcore` contains reusable, Django-independent data preparation, training,
  evaluation, reporting, repository, and research services.
- SQLite stores metadata only.
- Datasets, models, and report files are stored in local filesystem artifacts.

## Data / ML Pipeline

```text
raw OHLCV
-> clean
-> build features
-> build target
-> time-based split
-> train dummy / baseline / CatBoost
-> evaluate
-> save models, metrics, datasets, and reports
```

Current target definition:

```text
target = 1 if close(t + horizon) > close(t), else 0
```

The main pipeline uses a global time-based holdout split. Rows are sorted by
`timestamp`; random shuffle is not used.

## Research Components

- Leakage control:
  - no random train/test shuffle;
  - timestamp, symbol, and target are excluded from model features;
  - future close used for target construction is not kept as a model feature.
- Time-based train/validation/test split.
- Dummy baseline for naive majority-class comparison.
- Period stability analysis over test predictions.
- Walk-forward validation service for sequential folds.
- Walk-forward evaluation command for fold-by-fold trainer evaluation.
- Feature ablation service and CLI for comparing feature group removal.

These tools are research aids. They make model behavior easier to inspect, but
they do not prove profitability.

## Quickstart

Generic local setup:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

Optional Django environment variables:

- `DJANGO_SECRET_KEY`: set a local development secret when you do not want to
  use the fallback placeholder;
- `DJANGO_DEBUG`: set to `True` or `False`;
- `DJANGO_ALLOWED_HOSTS`: comma-separated host list, for example local hostnames.

Local development defaults are defined in `config/settings.py`, so the project
can run without a `.env` file. Use `.env.example` as a reference if you want to
set shell-level environment variables. Do not commit a real `.env` file.

This workspace has been developed and checked with a local `.crypto` virtual
environment, so task verification commands use:

```powershell
.crypto\Scripts\python.exe ...
```

## Docker Local Stack

The project also includes a local Docker Compose stack with Django and
PostgreSQL. It is intended for local containerized testing, not server
deployment.

```powershell
docker compose build
docker compose up
```

Open:

```text
http://localhost:8000/
```

Stop the stack:

```powershell
docker compose down
```

Docker uses PostgreSQL through `DATABASE_URL`. The local `.crypto` workflow
continues to use SQLite unless `DATABASE_URL` is set in the shell environment.

## Deployment

The repository includes:

- GitHub Actions CI for Django checks, Ruff checks, and Django tests;
- an optional SSH deployment workflow in `.github/workflows/deploy.yml`;
- production-oriented Docker Compose files for Django, PostgreSQL, Caddy,
  persistent media, and collected static files.

The SSH deployment workflow is configured through GitHub Secrets and is intended
for the server setup described in the [deployment guide](docs/deployment_guide.md).
The server-only `.env.production` file stays on the server and is not committed.

## Offline Demo Dataset

The repository includes a small deterministic synthetic OHLCV dataset for
offline demos:

```text
data/samples/sample_ohlcv.csv
```

It follows the expected CSV schema and does not require Binance/network access.
It is useful for smoke checks and local demonstrations only; it is not real
market data and must not be used for performance claims.

See the [sample dataset EDA report](docs/eda_sample_dataset.md) for schema,
missing values, summary statistics, returns distribution, and target balance
after the current feature/target pipeline.

See the [sample experiment summary](docs/experiment_summary_sample.md) for a
recorded pipeline run on this dataset, including parameters, artifacts, metrics,
confusion matrices, and stability output.

Run the CSV pipeline on the sample dataset:

```powershell
.crypto\Scripts\python.exe manage.py run_csv_pipeline --csv data/samples/sample_ohlcv.csv --symbol BTCUSDT --interval 1h --start-date 2024-01-01 --end-date 2024-01-10 --target-horizon 3
```

Generic equivalent:

```powershell
python manage.py run_csv_pipeline --csv data/samples/sample_ohlcv.csv --symbol BTCUSDT --interval 1h --start-date 2024-01-01 --end-date 2024-01-10 --target-horizon 3
```

## Running Pipelines

CSV through UI:

```text
http://127.0.0.1:8000/upload/
```

Binance through UI:

```text
http://127.0.0.1:8000/binance/
```

CSV through CLI:

```powershell
.crypto\Scripts\python.exe manage.py run_csv_pipeline --csv tmp_cli_check/input.csv --symbol BTCUSDT --interval 1h --start-date 2024-01-01 --end-date 2024-01-05 --target-horizon 3
```

Binance through CLI:

```powershell
.crypto\Scripts\python.exe manage.py run_binance_pipeline --symbol BTCUSDT --interval 1h --start-date 2024-01-01 --end-date 2024-01-10 --target-horizon 3 --skip-catboost
```

Both UI flows are synchronous in the current MVP.

## Running Research Evaluation

Run offline research checks on an existing final dataset:

```powershell
.crypto\Scripts\python.exe manage.py run_research_evaluation --dataset tmp_research_check/final.parquet --output-dir tmp_research_check/out --trainer dummy --run-walk-forward --run-ablation --train-window 40 --test-window 20
```

Supported research CLI trainers:

- `dummy`
- `baseline`
- `catboost`

Outputs:

- `walk_forward_<trainer>.csv`
- `ablation_<trainer>.csv`

CatBoost research evaluation uses lighter CLI parameters than the main pipeline,
but it can still be slower than `dummy` or `baseline`. Use the simpler trainers
for quick checks.

## Outputs

SQLite metadata:

- `PipelineRun`
- `DatasetArtifact`
- `ModelArtifact`
- `MetricSnapshot`
- `ReportArtifact`

Filesystem artifacts:

- `media/datasets/raw/`
- `media/datasets/processed/`
- `media/datasets/final/`
- `media/models/`
- `media/reports/`

The database stores paths and metadata. Large datasets, models, and reports stay
as files.

## Tests and Code Quality

```powershell
.crypto\Scripts\python.exe manage.py check
.crypto\Scripts\python.exe -m ruff check .
.crypto\Scripts\python.exe -m ruff format --check .
.crypto\Scripts\python.exe manage.py test
```

GitHub Actions CI runs the same Django check, Ruff checks, and Django test
runner on push and pull request events. The optional SSH deployment workflow can
update the configured Docker Compose server after successful checks on `main`.

## Current Limitations

- No async/background queue yet; UI pipeline runs are synchronous.
- Local filesystem artifact storage only.
- HTTPS is not configured yet.
- Server deployment is Docker Compose based; no managed platform setup is
  included.
- No live trading, order execution, asset allocation logic, fees, slippage, or
  transaction cost modeling.
- High metrics on a short historical period can be misleading.
- The main pipeline still uses a single holdout split; walk-forward evaluation is
  currently an offline research command.
- Feature ablation is available as offline research output, not yet as a
  first-class dashboard report.
- Binance availability depends on network access and Binance API behavior.

## Documentation

- [Current usage guide](docs/current_usage_guide.md)
- [Beginner code explanation](docs/beginner_code_explanation.md)
- [Deployment guide](docs/deployment_guide.md)
- [Research report](docs/research_report.md)
- [Model card](docs/model_card.md)
- [Sample dataset EDA report](docs/eda_sample_dataset.md)
- [Sample experiment summary](docs/experiment_summary_sample.md)
- [Storage architecture](docs/storage_architecture.md)
- [Final regression checklist](docs/final_regression_checklist.md)
- [Release readiness summary](docs/release_readiness.md)
- [GitHub publication checklist](docs/github_publication_checklist.md)

## Engineering Highlights

- Clear separation between Django UI/orchestration and Django-independent ML
  services.
- Reproducible local artifacts with SQLite metadata.
- Time-aware validation and explicit leakage control.
- Baseline discipline: dummy baseline, LogisticRegression baseline, CatBoost
  main model.
- Practical research tooling: period stability, walk-forward evaluation, and
  feature ablation.
- Honest limitations: no profitability claims, no live trading, and no
  production-ready deployment story.
