import os
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError

django.setup()

from runs.models import (  # noqa: E402
    DatasetArtifact,
    MetricSnapshot,
    ModelArtifact,
    PipelineRun,
    ReportArtifact,
)


class RunCsvPipelineCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.csv_path = Path(self.temp_dir.name) / "input.csv"
        self.csv_path.write_text(self._csv_content(), encoding="utf-8")
        self.run_ids = []

    def tearDown(self):
        self._delete_artifact_files()
        PipelineRun.objects.filter(id__in=self.run_ids).delete()
        self.temp_dir.cleanup()

    def test_valid_csv_runs_pipeline_with_baseline_only(self):
        out = StringIO()

        call_command(
            "run_csv_pipeline",
            "--csv",
            str(self.csv_path),
            "--symbol",
            "BTCUSDT",
            "--interval",
            "1h",
            "--start-date",
            "2024-01-01",
            "--end-date",
            "2024-01-05",
            "--target-horizon",
            "3",
            "--skip-catboost",
            stdout=out,
        )

        run = PipelineRun.objects.latest("id")
        self.run_ids.append(run.id)
        self.assertEqual(run.status, PipelineRun.Status.SUCCESS)
        self.assertEqual(run.symbols_json, ["BTCUSDT"])
        self.assertEqual(run.interval, "1h")
        self.assertEqual(run.target_horizon, 3)
        self.assertEqual(DatasetArtifact.objects.filter(run=run).count(), 3)
        self.assertEqual(ModelArtifact.objects.filter(run=run).count(), 2)
        self.assertEqual(MetricSnapshot.objects.filter(run=run).count(), 2)
        self.assertEqual(ReportArtifact.objects.filter(run=run).count(), 4)

        raw_artifact = DatasetArtifact.objects.get(
            run=run,
            artifact_type=DatasetArtifact.ArtifactType.RAW,
        )
        self.assertEqual(raw_artifact.symbol, "BTCUSDT")
        self.assertEqual(raw_artifact.row_count, 120)
        self.assertTrue(raw_artifact.file_path.endswith(".csv"))
        self.assertTrue((Path(settings.MEDIA_ROOT) / raw_artifact.file_path).exists())

        output = out.getvalue()
        self.assertIn(f"Run id: {run.id}", output)
        self.assertIn("Run status: success", output)
        self.assertIn(f"Detail URL: /runs/{run.id}/", output)

    def test_invalid_path_raises_command_error(self):
        before_count = PipelineRun.objects.count()

        with self.assertRaises(CommandError):
            call_command(
                "run_csv_pipeline",
                "--csv",
                str(Path(self.temp_dir.name) / "missing.csv"),
                "--symbol",
                "BTCUSDT",
                "--start-date",
                "2024-01-01",
                "--end-date",
                "2024-01-05",
            )

        self.assertEqual(PipelineRun.objects.count(), before_count)

    def test_skip_both_models_raises_command_error_before_run_creation(self):
        before_count = PipelineRun.objects.count()

        with self.assertRaises(CommandError):
            call_command(
                "run_csv_pipeline",
                "--csv",
                str(self.csv_path),
                "--symbol",
                "BTCUSDT",
                "--start-date",
                "2024-01-01",
                "--end-date",
                "2024-01-05",
                "--skip-baseline",
                "--skip-catboost",
            )

        self.assertEqual(PipelineRun.objects.count(), before_count)

    def test_use_case_failure_prints_run_and_error_then_raises(self):
        out = StringIO()
        err = StringIO()
        fake_use_case = FailingUploadUseCase()

        with patch(
            "runs.management.commands.run_csv_pipeline.CsvPipelineUploadUseCase",
            return_value=fake_use_case,
        ):
            with self.assertRaises(CommandError):
                call_command(
                    "run_csv_pipeline",
                    "--csv",
                    str(self.csv_path),
                    "--symbol",
                    "BTCUSDT",
                    "--start-date",
                    "2024-01-01",
                    "--end-date",
                    "2024-01-05",
                    stdout=out,
                    stderr=err,
                )

        self.run_ids.append(fake_use_case.run.id)
        self.assertIn(f"Run id: {fake_use_case.run.id}", out.getvalue())
        self.assertIn("Run status: failed", out.getvalue())
        self.assertIn("pipeline failed", err.getvalue())

    @staticmethod
    def _csv_content():
        rows = ["timestamp,open,high,low,close,volume,symbol"]
        closes = [100 + ((index % 12) - 6) for index in range(120)]
        for index, close in enumerate(closes):
            timestamp = f"2024-01-{(index // 24) + 1:02d} {index % 24:02d}:00:00"
            rows.append(
                f"{timestamp},{close},{close + 1},{close - 1},{close},{100 + index},BTCUSDT"
            )
        return "\n".join(rows)

    def _delete_artifact_files(self):
        file_paths = list(
            DatasetArtifact.objects.filter(run_id__in=self.run_ids).values_list(
                "file_path",
                flat=True,
            )
        )
        file_paths.extend(
            ModelArtifact.objects.filter(run_id__in=self.run_ids).values_list(
                "file_path",
                flat=True,
            )
        )
        file_paths.extend(
            ReportArtifact.objects.filter(run_id__in=self.run_ids).values_list(
                "file_path",
                flat=True,
            )
        )

        for file_path in file_paths:
            path = Path(file_path)
            paths = [path] if path.is_absolute() else [path, Path(settings.MEDIA_ROOT) / path]
            for candidate in paths:
                if candidate.exists():
                    candidate.unlink()


class FailingUploadUseCase:
    def __init__(self):
        self.run = None

    def execute(self, *args, **kwargs):
        self.run = PipelineRun.objects.create(
            name="Manual CSV upload BTCUSDT 1h",
            status=PipelineRun.Status.FAILED,
            symbols_json=["BTCUSDT"],
            interval="1h",
            target_horizon=3,
            error_message="pipeline failed",
        )
        return SimpleNamespace(
            run=self.run,
            raw_artifact=None,
            pipeline_result=None,
            error_message="pipeline failed",
        )


if __name__ == "__main__":
    unittest.main()
