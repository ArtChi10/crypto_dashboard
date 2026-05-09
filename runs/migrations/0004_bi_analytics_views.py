from django.db import migrations


DROP_BI_VIEWS_SQL = (
    "DROP VIEW IF EXISTS bi_confusion_matrix;",
    "DROP VIEW IF EXISTS bi_artifacts;",
    "DROP VIEW IF EXISTS bi_run_metrics;",
)


POSTGRESQL_BI_RUN_METRICS_SQL = """
CREATE VIEW bi_run_metrics AS
SELECT
    r.id AS run_id,
    r.name AS run_name,
    r.status,
    r.symbols_json::text AS symbols_json,
    r.interval,
    r.target_horizon,
    r.started_at,
    r.finished_at,
    r.created_at,
    m.model_type,
    m.accuracy,
    m.precision,
    m.recall,
    m.f1,
    m.roc_auc,
    m.created_at AS metrics_created_at,
    (r.status = 'success') AS is_success
FROM runs_pipelinerun r
LEFT JOIN runs_metricsnapshot m ON m.run_id = r.id;
"""


SQLITE_BI_RUN_METRICS_SQL = """
CREATE VIEW bi_run_metrics AS
SELECT
    r.id AS run_id,
    r.name AS run_name,
    r.status,
    r.symbols_json AS symbols_json,
    r.interval,
    r.target_horizon,
    r.started_at,
    r.finished_at,
    r.created_at,
    m.model_type,
    m.accuracy,
    m.precision,
    m.recall,
    m.f1,
    m.roc_auc,
    m.created_at AS metrics_created_at,
    CASE WHEN r.status = 'success' THEN 1 ELSE 0 END AS is_success
FROM runs_pipelinerun r
LEFT JOIN runs_metricsnapshot m ON m.run_id = r.id;
"""


BI_ARTIFACTS_SQL = """
CREATE VIEW bi_artifacts AS
SELECT
    r.id AS run_id,
    r.name AS run_name,
    r.status,
    'dataset' AS artifact_family,
    d.artifact_type AS artifact_type,
    NULL AS model_type,
    NULL AS report_type,
    d.file_path,
    d.row_count,
    d.created_at
FROM runs_datasetartifact d
JOIN runs_pipelinerun r ON r.id = d.run_id
UNION ALL
SELECT
    r.id AS run_id,
    r.name AS run_name,
    r.status,
    'model' AS artifact_family,
    NULL AS artifact_type,
    m.model_type AS model_type,
    NULL AS report_type,
    m.file_path,
    NULL AS row_count,
    m.created_at
FROM runs_modelartifact m
JOIN runs_pipelinerun r ON r.id = m.run_id
UNION ALL
SELECT
    r.id AS run_id,
    r.name AS run_name,
    r.status,
    'report' AS artifact_family,
    NULL AS artifact_type,
    NULL AS model_type,
    rp.report_type AS report_type,
    rp.file_path,
    NULL AS row_count,
    rp.created_at
FROM runs_reportartifact rp
JOIN runs_pipelinerun r ON r.id = rp.run_id;
"""


POSTGRESQL_BI_CONFUSION_MATRIX_SQL = """
CREATE VIEW bi_confusion_matrix AS
SELECT
    r.id AS run_id,
    r.name AS run_name,
    r.status,
    m.model_type,
    CASE
        WHEN jsonb_typeof(m.confusion_matrix_json) = 'array'
        THEN (m.confusion_matrix_json->0->>0)::int
        ELSE NULL
    END AS tn,
    CASE
        WHEN jsonb_typeof(m.confusion_matrix_json) = 'array'
        THEN (m.confusion_matrix_json->0->>1)::int
        ELSE NULL
    END AS fp,
    CASE
        WHEN jsonb_typeof(m.confusion_matrix_json) = 'array'
        THEN (m.confusion_matrix_json->1->>0)::int
        ELSE NULL
    END AS fn,
    CASE
        WHEN jsonb_typeof(m.confusion_matrix_json) = 'array'
        THEN (m.confusion_matrix_json->1->>1)::int
        ELSE NULL
    END AS tp,
    m.accuracy,
    m.precision,
    m.recall,
    m.f1,
    m.roc_auc,
    m.created_at
FROM runs_pipelinerun r
JOIN runs_metricsnapshot m ON m.run_id = r.id;
"""


SQLITE_BI_CONFUSION_MATRIX_SQL = """
CREATE VIEW bi_confusion_matrix AS
SELECT
    r.id AS run_id,
    r.name AS run_name,
    r.status,
    m.model_type,
    json_extract(m.confusion_matrix_json, '$[0][0]') AS tn,
    json_extract(m.confusion_matrix_json, '$[0][1]') AS fp,
    json_extract(m.confusion_matrix_json, '$[1][0]') AS fn,
    json_extract(m.confusion_matrix_json, '$[1][1]') AS tp,
    m.accuracy,
    m.precision,
    m.recall,
    m.f1,
    m.roc_auc,
    m.created_at
FROM runs_pipelinerun r
JOIN runs_metricsnapshot m ON m.run_id = r.id;
"""


def create_bi_views(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    run_metrics_sql = (
        POSTGRESQL_BI_RUN_METRICS_SQL
        if vendor == "postgresql"
        else SQLITE_BI_RUN_METRICS_SQL
    )
    confusion_matrix_sql = (
        POSTGRESQL_BI_CONFUSION_MATRIX_SQL
        if vendor == "postgresql"
        else SQLITE_BI_CONFUSION_MATRIX_SQL
    )

    with schema_editor.connection.cursor() as cursor:
        for statement in DROP_BI_VIEWS_SQL:
            cursor.execute(statement)
        cursor.execute(run_metrics_sql)
        cursor.execute(BI_ARTIFACTS_SQL)
        cursor.execute(confusion_matrix_sql)


def drop_bi_views(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        for statement in DROP_BI_VIEWS_SQL:
            cursor.execute(statement)


class Migration(migrations.Migration):
    dependencies = [
        ("runs", "0003_alter_reportartifact_report_type"),
    ]

    operations = [
        migrations.RunPython(create_bi_views, reverse_code=drop_bi_views),
    ]
