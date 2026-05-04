from __future__ import annotations

import math
import random
from collections.abc import Iterable
from typing import Any


def bootstrap_mean_ci(
    values: Iterable[Any],
    n_bootstrap: int = 1000,
    confidence_level: float = 0.95,
    random_state: int | None = 42,
) -> dict[str, float | int | None]:
    """Estimate a bootstrap confidence interval for the mean."""
    if n_bootstrap < 1:
        raise ValueError("n_bootstrap must be at least 1.")
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be between 0 and 1.")

    clean_values = _clean_numeric_values(values)
    value_count = len(clean_values)
    if value_count == 0:
        return {"mean": None, "ci_lower": None, "ci_upper": None, "n": 0}

    mean_value = sum(clean_values) / value_count
    if value_count == 1:
        return {
            "mean": mean_value,
            "ci_lower": mean_value,
            "ci_upper": mean_value,
            "n": 1,
        }

    rng = random.Random(random_state)
    bootstrap_means = []
    for _ in range(n_bootstrap):
        sample_sum = sum(clean_values[rng.randrange(value_count)] for _ in range(value_count))
        bootstrap_means.append(sample_sum / value_count)
    bootstrap_means.sort()

    alpha = (1 - confidence_level) / 2
    return {
        "mean": mean_value,
        "ci_lower": _quantile(bootstrap_means, alpha),
        "ci_upper": _quantile(bootstrap_means, 1 - alpha),
        "n": value_count,
    }


def _clean_numeric_values(values: Iterable[Any]) -> list[float]:
    clean_values = []
    for value in values:
        if value is None:
            continue
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            continue
        if math.isnan(numeric_value):
            continue
        clean_values.append(numeric_value)
    return clean_values


def _quantile(sorted_values: list[float], quantile: float) -> float:
    if not sorted_values:
        raise ValueError("sorted_values must not be empty.")
    if quantile <= 0:
        return sorted_values[0]
    if quantile >= 1:
        return sorted_values[-1]

    position = (len(sorted_values) - 1) * quantile
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    if lower_index == upper_index:
        return sorted_values[lower_index]

    lower_value = sorted_values[lower_index]
    upper_value = sorted_values[upper_index]
    weight = position - lower_index
    return lower_value + (upper_value - lower_value) * weight
