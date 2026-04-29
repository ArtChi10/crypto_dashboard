from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
from catboost import CatBoostClassifier


class ModelRepository:
    SUPPORTED_EXTENSIONS = frozenset({".joblib", ".pkl", ".cbm"})

    def save(self, model: Any, path: str | Path) -> None:
        path = Path(path)
        extension = self._validate_extension(path)

        path.parent.mkdir(parents=True, exist_ok=True)
        if extension == ".cbm":
            self._save_catboost_model(model, path)
            return

        joblib.dump(model, path)

    def load(self, path: str | Path) -> Any:
        path = Path(path)
        extension = self._validate_extension(path)

        if extension == ".cbm":
            model = CatBoostClassifier()
            model.load_model(str(path))
            return model

        return joblib.load(path)

    @classmethod
    def _validate_extension(cls, path: Path) -> str:
        extension = path.suffix.lower()
        if extension not in cls.SUPPORTED_EXTENSIONS:
            allowed = ", ".join(sorted(cls.SUPPORTED_EXTENSIONS))
            raise ValueError(
                f"Unsupported model file extension: {path.suffix!r}. Expected one of: {allowed}."
            )
        return extension

    @staticmethod
    def _save_catboost_model(model: Any, path: Path) -> None:
        if not hasattr(model, "save_model"):
            raise ValueError("Models saved as .cbm must provide a save_model method.")

        model.save_model(str(path))
