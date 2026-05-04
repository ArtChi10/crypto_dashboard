from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from mlcore.evaluation import Evaluator
from mlcore.repositories import ArtifactRepository, ModelRepository
from mlcore.training import BaselineTrainer, SplitService


@dataclass(frozen=True)
class BaselineTrainingResult:
    model_path: Path
    metrics: dict[str, Any]
    feature_columns: list[str]
    train_rows: int
    valid_rows: int
    test_rows: int
    test_predictions: pd.DataFrame = field(default_factory=pd.DataFrame)
    model: Any | None = None


class BaselineTrainingService:
    TARGET_COLUMN = "target"

    def __init__(
        self,
        split_service: SplitService | None = None,
        trainer: BaselineTrainer | None = None,
        evaluator: Evaluator | None = None,
        artifact_repository: ArtifactRepository | None = None,
        model_repository: ModelRepository | None = None,
    ) -> None:
        self.split_service = split_service or SplitService()
        self.trainer = trainer or BaselineTrainer()
        self.evaluator = evaluator or Evaluator()
        self.artifact_repository = artifact_repository or ArtifactRepository(Path("runs"))
        self.model_repository = model_repository or ModelRepository()

    def train_and_evaluate(self, df: Any, run_id: int) -> BaselineTrainingResult:
        self._validate_dataset(df)
        feature_columns = self.trainer.get_feature_columns(df)
        if not feature_columns:
            raise ValueError("df must contain at least one numeric feature column.")

        train_df, valid_df, test_df = self.split_service.split(df)
        model = self.trainer.train(
            train_df[feature_columns],
            train_df[self.TARGET_COLUMN],
            x_valid=valid_df[feature_columns],
            y_valid=valid_df[self.TARGET_COLUMN],
        )
        test_predictions = self._test_predictions(model, test_df, feature_columns)
        metrics = self.evaluator.evaluate_predictions(
            test_predictions["y_true"],
            test_predictions["y_pred"],
            test_predictions.get("y_proba"),
        )
        model_path = self.artifact_repository.model_path(
            "baseline",
            run_id=run_id,
            extension="joblib",
        )
        self.model_repository.save(model, model_path)

        return BaselineTrainingResult(
            model_path=model_path,
            metrics=metrics,
            feature_columns=feature_columns,
            train_rows=len(train_df),
            valid_rows=len(valid_df),
            test_rows=len(test_df),
            test_predictions=test_predictions,
            model=model,
        )

    @classmethod
    def _validate_dataset(cls, df: Any) -> None:
        if cls.TARGET_COLUMN not in df.columns:
            raise ValueError(f"Missing required columns: {cls.TARGET_COLUMN}")

    def _test_predictions(
        self,
        model: Any,
        test_df: pd.DataFrame,
        feature_columns: list[str],
    ) -> pd.DataFrame:
        x_test = test_df[feature_columns]
        y_pred = np.asarray(model.predict(x_test)).ravel()
        predictions = pd.DataFrame(
            {
                "timestamp": test_df["timestamp"].reset_index(drop=True),
                "y_true": test_df[self.TARGET_COLUMN].reset_index(drop=True),
                "y_pred": y_pred,
            }
        )
        y_proba = self._positive_class_scores(model, x_test)
        if y_proba is not None:
            predictions["y_proba"] = y_proba

        return predictions

    @staticmethod
    def _positive_class_scores(model: Any, x_test: pd.DataFrame) -> np.ndarray | None:
        if not hasattr(model, "predict_proba"):
            return None

        scores = np.asarray(model.predict_proba(x_test))
        if scores.ndim == 2:
            if scores.shape[1] < 2:
                return None
            return scores[:, 1]

        return scores.ravel()
