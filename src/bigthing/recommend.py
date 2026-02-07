from __future__ import annotations

from typing import Dict, List

from .config import AppConfig
from .data_provider import YahooProvider
from .factors import compute_factors
from .scoring import score_factors, rank_scores


def build_recommendations(config: AppConfig) -> Dict[str, object]:
    provider = YahooProvider()
    data = provider.get_intraday(
        tickers=config.tickers,
        period=config.period,
        interval=config.interval,
    )

    factor_values: Dict[str, Dict[str, float]] = {}
    for ticker, df in data.intraday.items():
        factor_values[ticker] = compute_factors(
            df=df,
            morning_minutes=config.morning_minutes,
        )

    scores = score_factors(
        factor_values=factor_values,
        weights=config.weights,
        directions=config.factor_directions,
    )
    ranked = rank_scores(scores)

    top_n = max(1, min(config.top_n, len(ranked)))
    top = [
        {
            "ticker": t,
            "buy_score": round(s, 2),
            "factors": factor_values.get(t, {}),
        }
        for t, s in ranked[:top_n]
    ]

    return {
        "top_picks": top,
        "universe_size": len(ranked),
        "interval": config.interval,
        "morning_minutes": config.morning_minutes,
    }
