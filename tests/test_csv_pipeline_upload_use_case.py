import os
from io import StringIO
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.conf import settings
from django.test import TestCase

django.setup()

from mlcore.repositories import ArtifactRepository, DatasetRepository  # noqa: E402
from mlcore.services.csv_pipeline_upload_use_case import CsvPipelineUploadUseCase  # noqa: E402
from runs.models import DatasetArtifact, PipelineRun  # noqa: E402


class CsvPipelineUploadUseCaseTests(TestCase):
    def setUp(self):
        self.run_ids = []

    def tearDown(self):
        self._delete_dataset_files()
        PipelineRun.objects.filter(id__in=self.run_ids).delete()

    def test_execute_creates_run_saves_raw_and_runs_pipeline(self):
        pipeline_use_case = RecordingRunPipelineUseCase()
        use_case = self._build_use_case(pipeline_use_case)

        result = use_case.execute(
            StringIO(CSV_CONTENT),
            symbol="BTCUSDT",
            interval="1h",
            start_date="2024-01-01",
            end_date="2024-01-02",
            target_horizon=3,
            train_baseline=True,
            train_catboost=False,
        )
        self.run_ids.append(result.run.id)

        result.run.refresh_from_db()
        self.assertEqual(result.error_message, "")
        self.assertEqual(result.run.status, PipelineRun.Status.SUCCESS)
        self.assertEqual(result.run.name, "Manual CSV upload BTCUSDT 1h")
        self.assertEqual(result.run.symbols_json, ["BTCUSDT"])
        self.assertEqual(result.run.interval, "1h")
        self.assertEqual(result.run.target_horizon, 3)
        self.assertEqual(result.run.initiated_by, "manual_csv_upload")
        self.assertEqual(result.pipeline_result, pipeline_use_case.result)

        raw_artifact = DatasetArtifact.objects.get(
            run=result.run,
            artifact_type=DatasetArtifact.ArtifactType.RAW,
        )
        self.assertEqual(result.raw_artifact, raw_artifact)
        self.assertEqual(raw_artifact.symbol, "BTCUSDT")
        self.assertEqual(raw_artifact.row_count, 2)
        self.assertIn("datasets/raw/raw_run_", raw_artifact.file_path)
        self.assertTrue(raw_artifact.file_path.endswith(".csv"))
        self.assertTrue((Path(settings.MEDIA_ROOT) / raw_artifact.file_path).exists())

        self.assertEqual(pipeline_use_case.seen_run.id, result.run.id)
        self.assertEqual(list(pipeline_use_case.seen_raw_df.columns), EXPECTED_COLUMNS)
        self.assertTrue(pipeline_use_case.train_baseline)
        self.assertFalse(pipeline_use_case.train_catboost)

    def test_pipeline_error_marks_run_failed_and_keeps_raw_artifact(self):
        use_case = self._build_use_case(FailingRunPipelineUseCase("training failed"))

        result = use_case.execute(
            StringIO(CSV_CONTENT),
            symbol="BTCUSDT",
            interval="1h",
            start_date="2024-01-01",
            end_date="2024-01-02",
            target_horizon=3,
        )
        self.run_ids.append(result.run.id)

        result.run.refresh_from_db()
        self.assertEqual(result.error_message, "training failed")
        self.assertIsNone(result.pipeline_result)
        self.assertEqual(result.run.status, PipelineRun.Status.FAILED)
        self.assertIsNotNone(result.run.started_at)
        self.assertIsNotNone(result.run.finished_at)
        self.assertEqual(result.run.error_message, "training failed")
        self.assertEqual(DatasetArtifact.objects.filter(run=result.run).count(), 1)
        self.assertEqual(result.raw_artifact.artifact_type, DatasetArtifact.ArtifactType.RAW)
        self.assertTrue((Path(settings.MEDIA_ROOT) / result.raw_artifact.file_path).exists())

    def test_csv_read_error_marks_run_failed_without_raw_artifact(self):
        use_case = self._build_use_case(RecordingRunPipelineUseCase())

        result = use_case.execute(
            BrokenCsvFile(),
            symbol="BTCUSDT",
            interval="1h",
            start_date="2024-01-01",
            end_date="2024-01-02",
            target_horizon=3,
        )
        self.run_ids.append(result.run.id)

        result.run.refresh_from_db()
        self.assertEqual(result.error_message, "cannot read csv")
        self.assertIsNone(result.raw_artifact)
        self.assertIsNone(result.pipeline_result)
        self.assertEqual(result.run.status, PipelineRun.Status.FAILED)
        self.assertEqual(DatasetArtifact.objects.filter(run=result.run).count(), 0)

    @staticmethod
    def _build_use_case(run_pipeline_use_case):
        return CsvPipelineUploadUseCase(
            artifact_repository=ArtifactRepository(settings.MEDIA_ROOT),
            dataset_repository=DatasetRepository(),
            run_pipeline_use_case=run_pipeline_use_case,
        )

    def _delete_dataset_files(self):
        artifacts = DatasetArtifact.objects.filter(run_id__in=self.run_ids)
        for file_path in artifacts.values_list("file_path", flat=True):
            path = Path(file_path)
            if not path.is_absolute():
                path = Path(settings.MEDIA_ROOT) / path
            if path.exists():
                path.unlink()


class RecordingRunPipelineUseCase:
    result = {"ok": True}

    def __init__(self):
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
        return self.result


class FailingRunPipelineUseCase:
    def __init__(self, message):
        self.message = message

    def execute(self, *args, **kwargs):
        raise ValueError(self.message)


class BrokenCsvFile:
    def read(self, *args, **kwargs):
        raise ValueError("cannot read csv")


EXPECTED_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume", "symbol"]
CSV_CONTENT = "\n".join(
    [
        ",".join(EXPECTED_COLUMNS),
        "2024-01-01 00:00:00,1,2,0,1,100,BTCUSDT",
        "2024-01-01 01:00:00,2,3,1,2,101,BTCUSDT",
    ]
)
