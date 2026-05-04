from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path


class ArtifactRepository:
    DATASET_TYPES = frozenset({"raw", "processed", "final"})
    MODEL_TYPES = frozenset({"baseline", "catboost"})
    REPORT_TYPES = frozenset(
        {
            "price_plot",
            "target_distribution",
            "feature_importance",
            "metrics_plot",
            "stability_table",
            "stability_plot",
            "forecast_replay",
            "forecast_replay_table",
        }
    )

    _TIMESTAMP_PATTERN = re.compile(r"^\d{8}_\d{6}$")
    _SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]+$")
    _EXTENSION_PATTERN = re.compile(r"^[a-z0-9]+$")

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)

    def dataset_path(
        self,
        artifact_type: str,
        run_id: int,
        symbol: str | None = None,
        timestamp: str | None = None,
        extension: str = "parquet",
    ) -> Path:
        artifact_type = self._validate_type("artifact_type", artifact_type, self.DATASET_TYPES)
        run_id = self._validate_run_id(run_id)
        timestamp = self._normalize_timestamp(timestamp)
        extension = self._normalize_extension(extension)

        filename_parts = [artifact_type, "run", str(run_id)]
        if symbol:
            filename_parts.append(self._normalize_symbol(symbol))
        filename_parts.append(timestamp)

        directory = self.base_dir / "datasets" / artifact_type
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{'_'.join(filename_parts)}.{extension}"

    def model_path(
        self,
        model_type: str,
        run_id: int,
        timestamp: str | None = None,
        extension: str = "joblib",
    ) -> Path:
        model_type = self._validate_type("model_type", model_type, self.MODEL_TYPES)
        run_id = self._validate_run_id(run_id)
        timestamp = self._normalize_timestamp(timestamp)
        extension = self._normalize_extension(extension)

        directory = self.base_dir / "models"
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"model_{model_type}_run_{run_id}_{timestamp}.{extension}"

    def report_path(
        self,
        report_type: str,
        run_id: int,
        timestamp: str | None = None,
        extension: str = "png",
    ) -> Path:
        report_type = self._validate_type("report_type", report_type, self.REPORT_TYPES)
        run_id = self._validate_run_id(run_id)
        timestamp = self._normalize_timestamp(timestamp)
        extension = self._normalize_extension(extension)

        directory = self.base_dir / "reports"
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{report_type}_run_{run_id}_{timestamp}.{extension}"

    @classmethod
    def _validate_type(
        cls,
        field_name: str,
        value: str,
        allowed_values: frozenset[str],
    ) -> str:
        normalized = str(value).strip().lower()
        if normalized not in allowed_values:
            allowed = ", ".join(sorted(allowed_values))
            raise ValueError(f"Invalid {field_name}: {value!r}. Expected one of: {allowed}.")
        return normalized

    @staticmethod
    def _validate_run_id(run_id: int) -> int:
        if isinstance(run_id, bool):
            raise ValueError("run_id must be a positive integer.")

        try:
            normalized = int(run_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("run_id must be a positive integer.") from exc

        if normalized <= 0:
            raise ValueError("run_id must be a positive integer.")
        return normalized

    @classmethod
    def _normalize_timestamp(cls, timestamp: str | None) -> str:
        if timestamp is None:
            return datetime.now().strftime("%Y%m%d_%H%M%S")

        normalized = str(timestamp).strip()
        if not cls._TIMESTAMP_PATTERN.fullmatch(normalized):
            raise ValueError("timestamp must use YYYYMMDD_HHMMSS format.")
        return normalized

    @classmethod
    def _normalize_symbol(cls, symbol: str) -> str:
        normalized = str(symbol).strip().upper()
        if not cls._SYMBOL_PATTERN.fullmatch(normalized):
            raise ValueError("symbol must contain only letters and digits.")
        return normalized

    @classmethod
    def _normalize_extension(cls, extension: str) -> str:
        normalized = str(extension).strip().lower().lstrip(".")
        if not cls._EXTENSION_PATTERN.fullmatch(normalized):
            raise ValueError("extension must contain only letters and digits.")
        return normalized
