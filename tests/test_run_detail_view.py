import os
import tempfile
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.test import Client, TestCase, override_settings

django.setup()

from runs.models import (  # noqa: E402
    DatasetArtifact,
    MetricSnapshot,
    ModelArtifact,
    PipelineRun,
    ReportArtifact,
)


class RunDetailViewTests(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="localhost")
        self.run_ids = []
        self.temp_dir = tempfile.TemporaryDirectory()
        self.media_root = Path(self.temp_dir.name)

    def tearDown(self):
        PipelineRun.objects.filter(id__in=self.run_ids).delete()
        self.temp_dir.cleanup()

    def test_artifact_links_model_summary_and_metrics_are_readable(self):
        run = self._create_run(status=PipelineRun.Status.SUCCESS)
        DatasetArtifact.objects.create(
            run=run,
            artifact_type=DatasetArtifact.ArtifactType.FINAL,
            symbol="BTCUSDT",
            file_path="datasets/final/final.parquet",
            row_count=73,
        )
        ModelArtifact.objects.create(
            run=run,
            model_type=ModelArtifact.ModelType.BASELINE,
            file_path="models/model_baseline.joblib",
            params_json={
                "feature_columns": ["feature_1", "feature_2", "feature_3"],
                "train_rows": 70,
                "valid_rows": 15,
                "test_rows": 15,
            },
        )
        MetricSnapshot.objects.create(
            run=run,
            model_type=ModelArtifact.ModelType.BASELINE,
            accuracy=0.87654321,
            precision=0.81234567,
            recall=0.7,
            f1=0.754321,
            roc_auc=0.912345,
            confusion_matrix_json=[[5, 1], [2, 4]],
        )
        ReportArtifact.objects.create(
            run=run,
            report_type=ReportArtifact.ReportType.METRICS_PLOT,
            file_path="reports/metrics.png",
        )

        response = self.client.get(f"/runs/{run.id}/")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('href="/media/datasets/final/final.parquet"', html)
        self.assertIn('href="/media/models/model_baseline.joblib"', html)
        self.assertIn('href="/media/reports/metrics.png"', html)
        self.assertIn('<img src="/media/reports/metrics.png"', html)
        self.assertIn("0.8765", html)
        self.assertIn("0.8123", html)
        self.assertIn("0.7000", html)
        self.assertIn("0.7543", html)
        self.assertIn("0.9123", html)
        self.assertIn("[ 5  1 ]", html)
        self.assertIn("[ 2  4 ]", html)
        self.assertIn("DatasetArtifact показывает datasets", html)
        self.assertIn("MetricSnapshot содержит test metrics", html)
        self.assertIn("true negatives", html)
        self.assertIn(">70<", html)
        self.assertIn(">15<", html)
        self.assertIn(">3<", html)
        self.assertNotIn("feature_columns", html)

    def test_unsafe_artifact_path_renders_as_text_without_media_link(self):
        run = self._create_run(status=PipelineRun.Status.SUCCESS)
        DatasetArtifact.objects.create(
            run=run,
            artifact_type=DatasetArtifact.ArtifactType.RAW,
            file_path="../secret.csv",
            row_count=10,
        )

        response = self.client.get(f"/runs/{run.id}/")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("../secret.csv", html)
        self.assertNotIn('href="/media/../secret.csv"', html)

    def test_report_images_render_only_for_safe_png_paths(self):
        run = self._create_run(status=PipelineRun.Status.SUCCESS)
        ReportArtifact.objects.create(
            run=run,
            report_type=ReportArtifact.ReportType.TARGET_DISTRIBUTION,
            file_path="reports/target_distribution.png",
        )
        ReportArtifact.objects.create(
            run=run,
            report_type=ReportArtifact.ReportType.METRICS_PLOT,
            file_path="reports/metrics.json",
        )
        ReportArtifact.objects.create(
            run=run,
            report_type=ReportArtifact.ReportType.FEATURE_IMPORTANCE,
            file_path="../reports/feature_importance.png",
        )

        response = self.client.get(f"/runs/{run.id}/")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('href="/media/reports/target_distribution.png"', html)
        self.assertIn('<img src="/media/reports/target_distribution.png"', html)
        self.assertIn('href="/media/reports/metrics.json"', html)
        self.assertNotIn('<img src="/media/reports/metrics.json"', html)
        self.assertIn("../reports/feature_importance.png", html)
        self.assertNotIn('href="/media/../reports/feature_importance.png"', html)
        self.assertNotIn('<img src="/media/../reports/feature_importance.png"', html)

    def test_stability_table_preview_renders_summary_and_truncates_rows(self):
        run = self._create_run(status=PipelineRun.Status.SUCCESS)
        self._write_stability_csv(row_count=22)
        ReportArtifact.objects.create(
            run=run,
            report_type="stability_table",
            file_path="reports/stability.csv",
        )

        with override_settings(MEDIA_ROOT=self.media_root):
            response = self.client.get(f"/runs/{run.id}/")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("Stability by Period", html)
        self.assertIn('href="/media/reports/stability.csv"', html)
        self.assertIn("model_0", html)
        self.assertIn("model_19", html)
        self.assertNotIn("model_20", html)
        self.assertIn("0.1235", html)
        self.assertIn("0.6543", html)
        self.assertIn("0.9877", html)
        self.assertIn("Showing first 20 rows", html)

    def test_stability_table_preview_missing_file_does_not_crash(self):
        run = self._create_run(status=PipelineRun.Status.SUCCESS)
        ReportArtifact.objects.create(
            run=run,
            report_type="stability_table",
            file_path="reports/missing_stability.csv",
        )

        with override_settings(MEDIA_ROOT=self.media_root):
            response = self.client.get(f"/runs/{run.id}/")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("Stability by Period", html)
        self.assertIn("Stability preview unavailable", html)
        self.assertIn('href="/media/reports/missing_stability.csv"', html)

    def test_stability_table_preview_does_not_read_unsafe_paths(self):
        run = self._create_run(status=PipelineRun.Status.SUCCESS)
        self._write_stability_csv(row_count=1)
        ReportArtifact.objects.create(
            run=run,
            report_type="stability_table",
            file_path="../reports/stability.csv",
        )

        with override_settings(MEDIA_ROOT=self.media_root):
            response = self.client.get(f"/runs/{run.id}/")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("Stability preview unavailable", html)
        self.assertIn("../reports/stability.csv", html)
        self.assertNotIn('href="/media/../reports/stability.csv"', html)
        self.assertNotIn("model_0", html)

    def test_forecast_replay_preview_renders_summary_and_rows(self):
        run = self._create_run(status=PipelineRun.Status.SUCCESS)
        self._write_forecast_replay_csv()
        ReportArtifact.objects.create(
            run=run,
            report_type=ReportArtifact.ReportType.FORECAST_REPLAY_TABLE,
            file_path="reports/forecast_replay_table.csv",
        )

        with override_settings(MEDIA_ROOT=self.media_root):
            response = self.client.get(f"/runs/{run.id}/")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("Forecast Replay", html)
        self.assertIn("3 / 5", html)
        self.assertIn("60.0%", html)
        self.assertIn("0.6200", html)
        self.assertIn("timestamp", html)
        self.assertIn("predicted", html)
        self.assertIn("actual", html)
        self.assertIn("result", html)
        self.assertIn("correct", html)
        self.assertIn("wrong", html)
        self.assertIn("3.0000%", html)
        self.assertIn('href="/media/reports/forecast_replay_table.csv"', html)

    def test_forecast_replay_preview_missing_file_does_not_crash(self):
        run = self._create_run(status=PipelineRun.Status.SUCCESS)
        ReportArtifact.objects.create(
            run=run,
            report_type=ReportArtifact.ReportType.FORECAST_REPLAY_TABLE,
            file_path="reports/missing_forecast_replay_table.csv",
        )

        with override_settings(MEDIA_ROOT=self.media_root):
            response = self.client.get(f"/runs/{run.id}/")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("Forecast Replay", html)
        self.assertIn("Forecast replay preview unavailable", html)

    def test_forecast_replay_preview_does_not_read_unsafe_paths(self):
        run = self._create_run(status=PipelineRun.Status.SUCCESS)
        self._write_forecast_replay_csv()
        ReportArtifact.objects.create(
            run=run,
            report_type=ReportArtifact.ReportType.FORECAST_REPLAY_TABLE,
            file_path="../reports/forecast_replay_table.csv",
        )

        with override_settings(MEDIA_ROOT=self.media_root):
            response = self.client.get(f"/runs/{run.id}/")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("Forecast replay preview unavailable", html)
        self.assertIn("../reports/forecast_replay_table.csv", html)
        self.assertNotIn('href="/media/../reports/forecast_replay_table.csv"', html)
        self.assertNotIn("60.0%", html)

    def test_empty_states_still_render(self):
        run = self._create_run(status=PipelineRun.Status.CREATED)

        response = self.client.get(f"/runs/{run.id}/")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("Dataset artifacts для этого запуска пока нет.", html)
        self.assertIn("Model artifacts для этого запуска пока нет.", html)
        self.assertIn("Metric snapshots для этого запуска пока нет.", html)
        self.assertIn("Report artifacts для этого запуска пока нет.", html)

    def _create_run(self, status):
        run = PipelineRun.objects.create(
            name="Run detail view test",
            status=status,
            symbols_json=["BTCUSDT"],
            interval="1h",
            target_horizon=3,
        )
        self.run_ids.append(run.id)
        return run

    def _write_stability_csv(self, row_count):
        reports_dir = self.media_root / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        lines = [
            "model_type,period_start,period_end,rows,positive_rate,accuracy,precision,recall,f1,roc_auc"
        ]
        for index in range(row_count):
            lines.append(
                ",".join(
                    [
                        f"model_{index}",
                        f"2024-01-{index + 1:02d} 00:00:00",
                        f"2024-01-{index + 1:02d} 23:00:00",
                        "24",
                        "0.5",
                        "0.123456",
                        "0.222222",
                        "0.333333",
                        "0.654321",
                        "0.987654",
                    ]
                )
            )
        (reports_dir / "stability.csv").write_text("\n".join(lines), encoding="utf-8")

    def _write_forecast_replay_csv(self):
        reports_dir = self.media_root / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        lines = [
            ",".join(
                [
                    "timestamp",
                    "close",
                    "future_close",
                    "actual_direction",
                    "predicted_direction",
                    "predicted_probability",
                    "is_correct",
                    "actual_change",
                    "actual_change_pct",
                    "predicted_label",
                    "actual_label",
                    "result_label",
                ]
            ),
            "2024-01-01 00:00:00,100,103,1,1,0.8,True,3,3.0,up,up,correct",
            "2024-01-01 01:00:00,100,98,0,1,0.7,False,-2,-2.0,up,down,wrong",
            "2024-01-01 02:00:00,100,99,0,0,0.3,True,-1,-1.0,down,down,correct",
            "2024-01-01 03:00:00,100,104,1,0,0.9,False,4,4.0,down,up,wrong",
            "2024-01-01 04:00:00,100,101,1,1,0.4,True,1,1.0,up,up,correct",
        ]
        (reports_dir / "forecast_replay_table.csv").write_text(
            "\n".join(lines),
            encoding="utf-8",
        )
