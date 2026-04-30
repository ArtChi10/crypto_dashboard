from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand, CommandError

from mlcore.services.binance_pipeline_use_case import BinancePipelineUseCase


class Command(BaseCommand):
    help = "Download Binance OHLCV candles and run the ML pipeline."

    def add_arguments(self, parser):
        parser.add_argument("--symbol", required=True, help="Trading symbol, for example BTCUSDT.")
        parser.add_argument("--interval", default="1h", help="Candle interval. Default: 1h.")
        parser.add_argument(
            "--start-date",
            required=True,
            help="Dataset start date in YYYY-MM-DD format.",
        )
        parser.add_argument(
            "--end-date",
            required=True,
            help="Dataset end date in YYYY-MM-DD format.",
        )
        parser.add_argument(
            "--target-horizon",
            type=int,
            default=3,
            help="Target horizon in rows. Default: 3.",
        )
        parser.add_argument(
            "--skip-baseline",
            action="store_true",
            help="Do not train the baseline LogisticRegression model.",
        )
        parser.add_argument(
            "--skip-catboost",
            action="store_true",
            help="Do not train the CatBoost model.",
        )

    def handle(self, *args, **options):
        train_baseline = not options["skip_baseline"]
        train_catboost = not options["skip_catboost"]
        if not train_baseline and not train_catboost:
            raise CommandError("At least one model must be enabled.")

        start_date = self._parse_date(options["start_date"], "--start-date")
        end_date = self._parse_date(options["end_date"], "--end-date")
        if end_date <= start_date:
            raise CommandError("--end-date must be greater than --start-date.")

        target_horizon = options["target_horizon"]
        if target_horizon < 1:
            raise CommandError("--target-horizon must be greater than or equal to 1.")

        result = BinancePipelineUseCase().execute(
            symbol=options["symbol"],
            interval=options["interval"],
            start_date=start_date,
            end_date=end_date,
            target_horizon=target_horizon,
            train_baseline=train_baseline,
            train_catboost=train_catboost,
        )

        if result.run is None:
            raise CommandError(
                result.error_message or "Binance pipeline failed before run creation."
            )

        self.stdout.write(f"Run id: {result.run.id}")
        self.stdout.write(f"Run status: {result.run.status}")
        self.stdout.write(f"Detail URL: /runs/{result.run.id}/")

        if result.error_message:
            self.stderr.write(result.error_message)
            raise CommandError(result.error_message)

        self.stdout.write(self.style.SUCCESS("Binance pipeline finished successfully."))

    @staticmethod
    def _parse_date(value: str, option_name: str) -> date:
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise CommandError(f"{option_name} must use YYYY-MM-DD format.") from exc
