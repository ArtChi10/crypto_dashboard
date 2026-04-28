# Storage architecture for datasets, models and reports

## Goal

Separate the metadata database from large data files and model/report artifacts.

Core rule: **SQLite = metadata only**.

SQLite stores records that describe runs and artifacts. Large datasets, trained
models, plots, and reports are stored in the filesystem under `media/`.

## SQLite responsibility

SQLite stores only metadata:

- pipeline runs;
- run parameters;
- run statuses;
- paths to generated artifacts;
- dataset row counts;
- metric snapshots;
- error messages and failure details;
- creation and update timestamps.

The database must contain enough information to find, audit, and compare
artifacts, but it must not contain the artifact payloads themselves.

## Filesystem responsibility

Large data is not stored in SQLite.

The following artifact payloads are stored in the filesystem:

- raw OHLCV data;
- processed datasets;
- final feature/target datasets;
- trained models;
- plots;
- reports.

The database stores only paths and metadata for these files.

## Directory structure

All file artifacts live under `media/`:

```text
media/
  datasets/
    raw/
    processed/
    final/
  models/
  reports/
```

Expected usage:

- `media/datasets/raw/` stores raw downloaded or manually uploaded OHLCV
  datasets;
- `media/datasets/processed/` stores cleaned or transformed intermediate
  datasets;
- `media/datasets/final/` stores final feature/target datasets used for model
  training and evaluation;
- `media/models/` stores trained model artifacts;
- `media/reports/` stores plots, metric JSON files, markdown summaries, and
  other report artifacts.

Artifact paths saved in SQLite should be relative to the project `media/`
directory, for example `datasets/raw/raw_run_12_BTCUSDT_20260427_120501.parquet`.
Relative paths keep the metadata portable across local, staging, and production
deployments.

## File formats

Dataset formats:

- Internal dataset format: `parquet`.
- `csv` is allowed only for manual upload, manual inspection, and export.
- CSV should not be the default internal exchange format between pipeline
  stages.

Model formats:

- General Python models: `joblib` or `pkl`.
- CatBoost models may use native `cbm` files when needed.

Report and plot formats:

- plots: `png`;
- machine-readable metrics or report data: `json`;
- human-readable summaries or notes: `md` when needed.

## File naming rules

File names must be deterministic, readable, and safe for storage:

- use lowercase artifact prefixes such as `raw`, `processed`, `final`, `model`,
  `metrics`, `feature_importance`;
- include `run_id` for every artifact created by a pipeline run;
- include `symbol` for symbol-specific dataset artifacts;
- use uppercase trading symbols, for example `BTCUSDT`;
- use timestamps in `YYYYMMDD_HHMMSS` format;
- do not use spaces;
- do not overwrite existing artifacts from previous runs.

Recommended patterns:

```text
media/datasets/raw/raw_run_{run_id}_{symbol}_{YYYYMMDD_HHMMSS}.parquet
media/datasets/processed/processed_run_{run_id}_{symbol}_{YYYYMMDD_HHMMSS}.parquet
media/datasets/final/final_run_{run_id}_{YYYYMMDD_HHMMSS}.parquet
media/models/model_{model_type}_run_{run_id}.joblib
media/models/model_{model_type}_run_{run_id}.pkl
media/models/model_catboost_run_{run_id}.cbm
media/reports/metrics_run_{run_id}_{model_type}.json
media/reports/feature_importance_run_{run_id}.png
media/reports/report_run_{run_id}_{report_type}.md
```

Examples:

```text
raw_run_12_BTCUSDT_20260427_120501.parquet
processed_run_12_BTCUSDT_20260427_120612.parquet
final_run_12_20260427_120733.parquet
model_baseline_run_12.joblib
model_catboost_run_12.cbm
metrics_run_12_catboost.json
feature_importance_run_12.png
```

## Development environment note

Local Django and Python commands for this project should use the `.crypto`
virtual environment, for example `.crypto\Scripts\python.exe manage.py ...`.

The virtual environment is not part of artifact storage. Dataset, model, and
report paths saved in SQLite must still point to files under `media/`, not to
files under `.crypto/` or `.venv/`.

## Compatibility with current Django models

This section reviews the current models from `runs/models.py`.

### PipelineRun

Status: suitable for the metadata-only storage architecture.

Current fields cover:

- run identity via `name`;
- status via `status`;
- lifecycle timestamps via `started_at`, `finished_at`, `created_at`,
  `updated_at`;
- core run parameters via `symbols_json`, `interval`, `start_date`, `end_date`,
  and `target_horizon`;
- operator/source metadata via `initiated_by`;
- error details via `error_message`.

Recommendation for a future task: add a run-level `params_json` only if pipeline
parameters become more dynamic than the current explicit fields. This is not a
critical blocker for the storage layer.

### DatasetArtifact

Status: suitable.

Current fields cover the required storage metadata:

- `file_path` is present;
- `artifact_type` is present and separates `raw`, `processed`, and `final`;
- `symbol` is present for symbol-specific datasets;
- `row_count` is present;
- `run` links the dataset artifact to a pipeline run.

Recommendation for a future task: keep `file_path` values relative to `media/`.
Optional future metadata may include file size, checksum, schema version, or
source type, but these are not required for the current architecture.

### ModelArtifact

Status: suitable for per-run models; may need changes if models become
symbol-specific.

Current fields cover:

- `file_path` for the model artifact location;
- `model_type` for baseline/CatBoost separation;
- `params_json` for model parameters;
- `run` for ownership by a pipeline run.

There is no `symbol` field. This is acceptable if each model is trained for the
whole run or for the run's symbol set from `PipelineRun.symbols_json`. If the
project later trains one model per symbol inside the same run, add an optional
`symbol` field to `ModelArtifact`.

### MetricSnapshot

Status: suitable for current model metrics.

Current fields cover:

- run link via `run`;
- model identity via `model_type`;
- common metrics via `accuracy`, `precision`, `recall`, `f1`, and `roc_auc`;
- structured confusion matrix via `confusion_matrix_json`;
- timestamp via `created_at`.

Recommendation for a future task: if metric sets become dynamic, add a generic
`metrics_json` field or store detailed metric payloads as JSON report artifacts
under `media/reports/`.

### ReportArtifact

Status: suitable.

Current fields cover:

- `file_path` for report or plot location;
- `report_type` for report classification;
- `run` for ownership by a pipeline run;
- timestamp via `created_at`.

Recommendation for a future task: extend `ReportType` choices as new report
kinds appear. No storage architecture change is required.

## Model change decision

Current models are sufficient for the planned metadata-only storage layer.

No critical model changes are required for this task.

Recommended non-blocking future improvements:

- define `MEDIA_ROOT` and `MEDIA_URL` in Django settings;
- store artifact paths relative to `MEDIA_ROOT`;
- optionally add file metadata such as size, checksum, and schema version;
- optionally add `ModelArtifact.symbol` if training becomes per-symbol within a
  single run;
- optionally add run-level `params_json` if run parameters become highly
  dynamic.
