import os
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.test import TestCase

django.setup()

from mlcore.services import (  # noqa: E402
    DatasetPreparationResult,
    FullPipelineResult,
    RunPersistenceResult,
    RunPipelineUseCase,
)
from runs.models import PipelineRun  # noqa: E402


class RunPipelineUseCaseTests(TestCase):
    def setUp(self):
        self.run_ids = []

    def tearDown(self):
        PipelineRun.objects.filter(id__in=self.run_ids).delete()

    def test_execute_marks_run_running_then_success_and_persists_result(self):
        run = self._create_run(error_message="old error")
        full_pipeline_service = RecordingFullPipelineService()
        persistence_service = RecordingPersistenceService()
        use_case = RunPipelineUseCase(
            full_pipeline_service=full_pipeline_service,
            persistence_service=persistence_service,
        )

        result = use_case.execute(run, raw_df="raw")
        run.refresh_from_db()

        self.assertEqual(full_pipeline_service.status_during_call, PipelineRun.Status.RUNNING)
        self.assertEqual(full_pipeline_service.error_message_during_call, "")
        self.assertEqual(run.status, PipelineRun.Status.SUCCESS)
        self.assertIsNotNone(run.started_at)
        self.assertIsNotNone(run.finished_at)
        self.assertEqual(run.error_message, "")
        self.assertIs(persistence_service.seen_run, run)
        self.assertIs(persistence_service.seen_result, full_pipeline_service.result)
        self.assertIs(result.full_pipeline_result, full_pipeline_service.result)
        self.assertIs(result.persistence_result, persistence_service.result)

    def test_execute_passes_horizon_single_symbol_and_training_flags(self):
        run = self._create_run(symbols_json=["ETHUSDT"], target_horizon=6)
        full_pipeline_service = RecordingFullPipelineService()
        use_case = RunPipelineUseCase(
            full_pipeline_service=full_pipeline_service,
            persistence_service=RecordingPersistenceService(),
        )

        use_case.execute(
            run,
            raw_df="raw",
            train_baseline=False,
            train_catboost=True,
            future_df="future",
            enable_forecast_replay=True,
            replay_steps=7,
        )

        self.assertEqual(full_pipeline_service.raw_df, "raw")
        self.assertEqual(full_pipeline_service.run_id, run.id)
        self.assertEqual(full_pipeline_service.horizon, 6)
        self.assertEqual(full_pipeline_service.symbol, "ETHUSDT")
        self.assertFalse(full_pipeline_service.train_baseline)
        self.assertTrue(full_pipeline_service.train_catboost)
        self.assertEqual(full_pipeline_service.future_df, "future")
        self.assertTrue(full_pipeline_service.enable_forecast_replay)
        self.assertEqual(full_pipeline_service.replay_steps, 7)

    def test_execute_passes_none_symbol_for_multiple_symbols(self):
        run = self._create_run(symbols_json=["BTCUSDT", "ETHUSDT"])
        full_pipeline_service = RecordingFullPipelineService()
        use_case = RunPipelineUseCase(
            full_pipeline_service=full_pipeline_service,
            persistence_service=RecordingPersistenceService(),
        )

        use_case.execute(run, raw_df="raw")

        self.assertIsNone(full_pipeline_service.symbol)

    def test_execute_uses_default_horizon_when_run_horizon_is_empty(self):
        run = self._create_run(target_horizon=None)
        full_pipeline_service = RecordingFullPipelineService()
        use_case = RunPipelineUseCase(
            full_pipeline_service=full_pipeline_service,
            persistence_service=RecordingPersistenceService(),
        )

        use_case.execute(run, raw_df="raw")

        self.assertEqual(full_pipeline_service.horizon, 3)

    def test_execute_marks_failed_and_reraises_when_pipeline_fails(self):
        run = self._create_run()
        persistence_service = RecordingPersistenceService()
        use_case = RunPipelineUseCase(
            full_pipeline_service=FailingFullPipelineService("pipeline exploded"),
            persistence_service=persistence_service,
        )

        with self.assertRaisesRegex(RuntimeError, "pipeline exploded"):
            use_case.execute(run, raw_df="raw")

        run.refresh_from_db()
        self.assertEqual(run.status, PipelineRun.Status.FAILED)
        self.assertIsNotNone(run.started_at)
        self.assertIsNotNone(run.finished_at)
        self.assertEqual(run.error_message, "pipeline exploded")
        self.assertIsNone(persistence_service.seen_result)

    def _create_run(
        self,
        symbols_json=None,
        target_horizon=3,
        error_message="",
    ):
        run = PipelineRun.objects.create(
            name="Use case unit test",
            symbols_json=symbols_json or ["BTCUSDT"],
            interval="1h",
            target_horizon=target_horizon,
            error_message=error_message,
        )
        self.run_ids.append(run.id)
        return run


class RecordingFullPipelineService:
    def __init__(self):
        self.result = self._make_result()
        self.raw_df = None
        self.run_id = None
        self.horizon = None
        self.symbol = None
        self.train_baseline = None
        self.train_catboost = None
        self.future_df = None
        self.enable_forecast_replay = None
        self.replay_steps = None
        self.status_during_call = None
        self.error_message_during_call = None

    def run(
        self,
        raw_df,
        run_id,
        horizon=3,
        symbol=None,
        train_baseline=True,
        train_catboost=True,
        future_df=None,
        enable_forecast_replay=False,
        replay_steps=5,
    ):
        run = PipelineRun.objects.get(id=run_id)
        self.status_during_call = run.status
        self.error_message_during_call = run.error_message
        self.raw_df = raw_df
        self.run_id = run_id
        self.horizon = horizon
        self.symbol = symbol
        self.train_baseline = train_baseline
        self.train_catboost = train_catboost
        self.future_df = future_df
        self.enable_forecast_replay = enable_forecast_replay
        self.replay_steps = replay_steps
        return self.result

    @staticmethod
    def _make_result():
        return FullPipelineResult(
            preparation_result=DatasetPreparationResult(
                processed_path=Path("processed.parquet"),
                final_path=Path("final.parquet"),
                raw_rows=10,
                processed_rows=9,
                final_rows=8,
                feature_columns=["feature_1"],
                target_column="target",
            ),
            baseline_result=None,
            catboost_result=None,
        )


class FailingFullPipelineService:
    def __init__(self, message):
        self.message = message

    def run(self, *args, **kwargs):
        raise RuntimeError(self.message)


class RecordingPersistenceService:
    def __init__(self):
        self.result = RunPersistenceResult(
            processed_dataset_artifact="processed",
            final_dataset_artifact="final",
            baseline_model_artifact=None,
            baseline_metric_snapshot=None,
            catboost_model_artifact=None,
            catboost_metric_snapshot=None,
        )
        self.seen_run = None
        self.seen_result = None

    def save_full_pipeline_result(self, run, result):
        self.seen_run = run
        self.seen_result = result
        return self.result
