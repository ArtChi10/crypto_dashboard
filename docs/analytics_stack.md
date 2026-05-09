# Analytics Stack: Grafana and Metabase

## Purpose

The production analytics direction is:

```text
Django/PostgreSQL
-> BI SQL views
-> Grafana + Metabase
-> Django Analytics page
```

Grafana and Metabase should read stable BI views instead of querying raw Django
tables directly. The views provide a small reporting contract over pipeline
runs, metrics, artifacts, and confusion matrices.

## Data Contract

The first BI layer is created by Django migrations in the `runs` app. It exposes
read-only SQL views:

- `bi_run_metrics`;
- `bi_artifacts`;
- `bi_confusion_matrix`.

These views are intended for PostgreSQL production. SQLite compatibility exists
so local Django migrations and tests can run, but PostgreSQL is the supported BI
target.

## BI Views

### bi_run_metrics

One row per run/model metric snapshot. Runs without metric snapshots still
appear with metric columns as `NULL`.

Fields:

- `run_id`;
- `run_name`;
- `status`;
- `symbols_json`;
- `interval`;
- `target_horizon`;
- `started_at`;
- `finished_at`;
- `created_at`;
- `model_type`;
- `accuracy`;
- `precision`;
- `recall`;
- `f1`;
- `roc_auc`;
- `metrics_created_at`;
- `is_success`.

Example questions:

- How many successful runs exist by day?
- Which model type has the strongest F1 over recent runs?
- Which runs failed or never produced metrics?

### bi_artifacts

One unioned artifact table across datasets, models, and reports.

Fields:

- `run_id`;
- `run_name`;
- `status`;
- `artifact_family`: `dataset`, `model`, or `report`;
- `artifact_type`;
- `model_type`;
- `report_type`;
- `file_path`;
- `row_count`;
- `created_at`.

Example questions:

- Which runs produced final datasets?
- Which runs have CatBoost model artifacts?
- How many report PNG/CSV artifacts are available?

### bi_confusion_matrix

One row per metric snapshot with the confusion matrix flattened into numeric
columns.

Fields:

- `run_id`;
- `run_name`;
- `status`;
- `model_type`;
- `tn`;
- `fp`;
- `fn`;
- `tp`;
- `accuracy`;
- `precision`;
- `recall`;
- `f1`;
- `roc_auc`;
- `created_at`.

The PostgreSQL view extracts values from `confusion_matrix_json` with JSONB
operators. The SQLite fallback uses `json_extract` for local tests.

## PostgreSQL Production Notes

After deployment, run Django migrations as usual:

```powershell
python manage.py migrate
```

The production views are created in PostgreSQL and can be queried by BI tools:

```sql
SELECT * FROM bi_run_metrics LIMIT 5;
SELECT * FROM bi_artifacts LIMIT 5;
SELECT * FROM bi_confusion_matrix LIMIT 5;
```

Grafana and Metabase should connect with a read-only PostgreSQL user when that
user is added. The views are the intended BI contract; raw Django tables should
remain an implementation detail.

## SQLite Local Notes

Local development and tests use SQLite by default unless `DATABASE_URL` is set.
The BI migration creates SQLite-compatible views so `manage.py test` can run
without PostgreSQL.

SQLite compatibility is for testability only. Production analytics should use
PostgreSQL.

## Next Step: Grafana and Metabase Services

Next work can add self-hosted Grafana and Metabase services to the server
compose stack, then build dashboards from these views.

Suggested first dashboards:

- run success/failure counts;
- metrics by model type;
- artifacts produced by run;
- confusion-matrix false positives and false negatives;
- Forecast Replay report availability.

## Security Notes

- BI tools should not use the Django application database superuser.
- Prefer a read-only PostgreSQL user scoped to BI views.
- Do not expose PostgreSQL directly to the public internet.
- Keep `.env.production` and BI credentials server-only.
- Do not store raw real datasets in git.
