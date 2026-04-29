import tempfile
import unittest
from pathlib import Path

import pandas as pd

from mlcore.features import FeatureBuilder
from mlcore.repositories import ArtifactRepository, DatasetRepository
from mlcore.services import DatasetPreparationService


class DatasetPreparationServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base_dir = Path(self.temp_dir.name)
        self.dataset_repository = DatasetRepository()
        self.service = DatasetPreparationService(
            artifact_repository=ArtifactRepository(self.base_dir),
            dataset_repository=self.dataset_repository,
        )

    def test_prepare_cleans_builds_features_target_and_saves_parquet_artifacts(self):
        raw_df = self._make_raw_frame()

        result = self.service.prepare(raw_df, run_id=7, horizon=3, symbol="BTCUSDT")

        self.assertTrue(result.processed_path.is_file())
        self.assertTrue(result.final_path.is_file())
        self.assertEqual(result.processed_path.suffix, ".parquet")
        self.assertEqual(result.final_path.suffix, ".parquet")
        self.assertIn("BTCUSDT", result.processed_path.name)
        self.assertIn("BTCUSDT", result.final_path.name)
        self.assertEqual(result.raw_rows, 60)
        self.assertEqual(result.processed_rows, 60)
        self.assertEqual(result.final_rows, 43)
        self.assertEqual(result.feature_columns, list(FeatureBuilder.FEATURE_COLUMNS))
        self.assertEqual(result.target_column, "target")

        processed_df = self.dataset_repository.load(result.processed_path)
        final_df = self.dataset_repository.load(result.final_path)
        self.assertEqual(len(processed_df), result.processed_rows)
        self.assertEqual(len(final_df), result.final_rows)
        self.assertIn("target", final_df.columns)
        for column in FeatureBuilder.FEATURE_COLUMNS:
            self.assertIn(column, final_df.columns)

    def test_prepare_allows_dataset_without_symbol_in_artifact_name(self):
        result = self.service.prepare(self._make_raw_frame(), run_id=3, horizon=3)

        self.assertNotIn("BTCUSDT", result.processed_path.name)
        self.assertNotIn("BTCUSDT", result.final_path.name)
        self.assertTrue(result.processed_path.is_file())
        self.assertTrue(result.final_path.is_file())

    def test_prepare_uses_same_timestamp_for_processed_and_final_artifacts(self):
        result = self.service.prepare(self._make_raw_frame(), run_id=5, horizon=3)

        processed_timestamp = result.processed_path.stem.removeprefix("processed_run_5_")
        final_timestamp = result.final_path.stem.removeprefix("final_run_5_")

        self.assertEqual(processed_timestamp, final_timestamp)

    def test_prepare_raises_for_missing_raw_columns(self):
        raw_df = self._make_raw_frame().drop(columns=["close"])

        with self.assertRaisesRegex(ValueError, "Missing required columns: close"):
            self.service.prepare(raw_df, run_id=1)

    @staticmethod
    def _make_raw_frame(row_count: int = 60) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=row_count, freq="h"),
                "open": range(1, row_count + 1),
                "high": range(2, row_count + 2),
                "low": range(0, row_count),
                "close": range(1, row_count + 1),
                "volume": range(100, 100 + row_count),
                "symbol": ["BTCUSDT"] * row_count,
            }
        )


if __name__ == "__main__":
    unittest.main()
