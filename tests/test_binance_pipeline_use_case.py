import os
from pathlib import Path

import pandas as pd

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.conf import settings
from django.test import TestCase

django.setup()

from mlcore.repositories import ArtifactRepository, DatasetRepository  # noqa: E402
from mlcore.services.binance_pipeline_use_case import BinancePipelineUseCase  # noqa: E402
from runs.models import DatasetArtifact, PipelineRun  # noqa: E402


class BinancePipelineUseCaseTests(TestCase):
    def setUp(self):
        self.run_ids = []

    def tearDown(self):
        self._delete_dataset_files()
        PipelineRun.objects.filter(id__in=self.run_ids).delete()

    def test_execute_downloads_saves_raw_and_runs_pipeline(self):
        provider = RecordingMarketDataProvider(self._raw_df())
        pipeline_use_case = RecordingRunPipelineUseCase()
        use_case = self._build_use_case(provider, pipeline_use_case)

        result = use_case.execute(
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
        self.assertEqual(result.run.name, "Binance pipeline BTCUSDT 1h")
        self.assertEqual(result.run.symbols_json, ["BTCUSDT"])
        self.assertEqual(result.run.interval, "1h")
        self.assertEqual(result.run.target_horizon, 3)
        self.assertEqual(result.run.initiated_by, "binance_cli")
        self.assertEqual(result.pipeline_result, pipeline_use_case.result)
        self.assertEqual(
            provider.calls,
            [
                {
                    "symbol": "BTCUSDT",
                    "interval": "1h",
                    "start": "2024-01-01",
                    "end": "2024-01-02",
                }
            ],
        )

        raw_artifact = DatasetArtifact.objects.get(
            run=result.run,
            artifact_type=DatasetArtifact.ArtifactType.RAW,
        )
        self.assertEqual(result.raw_artifact, raw_artifact)
        self.assertEqual(raw_artifact.symbol, "BTCUSDT")
        self.assertEqual(raw_artifact.row_count, 2)
        self.assertIn("datasets/raw/raw_run_", raw_artifact.file_path)
        self.assertTrue(raw_artifact.file_path.endswith(".parquet"))
        self.assertTrue((Path(settings.MEDIA_ROOT) / raw_artifact.file_path).exists())

        self.assertEqual(pipeline_use_case.seen_run.id, result.run.id)
        pd.testing.assert_frame_equal(pipeline_use_case.seen_raw_df, provider.raw_df)
        self.assertTrue(pipeline_use_case.train_baseline)
        self.assertFalse(pipeline_use_case.train_catboost)
        self.assertIsNone(pipeline_use_case.future_df)
        self.assertFalse(pipeline_use_case.enable_forecast_replay)
        self.assertEqual(pipeline_use_case.replay_steps, 5)

    def test_execute_with_forecast_replay_downloads_future_window(self):
        history_df = self._raw_df()
        future_df = self._future_df()
        provider = RecordingMarketDataProvider([history_df, future_df])
        pipeline_use_case = RecordingRunPipelineUseCase()
        use_case = self._build_use_case(provider, pipeline_use_case)

        result = use_case.execute(
            symbol="BTCUSDT",
            interval="1h",
            start_date="2024-01-01",
            end_date="2024-01-02",
            target_horizon=3,
            train_baseline=True,
            train_catboost=True,
            enable_forecast_replay=True,
            replay_steps=5,
        )
        self.run_ids.append(result.run.id)

        self.assertEqual(result.error_message, "")
        self.assertEqual(
            provider.calls,
            [
                {
                    "symbol": "BTCUSDT",
                    "interval": "1h",
                    "start": "2024-01-01",
                    "end": "2024-01-02",
                },
                {
                    "symbol": "BTCUSDT",
                    "interval": "1h",
                    "start": pd.Timestamp("2024-01-02 01:00:00"),
                    "end": pd.Timestamp("2024-01-02 08:00:00"),
                },
            ],
        )
        pd.testing.assert_frame_equal(pipeline_use_case.future_df, future_df)
        self.assertTrue(pipeline_use_case.enable_forecast_replay)
        self.assertEqual(pipeline_use_case.replay_steps, 5)

    def test_execute_with_forecast_replay_rejects_unknown_interval(self):
        provider = RecordingMarketDataProvider(self._raw_df())
        pipeline_use_case = RecordingRunPipelineUseCase()
        use_case = self._build_use_case(provider, pipeline_use_case)

        result = use_case.execute(
            symbol="BTCUSDT",
            interval="2d",
            start_date="2024-01-01",
            end_date="2024-01-02",
            target_horizon=3,
            enable_forecast_replay=True,
            replay_steps=5,
        )
        self.run_ids.append(result.run.id)

        result.run.refresh_from_db()
        self.assertIn("Unsupported replay interval", result.error_message)
        self.assertEqual(result.run.status, PipelineRun.Status.FAILED)
        self.assertEqual(len(provider.calls), 1)
        self.assertIsNone(pipeline_use_case.seen_run)

    def test_provider_error_marks_run_failed_without_raw_artifact(self):
        provider = FailingMarketDataProvider("binance unavailable")
        use_case = self._build_use_case(provider, RecordingRunPipelineUseCase())

        result = use_case.execute(
            symbol="BTCUSDT",
            interval="1h",
            start_date="2024-01-01",
            end_date="2024-01-02",
            target_horizon=3,
        )
        self.run_ids.append(result.run.id)

        result.run.refresh_from_db()
        self.assertEqual(result.error_message, "binance unavailable")
        self.assertIsNone(result.raw_artifact)
        self.assertIsNone(result.pipeline_result)
        self.assertEqual(result.run.status, PipelineRun.Status.FAILED)
        self.assertIsNotNone(result.run.started_at)
        self.assertIsNotNone(result.run.finished_at)
        self.assertEqual(DatasetArtifact.objects.filter(run=result.run).count(), 0)

    def test_pipeline_error_marks_run_failed_and_keeps_raw_artifact(self):
        provider = RecordingMarketDataProvider(self._raw_df())
        use_case = self._build_use_case(provider, FailingRunPipelineUseCase("training failed"))

        result = use_case.execute(
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
        self.assertEqual(DatasetArtifact.objects.filter(run=result.run).count(), 1)
        self.assertEqual(result.raw_artifact.artifact_type, DatasetArtifact.ArtifactType.RAW)
        self.assertTrue((Path(settings.MEDIA_ROOT) / result.raw_artifact.file_path).exists())

    @staticmethod
    def _build_use_case(provider, run_pipeline_use_case):
        return BinancePipelineUseCase(
            market_data_provider=provider,
            artifact_repository=ArtifactRepository(settings.MEDIA_ROOT),
            dataset_repository=DatasetRepository(),
            run_pipeline_use_case=run_pipeline_use_case,
        )

    @staticmethod
    def _raw_df():
        return pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=2, freq="h"),
                "open": [1.0, 2.0],
                "high": [2.0, 3.0],
                "low": [0.5, 1.5],
                "close": [1.5, 2.5],
                "volume": [100.0, 101.0],
                "symbol": ["BTCUSDT", "BTCUSDT"],
            }
        )

    @staticmethod
    def _future_df():
        return pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-02 01:00:00", periods=8, freq="h"),
                "open": range(3, 11),
                "high": range(4, 12),
                "low": range(2, 10),
                "close": range(3, 11),
                "volume": range(102, 110),
                "symbol": ["BTCUSDT"] * 8,
            }
        )

    def _delete_dataset_files(self):
        artifacts = DatasetArtifact.objects.filter(run_id__in=self.run_ids)
        for file_path in artifacts.values_list("file_path", flat=True):
            path = Path(file_path)
            if not path.is_absolute():
                path = Path(settings.MEDIA_ROOT) / path
            if path.exists():
                path.unlink()


