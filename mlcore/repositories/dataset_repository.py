from __future__ import annotations

from pathlib import Path

import pandas as pd


class DatasetRepository:
    SUPPORTED_EXTENSIONS = frozenset({".csv", ".parquet"})

    def save(self, df: pd.DataFrame, path: str | Path) -> None:
        path = Path(path)
        extension = self._validate_extension(path)

        path.parent.mkdir(parents=True, exist_ok=True)
        if extension == ".parquet":
            df.to_parquet(path)
            return

        df.to_csv(path, index=False)

    def load(self, path: str | Path) -> pd.DataFrame:
        path = Path(path)
        extension = self._validate_extension(path)

        if extension == ".parquet":
            return pd.read_parquet(path)

        return pd.read_csv(path)

    @classmethod
    def _validate_extension(cls, path: Path) -> str:
        extension = path.suffix.lower()
        if extension not in cls.SUPPORTED_EXTENSIONS:
            allowed = ", ".join(sorted(cls.SUPPORTED_EXTENSIONS))
            raise ValueError(
                f"Unsupported dataset file extension: {path.suffix!r}. Expected one of: {allowed}."
            )
        return extension
