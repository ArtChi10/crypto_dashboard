import os
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.test import Client, TestCase
from django.utils import timezone

django.setup()

from runs.models import PipelineRun  # noqa: E402


class BinancePipelineViewTests(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="localhost")
        self.run_ids = []

    def tearDown(self):
        PipelineRun.objects.filter(id__in=self.run_ids).delete()

    def test_binance_get_returns_form(self):
        response = self.client.get("/binance/")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("BTCUSDT", html)
        self.assertIn("Binance", html)
        self.assertIn("Binance Spot API", html)
        self.assertIn("OHLCV candles", html)
        self.assertIn("target_horizon", html)
        self.assertIn("через сколько свечей", html)
        self.assertIn("Enable forecast replay", html)
        self.assertIn("Replay steps", html)
        self.assertIn("trading signal", html)

    def test_dashboard_and_nav_contain_binance_link(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("/binance/", response.content.decode())

    def test_valid_post_calls_use_case_and_redirects_to_detail(self):
        use_case = RecordingBinanceUseCase()

        with patch("dashboard.views._build_binance_pipeline_use_case", return_value=use_case):
            response = self.client.post(
                "/binance/",
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
        self.assertEqual(run.initiated_by, "binance_cli")
        self.assertEqual(use_case.symbol, "BTCUSDT")
        self.assertEqual(use_case.interval, "1h")
        self.assertEqual(str(use_case.start_date), "2024-01-01")
        self.assertEqual(str(use_case.end_date), "2024-01-02")
        self.assertEqual(use_case.target_horizon, 3)
        self.assertTrue(use_case.train_baseline)
        self.assertTrue(use_case.train_catboost)
        self.assertTrue(use_case.enable_forecast_replay)
        self.assertEqual(use_case.replay_steps, 5)

    def test_pipeline_error_after_run_creation_redirects_to_failed_run(self):
        use_case = FailingBinanceUseCase("binance failed")

        with patch("dashboard.views._build_binance_pipeline_use_case", return_value=use_case):
            response = self.client.post(
                "/binance/",
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
        self.assertEqual(run.error_message, "binance failed")

    def test_early_use_case_error_without_run_shows_form_error(self):
        before_count = PipelineRun.objects.count()
        use_case = EarlyFailingBinanceUseCase("could not create run")

        with patch("dashboard.views._build_binance_pipeline_use_case", return_value=use_case):
            response = self.client.post(
                "/binance/",
                data=self._form_data(),
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(PipelineRun.objects.count(), before_count)
        self.assertIn("could not create run", response.content.decode())

    def test_both_train_flags_false_show_form_error_without_use_case(self):
        before_count = PipelineRun.objects.count()
        use_case = RecordingBinanceUseCase()

        with patch("dashboard.views._build_binance_pipeline_use_case", return_value=use_case):
            response = self.client.post(
                "/binance/",
                data={
                    "symbol": "BTCUSDT",
                    "interval": "1h",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-02",
                    "target_horizon": "3",
                    "replay_steps": "5",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(PipelineRun.objects.count(), before_count)
        self.assertIsNone(use_case.symbol)
        self.assertIn("Выберите хотя бы одну модель", response.content.decode())

    @staticmethod
    def _form_data():
        return {
            "symbol": "BTCUSDT",
            "interval": "1h",
            "start_date": "2024-01-01",
            "end_date": "2024-01-02",
            "target_horizon": "3",
            "train_baseline": "on",
            "train_catboost": "on",
            "enable_forecast_replay": "on",
            "replay_steps": "5",
        }


class RecordingBinanceUseCase:
    def __init__(self):
        self.symbol = None
        self.interval = None
        self.start_date = None
        self.end_date = None
        self.target_horizon = None
        self.train_baseline = None
        self.train_catboost = None
        self.enable_forecast_replay = None
        self.replay_steps = None

    def execute(
        self,
        symbol,
        interval,
        start_date,
        end_date,
        target_horizon,
        train_baseline=True,
        train_catboost=True,
        enable_forecast_replay=False,
        replay_steps=5,
    ):
        self.symbol = symbol
        self.interval = interval
        self.start_date = start_date
        self.end_date = end_date
        self.target_horizon = target_horizon
        self.train_baseline = train_baseline
        self.train_catboost = train_catboost
        self.enable_forecast_replay = enable_forecast_replay
        self.replay_steps = replay_steps
        run = self._create_run(
            symbol=symbol,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
            target_horizon=target_horizon,
            status=PipelineRun.Status.SUCCESS,
        )
        return SimpleNamespace(
            run=run,
            raw_artifact=None,
            pipeline_result={"ok": True},
            error_message="",
        )

    @staticmethod
    def _create_run(
        symbol,
        interval,
        start_date,
        end_date,
        target_horizon,
        status,
        error_message="",
    ):
        return PipelineRun.objects.create(
            name=f"Binance pipeline {symbol} {interval}",
            status=status,
            symbols_json=[symbol],
            interval=interval,
            start_date=start_date,
            end_date=end_date,
            target_horizon=target_horizon,
            initiated_by="binance_cli",
            error_message=error_message,
        )


class FailingBinanceUseCase:
    def __init__(self, message):
        self.message = message

    def execute(self, symbol, interval, start_date, end_date, target_horizon, **kwargs):
        now = timezone.now()
        run = RecordingBinanceUseCase._create_run(
            symbol=symbol,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
            target_horizon=target_horizon,
            status=PipelineRun.Status.FAILED,
            error_message=self.message,
        )
        run.started_at = now
        run.finished_at = now
        run.save(update_fields=["started_at", "finished_at"])
        return SimpleNamespace(
            run=run,
            raw_artifact=None,
            pipeline_result=None,
            error_message=self.message,
        )


class EarlyFailingBinanceUseCase:
    def __init__(self, message):
        self.message = message

    def execute(self, *args, **kwargs):
        return SimpleNamespace(
            run=None,
            raw_artifact=None,
            pipeline_result=None,
            error_message=self.message,
        )
