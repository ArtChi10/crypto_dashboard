from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


class Evaluator:
    def evaluate_predictions(
        self,
        y_true: Any,
        y_pred: Any,
        y_proba: Any | None = None,
    ) -> dict[str, Any]:
        return {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "precision": float(precision_score(y_true, y_pred, zero_division=0)),
            "recall": float(recall_score(y_true, y_pred, zero_division=0)),
            "f1": float(f1_score(y_true, y_pred, zero_division=0)),
            "roc_auc": self._roc_auc(y_true, y_proba),
            "confusion_matrix": confusion_matrix(y_true, y_pred, labels=[0, 1]).tolist(),
        }

    def evaluate_model(self, model: Any, x_test: Any, y_test: Any) -> dict[str, Any]:
        y_pred = model.predict(x_test)
        y_proba = None
        if hasattr(model, "predict_proba"):
            y_proba = model.predict_proba(x_test)

        return self.evaluate_predictions(y_test, y_pred, y_proba)

    def _roc_auc(self, y_true: Any, y_proba: Any | None) -> float | None:
        if y_proba is None or self._has_single_class(y_true):
            return None

        return float(roc_auc_score(y_true, self._positive_class_scores(y_proba)))

    @staticmethod
    def _has_single_class(y_true: Any) -> bool:
        return np.unique(np.asarray(y_true).ravel()).size < 2

    @staticmethod
    def _positive_class_scores(y_proba: Any) -> Any:
        scores = np.asarray(y_proba)
        if scores.ndim == 2:
            if scores.shape[1] < 2:
                raise ValueError("y_proba must include positive class probabilities.")
            return scores[:, 1]

        return scores
