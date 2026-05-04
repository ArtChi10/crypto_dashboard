import tempfile
import unittest
from pathlib import Path

import pandas as pd

from mlcore.services.report_service import ForecastReplayReportService


class ForecastReplayReportServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base_dir = Path(self.temp_dir.name)

    def test_build_creates_png(self):
        path = self.base_dir / "reports" / "forecast_replay.png"

        result_path = ForecastReplayReportService().build(
            history_df=self._history(),
            replay_df=self._replay(),
            path=path,
        )

        self.assertEqual(result_path, path)
        self.assert_png(path)

    def test_build_raises_for_empty_replay(self):
        with self.assertRaisesRegex(ValueError, "replay_df must not be empty"):
            ForecastReplayReportService().build(
                history_df=self._history(),
                replay_df=self._replay().iloc[0:0],
                path=self.base_dir / "empty.png",
            )

    @staticmethod
    def _history():
        return pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=12, freq="h"),
                "close": [100, 101, 102, 101, 103, 104, 103, 105, 106, 105, 107, 108],
            }
        )

    @staticmethod
    def _replay():
        return pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01 12:00:00", periods=4, freq="h"),
                "close": [108, 109, 107, 110],
                "future_close": [111, 108, 112, 109],
                "actual_direction": [1, 0, 1, 0],
                "predicted_direction": [1, 1, 0, 0],
                "predicted_probability": [0.8, 0.7, None, 0.2],
                "is_correct": [True, False, False, True],
            }
        )

    def assert_png(self, path):
        self.assertTrue(path.is_file())
        self.assertGreater(path.stat().st_size, 0)
        self.assertEqual(path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")


if __name__ == "__main__":
    unittest.main()
