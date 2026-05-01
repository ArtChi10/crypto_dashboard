from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from mlcore.evaluation import Evaluator
from mlcore.repositories import ArtifactRepository, ModelRepository
from mlcore.training import DummyBaselineTrainer, SplitService


@dataclass(frozen=True)
class DummyTrainingResult:
    model_path: Path
    metrics: dict[str, Any]
    feature_columns: list[str]
    train_rows: int
    valid_rows: int
    test_rows: int


class DummyTrainingService:
    TARGET_COLUMN = "target"
    MODEL_TYPE = "dummy"

    def __init__(
        self,
        split_service: SplitService | None = None,
        trainer: DummyBaselineTrainer | None = None,
        evaluator: Evaluator | None = None,
        artifact_repository: ArtifactRepository | None = None,
        model_repository: ModelRepository | None = None,
    ) -> None:
        self.split_service = split_service or SplitService()
        self.trainer = trainer or DummyBaselineTrainer()
        self.evaluator = evaluator or Evaluator()
        self.artifact_repository = artifact_repository or ArtifactRepository(Path("runs"))
        self.model_repository = model_repository or ModelRepository()

    def train_and_evaluate(self, df: Any, run_id: int) -> DummyTrainingResult:
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
        metrics = self._evaluate_model(
            model,
            test_df[feature_columns],
            test_df[self.TARGET_COLUMN],
        )
        model_path = self._model_path(run_id)
        self.model_repository.save(model, model_path)

        return DummyTrainingResult(
            model_path=model_path,
            metrics=metrics,
            feature_columns=feature_columns,
            train_rows=len(train_df),
            valid_rows=len(valid_df),
            test_rows=len(test_df),
        )

    def _evaluate_model(self, model: Any, x_test: Any, y_test: Any) -> dict[str, Any]:
        y_pred = model.predict(x_test)
        y_proba = None
        if hasattr(model, "predict_proba") and len(getattr(model, "classes_", [])) >= 2:
            y_proba = model.predict_proba(x_test)

        return self.evaluator.evaluate_predictions(y_test, y_pred, y_proba)

    def _model_path(self, run_id: int) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        directory = self.artifact_repository.base_dir / "models"
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"model_{self.MODEL_TYPE}_run_{run_id}_{timestamp}.joblib"

    @classmethod
    def _validate_dataset(cls, df: Any) -> None:
        if cls.TARGET_COLUMN not in df.columns:
            raise ValueError(f"Missing required columns: {cls.TARGET_COLUMN}")
