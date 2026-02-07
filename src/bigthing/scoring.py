from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np


def _zscore(values: List[float]) -> List[float]:
    arr = np.array(values, dtype=float)
    mean = float(np.nanmean(arr))
    std = float(np.nanstd(arr))
    if std == 0 or np.isnan(std):
        return [0.0 for _ in values]
    z = (arr - mean) / std
    z = np.clip(z, -3, 3)
    return z.tolist()


def score_factors(
    factor_values: Dict[str, Dict[str, float]],
    weights: Dict[str, float],
    directions: Dict[str, str],
) -> Dict[str, float]:
    tickers = list(factor_values.keys())
    factor_names = list(weights.keys())

    normalized: Dict[str, Dict[str, float]] = {t: {} for t in tickers}
    for factor in factor_names:
        values = [factor_values[t].get(factor, float("nan")) for t in tickers]
        zscores = _zscore(values)
        if directions.get(factor, "high") == "low":
            zscores = [-z for z in zscores]
        for t, z in zip(tickers, zscores):
            normalized[t][factor] = float(z)

    scores: Dict[str, float] = {}
    for t in tickers:
        total_weight = 0.0
        weighted_sum = 0.0
        for factor, weight in weights.items():
            value = normalized[t].get(factor, 0.0)
            if not np.isnan(value):
                weighted_sum += value * weight
                total_weight += abs(weight)
        if total_weight == 0:
            scores[t] = 0.0
        else:
            raw = weighted_sum / total_weight
            score = (raw + 3) / 6 * 100
            scores[t] = float(np.clip(score, 0, 100))
    return scores


def rank_scores(scores: Dict[str, float]) -> List[Tuple[str, float]]:
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
