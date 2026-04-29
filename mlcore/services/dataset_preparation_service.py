from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from mlcore.features import FeatureBuilder
from mlcore.preprocessing import DataCleaner
from mlcore.repositories import ArtifactRepository, DatasetRepository
from mlcore.targets import TargetBuilder


@dataclass(frozen=True)
class DatasetPreparationResult:
    processed_path: Path
    final_path: Path
    raw_rows: int
    processed_rows: int
    final_rows: int
    feature_columns: list[str]
    target_column: str


class DatasetPreparationService:
    TARGET_COLUMN = "target"

    def __init__(
        self,
        cleaner: DataCleaner | None = None,
        feature_builder: FeatureBuilder | None = None,
        target_builder: TargetBuilder | None = None,
        artifact_repository: ArtifactRepository | None = None,
        dataset_repository: DatasetRepository | None = None,
    ) -> None:
        self.cleaner = cleaner or DataCleaner()
        self.feature_builder = feature_builder or FeatureBuilder()
        self.target_builder = target_builder or TargetBuilder()
        self.artifact_repository = artifact_repository or ArtifactRepository(Path("runs"))
        self.dataset_repository = dataset_repository or DatasetRepository()

    def prepare(
        self,
        raw_df: Any,
        run_id: int,
        horizon: int = 3,
        symbol: str | None = None,
    ) -> DatasetPreparationResult:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        processed_df = self.cleaner.clean(raw_df)
        processed_path = self.artifact_repository.dataset_path(
            "processed",
            run_id=run_id,
            symbol=symbol,
            timestamp=timestamp,
            extension="parquet",
        )
        self.dataset_repository.save(processed_df, processed_path)

        feature_df = self.feature_builder.build(processed_df)
        final_df = self.target_builder.build(feature_df, horizon=horizon)
        final_path = self.artifact_repository.dataset_path(
            "final",
            run_id=run_id,
            symbol=symbol,
            timestamp=timestamp,
            extension="parquet",
        )
        self.dataset_repository.save(final_df, final_path)

        feature_columns = [
            column for column in self.feature_builder.FEATURE_COLUMNS if column in final_df.columns
        ]

        return DatasetPreparationResult(
            processed_path=processed_path,
            final_path=final_path,
            raw_rows=len(raw_df),
            processed_rows=len(processed_df),
            final_rows=len(final_df),
            feature_columns=feature_columns,
            target_column=self.TARGET_COLUMN,
        )
