# Final Regression Checklist

## 1. Purpose

This checklist defines the final regression pass for the current MVP. It covers
automatic checks, manual UI checks, CLI checks, expected artifacts, and known
non-production limitations.

Use it before tagging, publishing, or presenting a stable project snapshot.

## 2. Automated Checks

Run from the project root:

```powershell
.crypto\Scripts\python.exe manage.py check
.crypto\Scripts\python.exe -m ruff check .
.crypto\Scripts\python.exe -m ruff format --check .
.crypto\Scripts\python.exe -m unittest discover
```

Expected result:

- Django system check reports no issues.
- Ruff check passes.
- Ruff format check reports all files already formatted.
- Unit test discovery passes.

Optional environment sanity check:

```powershell
.crypto\Scripts\python.exe -c "import os; os.environ['DJANGO_DEBUG']='False'; os.environ['DJANGO_ALLOWED_HOSTS']='localhost,127.0.0.1,testserver'; import django; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); from django.conf import settings; print(settings.DEBUG); print(settings.ALLOWED_HOSTS)"
```

Expected result:

- `DEBUG` prints `False`.
- `ALLOWED_HOSTS` includes `localhost`, `127.0.0.1`, and `testserver`.

## 3. UI Manual Checks

Start the local server:

```powershell
.crypto\Scripts\python.exe manage.py runserver
```

Check the following pages:

- Dashboard: `http://127.0.0.1:8000/`
  - page loads;
  - navigation links are visible;
  - recent runs table renders.
- CSV upload: `http://127.0.0.1:8000/upload/`
  - form loads;
  - valid OHLCV CSV can create and run a pipeline;
  - invalid input fails without a white-screen error.
- Binance pipeline: `http://127.0.0.1:8000/binance/`
  - form loads;
  - short real-network run can create a successful or failed `PipelineRun`
    with visible status;
  - both model flags cannot be disabled at the same time.
- Runs list: `http://127.0.0.1:8000/runs/`
  - run table renders;
  - successful and failed statuses are visually distinguishable.
- Run detail: `http://127.0.0.1:8000/runs/<id>/`
  - run metadata renders;
  - dataset artifacts are listed;
  - model artifacts are listed;
  - metrics are rounded and readable;
  - report images render inline for PNG reports;
  - stability table preview appears when `stability_table` exists;
  - artifact links point to media URLs when paths are safe.

## 4. CLI Checks

CSV pipeline:

```powershell
.crypto\Scripts\python.exe manage.py run_csv_pipeline --csv data/samples/sample_ohlcv.csv --symbol BTCUSDT --interval 1h --start-date 2024-01-01 --end-date 2024-01-10 --target-horizon 3 --skip-catboost
```

Expected:

- command is available;
- works offline with the committed synthetic sample dataset;
- creates a `PipelineRun`;
- creates raw, processed, and final dataset artifacts;
- creates selected model artifacts and metric snapshots;
- creates report artifacts.

Binance pipeline:

```powershell
.crypto\Scripts\python.exe manage.py run_binance_pipeline --symbol BTCUSDT --interval 1h --start-date 2024-01-01 --end-date 2024-01-10 --target-horizon 3 --skip-catboost
```

Expected:

- command is available;
- downloads OHLCV data from Binance when network/API access is available;
- creates a `PipelineRun`;
- persists raw Binance data as a dataset artifact;
- runs the selected pipeline components.

Research evaluation:

```powershell
.crypto\Scripts\python.exe manage.py run_research_evaluation --dataset tmp_research_check/final.parquet --output-dir tmp_research_check/out --trainer dummy --run-walk-forward --run-ablation --train-window 40 --test-window 20
```

Expected:

- command is available;
- loads a final `.parquet` or `.csv` dataset;
- writes `walk_forward_dummy.csv` when `--run-walk-forward` is enabled;
- writes `ablation_dummy.csv` when `--run-ablation` is enabled;
- does not create Django metadata.

## 5. Expected Artifacts

For a full successful pipeline run with dummy, baseline, and CatBoost enabled:

Dataset artifacts:

- `raw`
- `processed`
- `final`

Model artifacts:

- `dummy`
- `baseline`
- `catboost`

Metric snapshots:

- `dummy`
- `baseline`
- `catboost`

Report artifacts:

- `target_distribution`
- `metrics_plot`
- `feature_importance`
- `stability_table`
- `stability_plot`

Expected storage:

- metadata in SQLite;
- datasets in `media/datasets/`;
- models in `media/models/`;
- reports in `media/reports/`.

## 6. Known Non-Production Limitations

- UI pipeline execution is synchronous.
- Artifacts are stored on the local filesystem.
- SQLite is used for metadata.
- There is no async task queue.
- There is no production deployment setup.
- There is no live trading, order execution, transaction cost modeling, or
  asset allocation management.
- High metrics on short historical periods can be misleading.
- Walk-forward evaluation and feature ablation are offline research utilities,
  not first-class dashboard reports.

## 7. Current Last Verified Status

- Date: 2026-05-02
- Automated checks: passed during the latest documentation/update tasks.
- Manual UI checks: latest known passed from prior manual phases and screenshot
  capture; rerun before any final release tag.
- CLI checks: latest known passed for CSV pipeline, Binance pipeline help/flows,
  and research evaluation smoke checks; rerun with fresh data before release.
- Notes:
  - Binance checks depend on external network/API availability.
  - Local manual/test artifacts are ignored by git.
  - This checklist is a regression guide, not a production certification.
