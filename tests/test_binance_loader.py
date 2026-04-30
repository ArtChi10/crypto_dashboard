import unittest

import requests
from pandas.api.types import is_datetime64_any_dtype, is_numeric_dtype

from mlcore.loaders.binance_loader import BinanceMarketDataError, BinanceMarketDataProvider


class FakeResponse:
    def __init__(self, payload, status_code=200, text="OK"):
        self.payload = payload
        self.status_code = status_code
        self.text = text

    def json(self):
        return self.payload


class InvalidJsonResponse(FakeResponse):
    def json(self):
        raise ValueError("invalid json")


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class BinanceMarketDataProviderTests(unittest.TestCase):
    def test_get_ohlcv_returns_normalized_dataframe(self):
        session = FakeSession(
            [
                FakeResponse(
                    [
                        self._kline(
                            1_704_067_200_000,
                            "42100.5",
                            "42200.0",
                            "42000.0",
                            "42150.5",
                            "12.3",
                        ),
                        self._kline(
                            1_704_070_800_000,
                            "42150.5",
                            "42300.0",
                            "42100.0",
                            "42210.0",
                            "15.0",
                        ),
                    ]
                )
            ]
        )
        provider = BinanceMarketDataProvider(session=session, timeout=3.5)

        df = provider.get_ohlcv("btcusdt", "1h", "2024-01-01", "2024-01-02")

        self.assertEqual(
            list(df.columns),
            ["timestamp", "open", "high", "low", "close", "volume", "symbol"],
        )
        self.assertEqual(len(df), 2)
        self.assertTrue(is_datetime64_any_dtype(df["timestamp"]))
        for column in ["open", "high", "low", "close", "volume"]:
            self.assertTrue(is_numeric_dtype(df[column]))
        self.assertEqual(df["symbol"].tolist(), ["BTCUSDT", "BTCUSDT"])
        self.assertEqual(session.calls[0]["url"], "https://api.binance.com/api/v3/klines")
        self.assertEqual(
            session.calls[0]["params"],
            {
                "symbol": "BTCUSDT",
                "interval": "1h",
                "startTime": 1_704_067_200_000,
                "endTime": 1_704_153_600_000,
                "limit": 1000,
            },
        )
        self.assertEqual(session.calls[0]["timeout"], 3.5)

    def test_get_ohlcv_paginates_large_ranges(self):
        first_page = [self._kline(1_704_067_200_000 + index * 3_600_000) for index in range(1000)]
        second_page = [self._kline(1_707_667_200_000)]
        session = FakeSession([FakeResponse(first_page), FakeResponse(second_page)])
        provider = BinanceMarketDataProvider(session=session)

        df = provider.get_ohlcv("BTCUSDT", "1h", "2024-01-01", "2024-02-15")

        self.assertEqual(len(df), 1001)
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(
            session.calls[1]["params"]["startTime"],
            int(first_page[-1][0]) + 1,
        )

    def test_non_200_response_raises_market_data_error(self):
        session = FakeSession([FakeResponse({"code": -1121}, status_code=400, text="Bad symbol")])
        provider = BinanceMarketDataProvider(session=session)

        with self.assertRaisesRegex(BinanceMarketDataError, "status 400"):
            provider.get_ohlcv("BAD", "1h", "2024-01-01", "2024-01-02")

    def test_empty_response_raises_market_data_error(self):
        session = FakeSession([FakeResponse([])])
        provider = BinanceMarketDataProvider(session=session)

        with self.assertRaisesRegex(BinanceMarketDataError, "no klines"):
            provider.get_ohlcv("BTCUSDT", "1h", "2024-01-01", "2024-01-02")

    def test_network_error_raises_market_data_error(self):
        session = FakeSession([requests.Timeout("timed out")])
        provider = BinanceMarketDataProvider(session=session)

        with self.assertRaisesRegex(BinanceMarketDataError, "request failed"):
            provider.get_ohlcv("BTCUSDT", "1h", "2024-01-01", "2024-01-02")

    def test_invalid_json_raises_market_data_error(self):
        session = FakeSession([InvalidJsonResponse(None)])
        provider = BinanceMarketDataProvider(session=session)

        with self.assertRaisesRegex(BinanceMarketDataError, "invalid JSON"):
            provider.get_ohlcv("BTCUSDT", "1h", "2024-01-01", "2024-01-02")

    def test_invalid_dates_raise_value_error(self):
        provider = BinanceMarketDataProvider(session=FakeSession([]))

        with self.assertRaisesRegex(ValueError, "end must be greater than start"):
            provider.get_ohlcv("BTCUSDT", "1h", "2024-01-02", "2024-01-01")

    @staticmethod
    def _kline(
        open_time,
        open_price="1.0",
        high="2.0",
        low="0.5",
        close="1.5",
        volume="10.0",
    ):
        return [
            open_time,
            open_price,
            high,
            low,
            close,
            volume,
            open_time + 3_599_999,
            "100.0",
            10,
            "5.0",
            "50.0",
            "0",
        ]


if __name__ == "__main__":
    unittest.main()
