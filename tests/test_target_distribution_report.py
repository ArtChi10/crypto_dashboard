import tempfile
import unittest
from pathlib import Path

import pandas as pd

from mlcore.repositories import ArtifactRepository
from mlcore.services import CatBoostTrainingService, FullPipelineService
from mlcore.services.report_service import TargetDistributionReportService
from mlcore.training import CatBoostTrainer


class TargetDistributionReportServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base_dir = Path(self.temp_dir.name)

    def test_build_creates_png_from_final_dataframe(self):
        path = self.base_dir / "reports" / "target_distribution.png"
        final_df = pd.DataFrame({"target": [0, 1, 1, 0, 1]})

        result_path = TargetDistributionReportService().build(final_df, path)

        self.assertEqual(result_path, path)
        self.assertTrue(path.is_file())
        self.assertGreater(path.stat().st_size, 0)
        self.assertEqual(path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_build_accepts_target_series(self):
        path = self.base_dir / "target_distribution.png"
        target = pd.Series([0, 0, 1], name="target")

        result_path = TargetDistributionReportService().build(target, path)

        self.assertEqual(result_path, path)
        self.assertTrue(path.is_file())

    def test_build_raises_when_target_column_is_missing(self):
        with self.assertRaisesRegex(ValueError, "Missing required columns: target"):
            TargetDistributionReportService().build(
                pd.DataFrame({"feature": [1, 2, 3]}),
                self.base_dir / "target_distribution.png",
            )

    def test_full_pipeline_creates_target_distribution_report_path(self):
        artifact_repository = ArtifactRepository(self.base_dir)
        service = FullPipelineService(
            catboost_training_service=CatBoostTrainingService(
                artifact_repository=artifact_repository,
                trainer=CatBoostTrainer(iterations=5, verbose=False),
            )
        )

        result = service.run(self._make_raw_frame(), run_id=11, horizon=3, symbol="BTCUSDT")

        self.assertIsNotNone(result.target_distribution_report_path)
        self.assertTrue(result.target_distribution_report_path.is_file())
        self.assertEqual(result.target_distribution_report_path.suffix, ".png")
        self.assertIn("target_distribution", result.target_distribution_report_path.name)

    @staticmethod
    def _make_raw_frame(row_count: int = 90) -> pd.DataFrame:
        close_pattern = [1, 3, 2, 4]
        close_values = [close_pattern[index % len(close_pattern)] for index in range(row_count)]
        return pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=row_count, freq="h"),
                "open": close_values,
                "high": [value + 1 for value in close_values],
                "low": [value - 1 for value in close_values],
                "close": close_values,
                "volume": range(100, 100 + row_count),
                "symbol": ["BTCUSDT"] * row_count,
            }
        )


if __name__ == "__main__":
    unittest.main()
