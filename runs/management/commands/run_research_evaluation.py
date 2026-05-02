from __future__ import annotations

from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand, CommandError

from mlcore.evaluation.ablation import FeatureAblationService
from mlcore.evaluation.walk_forward import WalkForwardEvaluationService
from mlcore.repositories.dataset_repository import DatasetRepository
from mlcore.training.baseline_trainer import BaselineTrainer
from mlcore.training.dummy_trainer import DummyBaselineTrainer


class Command(BaseCommand):
    help = "Run offline research evaluations on a final dataset file."

    TRAINER_FACTORIES = {
        "dummy": DummyBaselineTrainer,
        "baseline": BaselineTrainer,
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "--dataset",
            required=True,
            help="Path to final .parquet or .csv dataset.",
        )
        parser.add_argument(
            "--output-dir",
            default="research_outputs",
            help="Directory for research output CSV files. Default: research_outputs.",
        )
        parser.add_argument(
            "--target-col",
            default="target",
            help="Target column name. Default: target.",
        )
        parser.add_argument(
            "--trainer",
            choices=sorted(self.TRAINER_FACTORIES),
            default="dummy",
            help="Trainer to evaluate. Choices: dummy, baseline. Default: dummy.",
        )
        parser.add_argument(
            "--run-walk-forward",
            action="store_true",
            help="Run walk-forward fold evaluation.",
        )
        parser.add_argument(
            "--run-ablation",
            action="store_true",
            help="Run feature ablation evaluation.",
        )
        parser.add_argument(
            "--train-window",
            type=int,
            default=200,
            help="Walk-forward train window row count. Default: 200.",
        )
        parser.add_argument(
            "--test-window",
            type=int,
            default=50,
            help="Walk-forward test window row count. Default: 50.",
        )
        parser.add_argument(
            "--step",
            type=int,
            default=None,
            help="Walk-forward step row count. Default: test-window.",
        )

    def handle(self, *args, **options):
        run_walk_forward = options["run_walk_forward"]
        run_ablation = options["run_ablation"]
        if not run_walk_forward and not run_ablation:
            raise CommandError(
                "Select at least one analysis: --run-walk-forward or --run-ablation."
            )

        dataset_path = Path(options["dataset"])
        if not dataset_path.is_file():
            raise CommandError(f"Dataset file does not exist: {dataset_path}")

        target_col = options["target_col"]
        trainer_name = options["trainer"]
        trainer_factory = self.TRAINER_FACTORIES[trainer_name]
        output_dir = Path(options["output_dir"])

        df = self._load_dataset(dataset_path)
        if target_col not in df.columns:
            raise CommandError(f"Dataset is missing target column: {target_col}")

        output_dir.mkdir(parents=True, exist_ok=True)
        output_paths = []

        if run_walk_forward:
            walk_forward_result = WalkForwardEvaluationService().evaluate(
                trainer_factory(),
                df,
                train_window=options["train_window"],
                test_window=options["test_window"],
                step=options["step"],
                target_col=target_col,
            )
            output_paths.append(
                self._save_result(
                    walk_forward_result,
                    output_dir / f"walk_forward_{trainer_name}.csv",
                )
            )

        if run_ablation:
            train_df, test_df = self._time_split(df)
            ablation_result = FeatureAblationService().evaluate_groups(
                trainer_factory,
                train_df,
                test_df,
                target_col=target_col,
            )
            output_paths.append(
                self._save_result(
                    ablation_result,
                    output_dir / f"ablation_{trainer_name}.csv",
                )
            )

        for output_path in output_paths:
            self.stdout.write(f"Created: {output_path.as_posix()}")

        self.stdout.write(self.style.SUCCESS("Research evaluation finished successfully."))

    @staticmethod
    def _load_dataset(path: Path) -> pd.DataFrame:
        try:
            return DatasetRepository().load(path)
        except Exception as exc:
            raise CommandError(f"Failed to load dataset: {exc}") from exc

    @staticmethod
    def _time_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        if "timestamp" not in df.columns:
            raise CommandError("Dataset is missing timestamp column required for ablation split.")

        sorted_df = df.copy()
        sorted_df["timestamp"] = pd.to_datetime(sorted_df["timestamp"])
        sorted_df = sorted_df.sort_values("timestamp").reset_index(drop=True)

        split_index = int(len(sorted_df) * 0.7)
        if split_index < 1 or split_index >= len(sorted_df):
            raise CommandError("Dataset must be large enough for non-empty train and test splits.")

        train_df = sorted_df.iloc[:split_index].reset_index(drop=True)
        test_df = sorted_df.iloc[split_index:].reset_index(drop=True)
        return train_df, test_df

    @staticmethod
    def _save_result(df: pd.DataFrame, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)
        return path
