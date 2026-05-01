import os
import unittest
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

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


class RunBinancePipelineCommandTests(unittest.TestCase):
    def setUp(self):
        self.run_ids = []

    def tearDown(self):
        self._delete_artifact_files()
        PipelineRun.objects.filter(id__in=self.run_ids).delete()

    def test_valid_binance_pipeline_runs_with_baseline_only(self):
        out = StringIO()

        with patch(
            "mlcore.services.binance_pipeline_use_case.BinanceMarketDataProvider",
            return_value=RecordingMarketDataProvider(self._raw_df()),
        ):
            call_command(
                "run_binance_pipeline",
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
        self.assertEqual(run.initiated_by, "binance_cli")
        self.assertEqual(DatasetArtifact.objects.filter(run=run).count(), 3)
        self.assertEqual(ModelArtifact.objects.filter(run=run).count(), 2)
        self.assertEqual(MetricSnapshot.objects.filter(run=run).count(), 2)
        self.assertEqual(ReportArtifact.objects.filter(run=run).count(), 2)

        raw_artifact = DatasetArtifact.objects.get(
            run=run,
            artifact_type=DatasetArtifact.ArtifactType.RAW,
        )
        self.assertEqual(raw_artifact.symbol, "BTCUSDT")
        self.assertEqual(raw_artifact.row_count, 120)
        self.assertTrue(raw_artifact.file_path.endswith(".parquet"))
        self.assertTrue((Path(settings.MEDIA_ROOT) / raw_artifact.file_path).exists())

        output = out.getvalue()
        self.assertIn(f"Run id: {run.id}", output)
        self.assertIn("Run status: success", output)
        self.assertIn(f"Detail URL: /runs/{run.id}/", output)

    def test_invalid_date_raises_command_error_before_run_creation(self):
        before_count = PipelineRun.objects.count()

        with self.assertRaises(CommandError):
            call_command(
                "run_binance_pipeline",
                "--symbol",
                "BTCUSDT",
                "--start-date",
                "2024-01-05",
                "--end-date",
                "2024-01-01",
            )

        self.assertEqual(PipelineRun.objects.count(), before_count)

    def test_skip_both_models_raises_command_error_before_run_creation(self):
        before_count = PipelineRun.objects.count()

        with self.assertRaises(CommandError):
            call_command(
                "run_binance_pipeline",
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
        fake_use_case = FailingBinancePipelineUseCase()

        with patch(
            "runs.management.commands.run_binance_pipeline.BinancePipelineUseCase",
            return_value=fake_use_case,
        ):
            with self.assertRaises(CommandError):
                call_command(
                    "run_binance_pipeline",
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
        self.assertIn("binance pipeline failed", err.getvalue())

    @staticmethod
    def _raw_df():
        closes = [100 + ((index % 12) - 6) for index in range(120)]
        return pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=120, freq="h"),
                "open": closes,
                "high": [close + 1 for close in closes],
                "low": [close - 1 for close in closes],
                "close": closes,
                "volume": range(100, 220),
                "symbol": ["BTCUSDT"] * 120,
            }
        )

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


class RecordingMarketDataProvider:
    def __init__(self, raw_df):
        self.raw_df = raw_df

    def get_ohlcv(self, *args, **kwargs):
        return self.raw_df.copy()


class FailingBinancePipelineUseCase:
    def __init__(self):
        self.run = None

    def execute(self, *args, **kwargs):
        self.run = PipelineRun.objects.create(
            name="Binance pipeline BTCUSDT 1h",
            status=PipelineRun.Status.FAILED,
            symbols_json=["BTCUSDT"],
            interval="1h",
            target_horizon=3,
            error_message="binance pipeline failed",
        )
        return SimpleNamespace(
            run=self.run,
            raw_artifact=None,
            pipeline_result=None,
            error_message="binance pipeline failed",
        )


if __name__ == "__main__":
    unittest.main()