class RecordingMarketDataProvider:
    def __init__(self, raw_df):
        self.responses = raw_df if isinstance(raw_df, list) else [raw_df]
        self.raw_df = self.responses[0]
        self.calls = []

    def get_ohlcv(self, symbol, interval, start, end):
        self.calls.append(
            {
                "symbol": symbol,
                "interval": interval,
                "start": start,
                "end": end,
            }
        )
        response_index = min(len(self.calls) - 1, len(self.responses) - 1)
        return self.responses[response_index].copy()


class FailingMarketDataProvider:
    def __init__(self, message):
        self.message = message

    def get_ohlcv(self, *args, **kwargs):
        raise ValueError(self.message)


class RecordingRunPipelineUseCase:
    result = {"ok": True}

    def __init__(self):
        self.seen_run = None
        self.seen_raw_df = None
        self.future_df = None
        self.train_baseline = None
        self.train_catboost = None
        self.enable_forecast_replay = None
        self.replay_steps = None

    def execute(
        self,
        run,
        raw_df,
        train_baseline=True,
        train_catboost=True,
        future_df=None,
        enable_forecast_replay=False,
        replay_steps=5,
    ):
        self.seen_run = run
        self.seen_raw_df = raw_df
        self.future_df = future_df
        self.train_baseline = train_baseline
        self.train_catboost = train_catboost
        self.enable_forecast_replay = enable_forecast_replay
        self.replay_steps = replay_steps
        run.status = PipelineRun.Status.SUCCESS
        run.save(update_fields=["status"])
        return self.result


class FailingRunPipelineUseCase:
    def __init__(self, message):
        self.message = message

    def execute(self, *args, **kwargs):
        raise ValueError(self.message)
