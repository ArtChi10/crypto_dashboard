import os
import tempfile
import unittest
from io import StringIO
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
import pandas as pd
from django.core.management import call_command
from django.core.management.base import CommandError

django.setup()


class RunResearchEvaluationCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.parquet_path = self.base_path / "final.parquet"
        self.csv_path = self.base_path / "final.csv"
        self.output_dir = self.base_path / "out"
        self._dataset().to_parquet(self.parquet_path, index=False)
        self._dataset().to_csv(self.csv_path, index=False)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_command_creates_walk_forward_and_ablation_outputs_from_parquet(self):
        out = StringIO()

        call_command(
            "run_research_evaluation",
            "--dataset",
            str(self.parquet_path),
            "--output-dir",
            str(self.output_dir),
            "--trainer",
            "dummy",
            "--run-walk-forward",
            "--run-ablation",
            "--train-window",
            "20",
            "--test-window",
            "10",
            stdout=out,
        )

        walk_forward_path = self.output_dir / "walk_forward_dummy.csv"
        ablation_path = self.output_dir / "ablation_dummy.csv"
        self.assertTrue(walk_forward_path.exists())
        self.assertTrue(ablation_path.exists())

        walk_forward = pd.read_csv(walk_forward_path)
        ablation = pd.read_csv(ablation_path)
        self.assertEqual(len(walk_forward), 4)
        self.assertIn("fold_id", walk_forward.columns)
        self.assertIn("accuracy", walk_forward.columns)
        self.assertIn("all_features", ablation["experiment"].tolist())
        self.assertIn("without_price_raw", ablation["experiment"].tolist())

        output = out.getvalue()
        self.assertIn(walk_forward_path.as_posix(), output)
        self.assertIn(ablation_path.as_posix(), output)

    def test_command_loads_csv_dataset_for_ablation(self):
        out = StringIO()

        call_command(
            "run_research_evaluation",
            "--dataset",
            str(self.csv_path),
            "--output-dir",
            str(self.output_dir),
            "--trainer",
            "dummy",
            "--run-ablation",
            stdout=out,
        )

        ablation_path = self.output_dir / "ablation_dummy.csv"
        self.assertTrue(ablation_path.exists())
        result = pd.read_csv(ablation_path)
        self.assertEqual(result.loc[0, "experiment"], "all_features")
        self.assertIn(ablation_path.as_posix(), out.getvalue())

    def test_command_creates_catboost_walk_forward_output(self):
        out = StringIO()

        call_command(
            "run_research_evaluation",
            "--dataset",
            str(self.parquet_path),
            "--output-dir",
            str(self.output_dir),
            "--trainer",
            "catboost",
            "--run-walk-forward",
            "--train-window",
            "20",
            "--test-window",
            "10",
            stdout=out,
        )

        walk_forward_path = self.output_dir / "walk_forward_catboost.csv"
        self.assertTrue(walk_forward_path.exists())
        result = pd.read_csv(walk_forward_path)
        self.assertEqual(len(result), 4)
        self.assertIn("fold_id", result.columns)
        self.assertIn("accuracy", result.columns)
        self.assertIn("error_message", result.columns)
        self.assertIn(walk_forward_path.as_posix(), out.getvalue())

    def test_command_creates_catboost_ablation_output(self):
        out = StringIO()

        call_command(
            "run_research_evaluation",
            "--dataset",
            str(self.csv_path),
            "--output-dir",
            str(self.output_dir),
            "--trainer",
            "catboost",
            "--run-ablation",
            stdout=out,
        )

        ablation_path = self.output_dir / "ablation_catboost.csv"
        self.assertTrue(ablation_path.exists())
        result = pd.read_csv(ablation_path)
        self.assertIn("experiment", result.columns)
        self.assertIn("accuracy", result.columns)
        self.assertIn("error_message", result.columns)
        self.assertIn("all_features", result["experiment"].tolist())
        self.assertIn(ablation_path.as_posix(), out.getvalue())

    def test_invalid_dataset_path_raises_command_error(self):
        with self.assertRaises(CommandError):
            call_command(
                "run_research_evaluation",
                "--dataset",
                str(self.base_path / "missing.parquet"),
                "--run-walk-forward",
            )

    def test_no_selected_analysis_raises_command_error(self):
        with self.assertRaises(CommandError):
            call_command(
                "run_research_evaluation",
                "--dataset",
                str(self.parquet_path),
            )

    def test_missing_target_column_raises_command_error(self):
        path = self.base_path / "missing_target.csv"
        self._dataset().drop(columns=["target"]).to_csv(path, index=False)

        with self.assertRaises(CommandError):
            call_command(
                "run_research_evaluation",
                "--dataset",
                str(path),
                "--run-ablation",
            )

    @staticmethod
    def _dataset():
        row_count = 60
        return pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=row_count, freq="h"),
                "open": range(row_count),
                "high": range(1, row_count + 1),
                "low": range(row_count),
                "close": range(row_count),
                "return_1": [0.1] * row_count,
                "return_3": [0.2] * row_count,
                "volume": range(100, 100 + row_count),
                "target": [index % 2 for index in range(row_count)],
            }
        )


if __name__ == "__main__":
    unittest.main()
