from __future__ import annotations

from typing import Any

import pandas as pd
import requests


class BinanceMarketDataError(RuntimeError):
    """Raised when Binance market data cannot be loaded."""


class BinanceMarketDataProvider:
    BASE_URL = "https://api.binance.com"
    KLINES_PATH = "/api/v3/klines"
    LIMIT = 1000
    OUTPUT_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume", "symbol")
    NUMERIC_COLUMNS = ("open", "high", "low", "close", "volume")

    def __init__(
        self,
        base_url: str = BASE_URL,
        session: requests.Session | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.timeout = timeout

    def get_ohlcv(self, symbol: str, interval: str, start: Any, end: Any) -> pd.DataFrame:
        normalized_symbol = self._normalize_symbol(symbol)
        start_ms = self._to_milliseconds(start, name="start")
        end_ms = self._to_milliseconds(end, name="end")
        if end_ms <= start_ms:
            raise ValueError("end must be greater than start.")

        rows: list[list[Any]] = []
        next_start_ms = start_ms

        while next_start_ms <= end_ms:
            page = self._get_klines_page(
                symbol=normalized_symbol,
                interval=interval,
                start_ms=next_start_ms,
                end_ms=end_ms,
            )
            if not page:
                if not rows:
                    raise BinanceMarketDataError(
                        "Binance returned no klines for the requested range."
                    )
                break

            rows.extend(page)
            last_open_time = int(page[-1][0])
            if last_open_time < next_start_ms:
                raise BinanceMarketDataError("Binance pagination did not advance.")

            next_start_ms = last_open_time + 1
            if len(page) < self.LIMIT:
                break

        return self._to_dataframe(rows, normalized_symbol)

    def _get_klines_page(
        self,
        symbol: str,
        interval: str,
        start_ms: int,
        end_ms: int,
    ) -> list[list[Any]]:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": self.LIMIT,
        }

        try:
            response = self.session.get(
                f"{self.base_url}{self.KLINES_PATH}",
                params=params,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise BinanceMarketDataError(f"Binance request failed: {exc}") from exc

        if response.status_code != 200:
            raise BinanceMarketDataError(
                f"Binance request failed with status {response.status_code}: {response.text}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise BinanceMarketDataError("Binance returned invalid JSON.") from exc

        if not isinstance(payload, list):
            raise BinanceMarketDataError("Binance returned an unexpected response payload.")

        return payload

    @classmethod
    def _to_dataframe(cls, rows: list[list[Any]], symbol: str) -> pd.DataFrame:
        frame = pd.DataFrame(
            rows,
            columns=[
                "open_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "quote_asset_volume",
                "number_of_trades",
                "taker_buy_base_volume",
                "taker_buy_quote_volume",
                "ignore",
            ],
        )

        result = pd.DataFrame()
        result["timestamp"] = pd.to_datetime(
            frame["open_time"],
            unit="ms",
            utc=True,
        ).dt.tz_convert(None)
        for column in cls.NUMERIC_COLUMNS:
            result[column] = pd.to_numeric(frame[column], errors="coerce")
        result["symbol"] = symbol

        return result.loc[:, cls.OUTPUT_COLUMNS].reset_index(drop=True)

    @staticmethod
    def _to_milliseconds(value: Any, name: str) -> int:
        try:
            timestamp = pd.to_datetime(value, utc=True)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be a valid date or datetime.") from exc

        if pd.isna(timestamp):
            raise ValueError(f"{name} must be a valid date or datetime.")

        return int(timestamp.value // 1_000_000)

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        normalized = str(symbol or "").strip().upper()
        if not normalized:
            raise ValueError("symbol must not be empty.")
        return normalized
