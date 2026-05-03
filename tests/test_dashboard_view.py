import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.test import Client, TestCase

django.setup()

from runs.models import PipelineRun  # noqa: E402


class DashboardViewTests(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="localhost")

    def test_get_returns_overview_with_pipeline_entry_points(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("/binance/", html)
        self.assertIn("/upload/", html)
        self.assertIn("/runs/", html)
        self.assertIn("Что делает проект", html)
        self.assertIn("research dashboard", html)

    def test_get_does_not_show_empty_run_creation_form(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertNotIn('method="post"', html)
        self.assertNotIn("Создать запуск", html)
        self.assertNotIn("symbols", html)
        self.assertNotIn("train_main_model", html)

    def test_post_is_not_allowed_and_does_not_create_run(self):
        before_count = PipelineRun.objects.count()

        response = self.client.post(
            "/",
            data={
                "symbols": "BTCUSDT",
                "interval": "1h",
                "start_date": "2024-01-01",
                "end_date": "2024-01-02",
                "target_horizon": "3",
            },
        )

        self.assertEqual(response.status_code, 405)
        self.assertEqual(PipelineRun.objects.count(), before_count)

    def test_latest_runs_are_still_displayed(self):
        run = PipelineRun.objects.create(
            name="Successful Binance run",
            status=PipelineRun.Status.SUCCESS,
            symbols_json=["BTCUSDT"],
            interval="1h",
            target_horizon=3,
            initiated_by="binance_cli",
        )

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("Successful Binance run", html)
        self.assertIn(f"/runs/{run.id}/", html)

    def test_empty_state_points_to_real_pipeline_entry_points(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Запусков пока нет. Запустите Binance pipeline или загрузите CSV dataset.",
            response.content.decode(),
        )
