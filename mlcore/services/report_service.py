from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib
import pandas as pd

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


class TargetDistributionReportService:
    TARGET_COLUMN = "target"

    def build(self, final_df_or_target: Any, path: str | Path) -> Path:
        target = self._target_series(final_df_or_target)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        counts = target.value_counts().to_dict()
        labels = ["0", "1"]
        values = [int(counts.get(0, 0)), int(counts.get(1, 0))]

        figure, axis = plt.subplots(figsize=(5, 3.2))
        axis.bar(labels, values, color=["#175cd3", "#17663a"])
        axis.set_title("Target distribution")
        axis.set_xlabel("target")
        axis.set_ylabel("count")
        axis.bar_label(axis.containers[0], padding=3)
        axis.margins(y=0.18)
        figure.tight_layout()
        figure.savefig(path, format="png", dpi=120)
        plt.close(figure)

        return path

    @classmethod
    def _target_series(cls, final_df_or_target: Any) -> pd.Series:
        if isinstance(final_df_or_target, pd.Series):
            return final_df_or_target

        if cls.TARGET_COLUMN not in final_df_or_target.columns:
            raise ValueError(f"Missing required columns: {cls.TARGET_COLUMN}")

        return final_df_or_target[cls.TARGET_COLUMN]
