"""Module 1: Market Regime Engine.

Classifies the current market environment as RISK_ON, NEUTRAL, or RISK_OFF
using SPY trend structure, VIX levels, and Treasury yield direction.

Output drives position-size multipliers for the entire system.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List

import pandas as pd

from .config import RegimeConfig
from .data_provider import DataProvider, DataConfig
from .utils import (
    is_above_ma,
    ma_trending_up,
    higher_highs,
    lower_highs,
    slope,
    pct_from_ma,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RISK_ON = "RISK_ON"
NEUTRAL = "NEUTRAL"
RISK_OFF = "RISK_OFF"

MULTIPLIERS = {
    RISK_ON: 1.0,
    NEUTRAL: 0.7,
    RISK_OFF: 0.4,
}


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

@dataclass
class RegimeResult:
    """Output of the Market Regime Engine."""
    classification: str            # RISK_ON | NEUTRAL | RISK_OFF
    multiplier: float              # 1.0 / 0.7 / 0.4
    explanation: str               # Plain English summary
    signals: Dict[str, str] = field(default_factory=dict)
    spy_price: float = 0.0
    spy_200ma: float = 0.0
    spy_50ma: float = 0.0
    vix_level: float = 0.0
    treasury_yield: float = 0.0


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

def analyze_regime(cfg: RegimeConfig, data_config: DataConfig) -> RegimeResult:
    """Run the Market Regime Engine.

    Fetches SPY, VIX, 10Y Treasury daily data and classifies the market.
    """
    provider = DataProvider(config=data_config)
    macro_tickers = [cfg.spy_ticker, cfg.vix_ticker, cfg.treasury_ticker]

    daily = provider.fetch_daily(macro_tickers, lookback_days=cfg.lookback_days)

    # ---- SPY signals ----
    spy_data = daily.get(cfg.spy_ticker)
    signals: Dict[str, str] = {}
    bullish_count = 0
    bearish_count = 0

    spy_price = 0.0
    spy_200 = 0.0
    spy_50 = 0.0

    if spy_data and not spy_data.df.empty:
        close = spy_data.df["close"]
        spy_price = float(close.iloc[-1])

        # SPY vs 200 MA
        above_200 = is_above_ma(close, cfg.ma_long)
        signals["spy_vs_200ma"] = "ABOVE" if above_200 else "BELOW"
        if above_200:
            bullish_count += 1
        else:
            bearish_count += 1

        # SPY vs 50 MA
        above_50 = is_above_ma(close, cfg.ma_short)
        signals["spy_vs_50ma"] = "ABOVE" if above_50 else "BELOW"

        # 50 MA trending up
        ma50_up = ma_trending_up(close, cfg.ma_short, lookback=cfg.trend_window)
        signals["50ma_trend"] = "RISING" if ma50_up else "FALLING"
        if ma50_up:
            bullish_count += 1
        else:
            bearish_count += 1

        # Higher highs / lower highs
        hh = higher_highs(close, window=cfg.trend_window)
        lh = lower_highs(close, window=cfg.trend_window)
        if hh:
            signals["price_structure"] = "HIGHER_HIGHS"
            bullish_count += 1
        elif lh:
            signals["price_structure"] = "LOWER_HIGHS"
            bearish_count += 1
        else:
            signals["price_structure"] = "MIXED"

        # 20-day trend direction
        trend_slope = slope(close, window=cfg.trend_window)
        signals["20d_trend"] = f"{'UP' if trend_slope > 0 else 'DOWN'} ({trend_slope:+.4f})"
        if trend_slope > 0:
            bullish_count += 1
        else:
            bearish_count += 1

        # MA values
        from .utils import sma
        ma200 = sma(close, cfg.ma_long)
        ma50 = sma(close, cfg.ma_short)
        spy_200 = float(ma200.iloc[-1]) if not ma200.dropna().empty else 0
        spy_50 = float(ma50.iloc[-1]) if not ma50.dropna().empty else 0
    else:
        signals["spy_data"] = "MISSING"
        bearish_count += 2

    # ---- VIX signals ----
    vix_level = 0.0
    vix_data = daily.get(cfg.vix_ticker)
    if vix_data and not vix_data.df.empty:
        vix_close = vix_data.df["close"]
        vix_level = float(vix_close.iloc[-1])
        vix_elevated = vix_level > cfg.vix_elevated_threshold
        vix_trend = slope(vix_close, window=cfg.trend_window)
        signals["vix_level"] = f"{vix_level:.1f} ({'ELEVATED' if vix_elevated else 'NORMAL'})"
        signals["vix_trend"] = f"{'RISING' if vix_trend > 0 else 'FALLING'} ({vix_trend:+.4f})"
        if vix_elevated:
            bearish_count += 1
        else:
            bullish_count += 1
    else:
        signals["vix_data"] = "MISSING"

    # ---- Treasury signals ----
    treasury_yield = 0.0
    treasury_data = daily.get(cfg.treasury_ticker)
    if treasury_data and not treasury_data.df.empty:
        t_close = treasury_data.df["close"]
        treasury_yield = float(t_close.iloc[-1])
        t_trend = slope(t_close, window=30)
        signals["10y_yield"] = f"{treasury_yield:.2f}%"
        signals["10y_trend"] = f"{'RISING' if t_trend > 0 else 'FALLING'} ({t_trend:+.4f})"
        if t_trend > 0.001:
            bearish_count += 1  # rising rates = headwind
    else:
        signals["treasury_data"] = "MISSING"

    # ---- Classification ----
    if bullish_count >= 4 and bearish_count <= 1:
        classification = RISK_ON
    elif bearish_count >= 4:
        classification = RISK_OFF
    else:
        classification = NEUTRAL

    multiplier = MULTIPLIERS[classification]

    # ---- Plain English explanation ----
    explanation = _build_explanation(classification, signals, spy_price, spy_200, vix_level)

    return RegimeResult(
        classification=classification,
        multiplier=multiplier,
        explanation=explanation,
        signals=signals,
        spy_price=spy_price,
        spy_200ma=spy_200,
        spy_50ma=spy_50,
        vix_level=vix_level,
        treasury_yield=treasury_yield,
    )


def _build_explanation(
    regime: str, signals: Dict[str, str], spy_price: float, spy_200: float, vix: float
) -> str:
    """Build a plain-English regime explanation."""
    if regime == RISK_ON:
        return (
            f"Market is in RISK-ON mode. SPY (${spy_price:.2f}) is trading above its "
            f"200-day moving average (${spy_200:.2f}), the 50-day MA is trending upward, "
            f"and price structure shows higher highs. VIX at {vix:.1f} indicates low fear. "
            f"Full position sizing is appropriate."
        )
    elif regime == RISK_OFF:
        return (
            f"Market is in RISK-OFF mode. SPY (${spy_price:.2f}) is showing weakness "
            f"relative to its 200-day moving average (${spy_200:.2f}), with deteriorating "
            f"price structure. VIX at {vix:.1f} suggests elevated uncertainty. "
            f"Reduce exposure to 40% of normal position sizes. Prioritize capital preservation."
        )
    else:
        return (
            f"Market is in NEUTRAL mode with mixed signals. SPY at ${spy_price:.2f} "
            f"vs 200-day MA at ${spy_200:.2f}. VIX at {vix:.1f}. "
            f"Use 70% of normal position sizing. Be selective with new entries."
        )
