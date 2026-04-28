import tempfile
import unittest
from pathlib import Path

import pandas as pd

from mlcore.repositories.dataset_repository import DatasetRepository


class DatasetRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base_dir = Path(self.temp_dir.name)
        self.repo = DatasetRepository()
        self.df = pd.DataFrame(
            {
                "timestamp": ["2024-01-01", "2024-01-02"],
                "close": [42000.0, 42550.5],
                "symbol": ["BTCUSDT", "BTCUSDT"],
            }
        )

    def test_save_and_load_parquet(self):
        path = self.base_dir / "datasets" / "final" / "final_run_1.parquet"

        self.repo.save(self.df, path)
        loaded = self.repo.load(path)

        pd.testing.assert_frame_equal(loaded, self.df)

    def test_save_and_load_csv(self):
        path = self.base_dir / "datasets" / "raw" / "raw_run_1.csv"

        self.repo.save(self.df, path)
        loaded = self.repo.load(path)

        pd.testing.assert_frame_equal(loaded, self.df)

    def test_save_creates_parent_directories(self):
        path = self.base_dir / "nested" / "datasets" / "processed" / "processed_run_1.csv"

        self.repo.save(self.df, path)

        self.assertTrue(path.parent.is_dir())
        self.assertTrue(path.is_file())

    def test_invalid_extension_raises_value_error(self):
        path = self.base_dir / "datasets" / "final" / "final_run_1.json"

        with self.assertRaisesRegex(ValueError, "Unsupported dataset file extension"):
            self.repo.save(self.df, path)

        with self.assertRaisesRegex(ValueError, "Unsupported dataset file extension"):
            self.repo.load(path)


if __name__ == "__main__":
    unittest.main()
