import tempfile
import unittest
from pathlib import Path

from mlcore.repositories.artifact_repository import ArtifactRepository


class ArtifactRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base_dir = Path(self.temp_dir.name)
        self.repo = ArtifactRepository(self.base_dir)

    def test_dataset_path_with_symbol(self):
        path = self.repo.dataset_path(
            "raw",
            run_id=12,
            symbol="btcusdt",
            timestamp="20260427_120501",
        )

        self.assertEqual(
            path,
            self.base_dir / "datasets" / "raw" / "raw_run_12_BTCUSDT_20260427_120501.parquet",
        )
        self.assertTrue(path.parent.is_dir())

    def test_dataset_path_without_symbol(self):
        path = self.repo.dataset_path(
            "final",
            run_id=12,
            timestamp="20260427_120501",
        )

        self.assertEqual(
            path,
            self.base_dir / "datasets" / "final" / "final_run_12_20260427_120501.parquet",
        )
        self.assertTrue(path.parent.is_dir())

    def test_model_path(self):
        path = self.repo.model_path(
            "baseline",
            run_id=12,
            timestamp="20260427_120501",
        )

        self.assertEqual(
            path,
            self.base_dir / "models" / "model_baseline_run_12_20260427_120501.joblib",
        )
        self.assertTrue(path.parent.is_dir())

    def test_report_path(self):
        path = self.repo.report_path(
            "feature_importance",
            run_id=12,
            timestamp="20260427_120501",
        )

        self.assertEqual(
            path,
            self.base_dir / "reports" / "feature_importance_run_12_20260427_120501.png",
        )
        self.assertTrue(path.parent.is_dir())

    def test_custom_extension_accepts_leading_dot(self):
        path = self.repo.report_path(
            "metrics_plot",
            run_id=12,
            timestamp="20260427_120501",
            extension=".json",
        )

        self.assertEqual(
            path,
            self.base_dir / "reports" / "metrics_plot_run_12_20260427_120501.json",
        )

    def test_stability_table_report_path_uses_csv_extension(self):
        path = self.repo.report_path(
            "stability_table",
            run_id=12,
            timestamp="20260427_120501",
            extension="csv",
        )

        self.assertEqual(
            path,
            self.base_dir / "reports" / "stability_table_run_12_20260427_120501.csv",
        )
        self.assertTrue(path.parent.is_dir())

    def test_stability_plot_report_path_uses_png_extension(self):
        path = self.repo.report_path(
            "stability_plot",
            run_id=12,
            timestamp="20260427_120501",
            extension="png",
        )

        self.assertEqual(
            path,
            self.base_dir / "reports" / "stability_plot_run_12_20260427_120501.png",
        )
        self.assertTrue(path.parent.is_dir())

    def test_invalid_types_raise_value_error(self):
        with self.assertRaisesRegex(ValueError, "Invalid artifact_type"):
            self.repo.dataset_path(
                "temporary",
                run_id=12,
                timestamp="20260427_120501",
            )

        with self.assertRaisesRegex(ValueError, "Invalid model_type"):
            self.repo.model_path(
                "neural_net",
                run_id=12,
                timestamp="20260427_120501",
            )

        with self.assertRaisesRegex(ValueError, "Invalid report_type"):
            self.repo.report_path(
                "unknown",
                run_id=12,
                timestamp="20260427_120501",
            )


if __name__ == "__main__":
    unittest.main()
