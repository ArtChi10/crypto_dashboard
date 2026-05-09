import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.db import connection
from django.test import TestCase

django.setup()

from runs.models import (  # noqa: E402
    DatasetArtifact,
    MetricSnapshot,
    ModelArtifact,
    PipelineRun,
    ReportArtifact,
)


class BiViewsTests(TestCase):
    def test_bi_views_exist_and_are_queryable(self):
        for view_name in ("bi_run_metrics", "bi_artifacts", "bi_confusion_matrix"):
            with self.subTest(view_name=view_name):
                rows = self._query(f"SELECT * FROM {view_name} WHERE 1 = 0")
                self.assertEqual(rows, [])

    def test_bi_run_metrics_returns_pipeline_and_metric_fields(self):
        run = self._create_run()
        MetricSnapshot.objects.create(
            run=run,
            model_type=ModelArtifact.ModelType.BASELINE,
            accuracy=0.81,
            precision=0.7,
            recall=0.6,
            f1=0.6462,
            roc_auc=0.74,
            confusion_matrix_json=[[7, 1], [2, 3]],
        )

        rows = self._query(
            """
            SELECT
                run_id,
                run_name,
                status,
                interval,
                target_horizon,
                model_type,
                accuracy,
                precision,
                recall,
                f1,
                roc_auc,
                is_success
            FROM bi_run_metrics
            WHERE run_id = %s
            """,
            [run.id],
        )

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["run_id"], run.id)
        self.assertEqual(row["run_name"], "BI test run")
        self.assertEqual(row["status"], PipelineRun.Status.SUCCESS)
        self.assertEqual(row["interval"], "1h")
        self.assertEqual(row["target_horizon"], 3)
        self.assertEqual(row["model_type"], ModelArtifact.ModelType.BASELINE)
        self.assertEqual(row["accuracy"], 0.81)
        self.assertEqual(row["precision"], 0.7)
        self.assertEqual(row["recall"], 0.6)
        self.assertEqual(row["f1"], 0.6462)
        self.assertEqual(row["roc_auc"], 0.74)
        self.assertIn(row["is_success"], (True, 1))

    def test_bi_artifacts_returns_dataset_model_and_report_rows(self):
        run = self._create_run()
        DatasetArtifact.objects.create(
            run=run,
            artifact_type=DatasetArtifact.ArtifactType.FINAL,
            symbol="BTCUSDT",
            file_path="datasets/final/final.parquet",
            row_count=120,
        )
        ModelArtifact.objects.create(
            run=run,
            model_type=ModelArtifact.ModelType.BASELINE,
            file_path="models/baseline.joblib",
        )
        ReportArtifact.objects.create(
            run=run,
            report_type=ReportArtifact.ReportType.METRICS_PLOT,
            file_path="reports/metrics_plot.png",
        )

        rows = self._query(
            """
            SELECT
                artifact_family,
                artifact_type,
                model_type,
                report_type,
                file_path,
                row_count
            FROM bi_artifacts
            WHERE run_id = %s
            ORDER BY artifact_family
            """,
            [run.id],
        )

        by_family = {row["artifact_family"]: row for row in rows}
        self.assertEqual(set(by_family), {"dataset", "model", "report"})
        self.assertEqual(by_family["dataset"]["artifact_type"], DatasetArtifact.ArtifactType.FINAL)
        self.assertEqual(by_family["dataset"]["file_path"], "datasets/final/final.parquet")
        self.assertEqual(by_family["dataset"]["row_count"], 120)
        self.assertEqual(by_family["model"]["model_type"], ModelArtifact.ModelType.BASELINE)
        self.assertEqual(by_family["model"]["file_path"], "models/baseline.joblib")
        self.assertEqual(by_family["report"]["report_type"], ReportArtifact.ReportType.METRICS_PLOT)
        self.assertEqual(by_family["report"]["file_path"], "reports/metrics_plot.png")

    def test_bi_confusion_matrix_flattens_confusion_matrix_json(self):
        run = self._create_run()
        MetricSnapshot.objects.create(
            run=run,
            model_type=ModelArtifact.ModelType.CATBOOST,
            accuracy=0.83,
            precision=0.75,
            recall=0.6,
            f1=0.6667,
            roc_auc=0.79,
            confusion_matrix_json=[[7, 1], [2, 3]],
        )

        rows = self._query(
            """
            SELECT
                run_id,
                model_type,
                tn,
                fp,
                fn,
                tp,
                accuracy,
                precision,
                recall,
                f1,
                roc_auc
            FROM bi_confusion_matrix
            WHERE run_id = %s
            """,
            [run.id],
        )

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["run_id"], run.id)
        self.assertEqual(row["model_type"], ModelArtifact.ModelType.CATBOOST)
        self.assertEqual(row["tn"], 7)
        self.assertEqual(row["fp"], 1)
        self.assertEqual(row["fn"], 2)
        self.assertEqual(row["tp"], 3)
        self.assertEqual(row["accuracy"], 0.83)
        self.assertEqual(row["precision"], 0.75)
        self.assertEqual(row["recall"], 0.6)
        self.assertEqual(row["f1"], 0.6667)
        self.assertEqual(row["roc_auc"], 0.79)

    @staticmethod
    def _create_run():
        return PipelineRun.objects.create(
            name="BI test run",
            status=PipelineRun.Status.SUCCESS,
            symbols_json=["BTCUSDT"],
            interval="1h",
            target_horizon=3,
        )

    @staticmethod
    def _query(sql, params=None):
        with connection.cursor() as cursor:
            cursor.execute(sql, params or [])
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
