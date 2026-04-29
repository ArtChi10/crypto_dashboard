import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

django.setup()

from runs.models import DatasetArtifact, MetricSnapshot, ModelArtifact, PipelineRun  # noqa: E402


class CsvUploadViewTests(unittest.TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="localhost")
        self.run_ids = []

    def tearDown(self):
        self._delete_raw_artifact_files()
        PipelineRun.objects.filter(id__in=self.run_ids).delete()

    def test_upload_get_returns_form(self):
        response = self.client.get("/upload/")

        self.assertEqual(response.status_code, 200)
        content = response.content.decode().lower()
        self.assertIn("csv", content)
        self.assertIn("symbol", content)

    def test_dashboard_contains_upload_link(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("/upload/", response.content.decode())

    def test_valid_csv_creates_run_executes_pipeline_and_redirects_to_detail(self):
        use_case = RecordingUseCase(create_metadata=True)

        with patch("dashboard.views._build_upload_use_case", return_value=use_case):
            response = self.client.post(
                "/upload/",
                data=self._form_data(),
            )

        run = PipelineRun.objects.latest("id")
        self.run_ids.append(run.id)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"/runs/{run.id}/")
        self.assertEqual(run.status, PipelineRun.Status.SUCCESS)
        self.assertEqual(run.symbols_json, ["BTCUSDT"])
        self.assertEqual(run.interval, "1h")
        self.assertEqual(run.target_horizon, 3)
        self.assertEqual(run.initiated_by, "manual_csv_upload")
        self.assertEqual(use_case.seen_run.id, run.id)
        self.assertEqual(list(use_case.seen_raw_df.columns), EXPECTED_COLUMNS)
        self.assertTrue(use_case.train_baseline)
        self.assertTrue(use_case.train_catboost)
        self.assertEqual(DatasetArtifact.objects.filter(run=run).count(), 3)
        raw_artifact = DatasetArtifact.objects.get(
            run=run,
            artifact_type=DatasetArtifact.ArtifactType.RAW,
        )
        self.assertEqual(raw_artifact.symbol, "BTCUSDT")
        self.assertEqual(raw_artifact.row_count, 2)
        self.assertIn("datasets/raw/raw_run_", raw_artifact.file_path)
        self.assertTrue(raw_artifact.file_path.endswith(".csv"))
        self.assertTrue((Path(settings.MEDIA_ROOT) / raw_artifact.file_path).exists())
        self.assertEqual(ModelArtifact.objects.filter(run=run).count(), 1)
        self.assertEqual(MetricSnapshot.objects.filter(run=run).count(), 1)

        detail_response = self.client.get(response.url)
        detail_content = detail_response.content.decode()
        self.assertIn("raw", detail_content)
        self.assertIn("processed.parquet", detail_content)
        self.assertIn("baseline.joblib", detail_content)
        self.assertIn("MetricSnapshot", detail_content)

    def test_pipeline_error_marks_run_failed_and_redirects_to_detail(self):
        use_case = FailingUseCase("bad csv")

        with patch("dashboard.views._build_upload_use_case", return_value=use_case):
            response = self.client.post(
                "/upload/",
                data=self._form_data(),
            )

        run = PipelineRun.objects.latest("id")
        self.run_ids.append(run.id)
        run.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"/runs/{run.id}/")
        self.assertEqual(run.status, PipelineRun.Status.FAILED)
        self.assertIsNotNone(run.started_at)
        self.assertIsNotNone(run.finished_at)
        self.assertEqual(run.error_message, "bad csv")
        self.assertEqual(DatasetArtifact.objects.filter(run=run).count(), 1)
        raw_artifact = DatasetArtifact.objects.get(
            run=run,
            artifact_type=DatasetArtifact.ArtifactType.RAW,
        )
        self.assertEqual(raw_artifact.symbol, "BTCUSDT")
        self.assertEqual(raw_artifact.row_count, 2)
        self.assertTrue((Path(settings.MEDIA_ROOT) / raw_artifact.file_path).exists())

    def test_invalid_form_does_not_create_run_or_500(self):
        before_count = PipelineRun.objects.count()

        response = self.client.post(
            "/upload/",
            data={
                "symbol": "BTCUSDT",
                "interval": "1h",
                "target_horizon": "3",
                "train_baseline": "on",
                "train_catboost": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(PipelineRun.objects.count(), before_count)

    @staticmethod
    def _form_data():
        return {
            "csv_file": SimpleUploadedFile(
                "raw.csv",
                CSV_CONTENT.encode(),
                content_type="text/csv",
            ),
            "symbol": "BTCUSDT",
            "interval": "1h",
            "start_date": "2024-01-01",
            "end_date": "2024-01-02",
            "target_horizon": "3",
            "train_baseline": "on",
            "train_catboost": "on",
        }

    def _delete_raw_artifact_files(self):
        raw_artifacts = DatasetArtifact.objects.filter(
            run_id__in=self.run_ids,
            artifact_type=DatasetArtifact.ArtifactType.RAW,
        )
        for file_path in raw_artifacts.values_list("file_path", flat=True):
            path = Path(file_path)
            if not path.is_absolute():
                path = Path(settings.MEDIA_ROOT) / path
            if path.exists():
                path.unlink()


class RecordingUseCase:
    def __init__(self, create_metadata=False):
        self.create_metadata = create_metadata
        self.seen_run = None
        self.seen_raw_df = None
        self.train_baseline = None
        self.train_catboost = None

    def execute(self, run, raw_df, train_baseline=True, train_catboost=True):
        self.seen_run = run
        self.seen_raw_df = raw_df
        self.train_baseline = train_baseline
        self.train_catboost = train_catboost
        run.status = PipelineRun.Status.SUCCESS
        run.save(update_fields=["status"])
        if self.create_metadata:
            DatasetArtifact.objects.create(
                run=run,
                artifact_type=DatasetArtifact.ArtifactType.PROCESSED,
                file_path="processed.parquet",
                row_count=10,
            )
            DatasetArtifact.objects.create(
                run=run,
                artifact_type=DatasetArtifact.ArtifactType.FINAL,
                file_path="final.parquet",
                row_count=8,
            )
            ModelArtifact.objects.create(
                run=run,
                model_type=ModelArtifact.ModelType.BASELINE,
                file_path="baseline.joblib",
            )
            MetricSnapshot.objects.create(
                run=run,
                model_type=ModelArtifact.ModelType.BASELINE,
                accuracy=1.0,
                precision=1.0,
                recall=1.0,
                f1=1.0,
                roc_auc=1.0,
                confusion_matrix_json=[[1, 0], [0, 1]],
            )


class FailingUseCase:
    def __init__(self, message):
        self.message = message

    def execute(self, *args, **kwargs):
        raise ValueError(self.message)


EXPECTED_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume", "symbol"]
CSV_CONTENT = "\n".join(
    [
        ",".join(EXPECTED_COLUMNS),
        "2024-01-01 00:00:00,1,2,0,1,100,BTCUSDT",
        "2024-01-01 01:00:00,2,3,1,2,101,BTCUSDT",
    ]
)


if __name__ == "__main__":
    unittest.main()
