"""Module 2: Portfolio Health Engine.

Scores each holding on Trend (0-3), Fundamentals (0-3), Relative Strength (0-2),
and Macro Alignment (0-2) for a total of 0-10.

Produces actionable decisions: STRONG HOLD, HOLD, TRIM 25%, or EXIT.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .config import AppConfig, Holding
from .data_provider import DataProvider, StockDaily, FundamentalData, MarketData
from .regime import RegimeResult
from .utils import (
    is_above_ma,
    higher_highs,
    pct_from_ma,
    relative_strength,
    atr,
    sma,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sector strength lookup (simplified)
# ---------------------------------------------------------------------------

# Sectors that tend to outperform in each regime
_RISK_ON_SECTORS = {"Technology", "Consumer Cyclical", "Communication Services", "Financial Services"}
_RISK_OFF_SECTORS = {"Utilities", "Consumer Defensive", "Healthcare", "Real Estate"}


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

@dataclass
class HoldingHealth:
    """Health assessment for a single holding."""
    ticker: str
    shares: float
    avg_cost: float
    current_price: float
    unrealized_pnl_pct: float

    # Sub-scores
    trend_score: int              # 0-3
    fundamental_score: int        # 0-3
    relative_strength_score: int  # 0-2
    macro_alignment_score: int    # 0-2
    total_score: int              # 0-10

    # Decision
    decision: str                 # STRONG HOLD | HOLD | TRIM 25% | EXIT
    explanation: str

    # Risk metrics
    pct_from_50ma: float
    pct_from_200ma: float
    suggested_stop: float
    risk_per_share: float
    position_value: float
    risk_as_pct_of_portfolio: float

    # Detail breakdown
    trend_details: Dict[str, str] = field(default_factory=dict)
    fundamental_details: Dict[str, str] = field(default_factory=dict)
    rs_details: Dict[str, str] = field(default_factory=dict)
    macro_details: Dict[str, str] = field(default_factory=dict)


@dataclass
class PortfolioHealthResult:
    """Output of the Portfolio Health Engine."""
    holdings: List[HoldingHealth]
    total_invested: float
    total_current_value: float
    total_pnl_pct: float
    actions_required: List[str]


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

def analyze_portfolio_health(
    config: AppConfig,
    market_data: MarketData,
    regime: RegimeResult,
) -> PortfolioHealthResult:
    """Score every holding and produce decisions."""
    holdings_out: List[HoldingHealth] = []
    actions: List[str] = []
    total_invested = 0.0
    total_current = 0.0

    # Get SPY data for relative strength
    spy_daily = market_data.daily.get(config.regime.spy_ticker)
    spy_close = spy_daily.df["close"] if spy_daily else pd.Series(dtype=float)

    for h in config.portfolio.holdings:
        stock = market_data.daily.get(h.ticker)
        fund = market_data.fundamentals.get(h.ticker)

        if not stock or stock.df.empty:
            logger.warning("No data for holding %s, marking for EXIT", h.ticker)
            hh = _empty_holding(h, config.portfolio.total_value)
            hh.decision = "EXIT"
            hh.explanation = f"No market data available for {h.ticker}. Cannot assess — recommend exiting."
            holdings_out.append(hh)
            actions.append(f"EXIT {h.ticker}: No data available")
            continue

        close = stock.df["close"]
        current_price = float(close.iloc[-1])
        position_value = h.shares * current_price
        invested = h.shares * h.avg_cost
        pnl_pct = (current_price - h.avg_cost) / h.avg_cost * 100 if h.avg_cost > 0 else 0

        total_invested += invested
        total_current += position_value

        # ---- Trend Score (0-3) ----
        trend_score = 0
        trend_details: Dict[str, str] = {}

        above_200 = is_above_ma(close, 200)
        trend_details["above_200ma"] = "YES" if above_200 else "NO"
        if above_200:
            trend_score += 1

        above_50 = is_above_ma(close, 50)
        trend_details["above_50ma"] = "YES" if above_50 else "NO"
        if above_50:
            trend_score += 1

        hh_pattern = higher_highs(close, window=30)
        trend_details["higher_highs"] = "YES" if hh_pattern else "NO"
        if hh_pattern:
            trend_score += 1

        # ---- Fundamental Score (0-3) ----
        fundamental_score = 0
        fund_details: Dict[str, str] = {}

        if fund:
            if fund.revenue_growth is not None and fund.revenue_growth > 0:
                fundamental_score += 1
                fund_details["revenue_growth"] = f"{fund.revenue_growth:+.1%}"
            else:
                fund_details["revenue_growth"] = f"{fund.revenue_growth:+.1%}" if fund.revenue_growth is not None else "N/A"

            if fund.earnings_growth is not None and fund.earnings_growth > 0:
                fundamental_score += 1
                fund_details["earnings_growth"] = f"{fund.earnings_growth:+.1%}"
            else:
                fund_details["earnings_growth"] = f"{fund.earnings_growth:+.1%}" if fund.earnings_growth is not None else "N/A"

            if fund.profit_margin is not None and fund.profit_margin > 0.05:
                fundamental_score += 1
                fund_details["profit_margin"] = f"{fund.profit_margin:.1%}"
            else:
                fund_details["profit_margin"] = f"{fund.profit_margin:.1%}" if fund.profit_margin is not None else "N/A"
        else:
            fund_details["data"] = "UNAVAILABLE"

        # ---- Relative Strength Score (0-2) ----
        rs_score = 0
        rs_details: Dict[str, str] = {}

        if not spy_close.empty and len(close) >= 60:
            rs = relative_strength(close, spy_close, days=60)
            rs_details["vs_spy_60d"] = f"{rs:+.1f}%"
            if rs > 5:
                rs_score += 2
            elif rs > 0:
                rs_score += 1
        else:
            rs_details["vs_spy_60d"] = "N/A"

        # ---- Macro Alignment Score (0-2) ----
        macro_score = 0
        macro_details: Dict[str, str] = {}

        sector = fund.sector if fund else "Unknown"
        macro_details["sector"] = sector

        if regime.classification == "RISK_ON" and sector in _RISK_ON_SECTORS:
            macro_score += 1
            macro_details["sector_alignment"] = "FAVORABLE"
        elif regime.classification == "RISK_OFF" and sector in _RISK_OFF_SECTORS:
            macro_score += 1
            macro_details["sector_alignment"] = "FAVORABLE"
        elif regime.classification == "NEUTRAL":
            macro_score += 1  # neutral is fine for any sector
            macro_details["sector_alignment"] = "NEUTRAL"
        else:
            macro_details["sector_alignment"] = "UNFAVORABLE"

        # Regime alignment
        if regime.classification == "RISK_ON":
            macro_score += 1
            macro_details["regime_alignment"] = "STRONG"
        elif regime.classification == "NEUTRAL":
            macro_details["regime_alignment"] = "MODERATE"
        else:
            macro_details["regime_alignment"] = "WEAK"

        # ---- Total Score & Decision ----
        total = trend_score + fundamental_score + rs_score + macro_score

        if total >= 8:
            decision = "STRONG HOLD"
        elif total >= 6:
            decision = "HOLD"
        elif total >= 4:
            decision = "TRIM 25%"
        else:
            decision = "EXIT"

        # ---- Risk Metrics ----
        pct_50 = pct_from_ma(close, 50)
        pct_200 = pct_from_ma(close, 200)
        current_atr = atr(stock.df)
        suggested_stop = current_price - (2 * current_atr) if current_atr > 0 else current_price * 0.92
        risk_per_share = current_price - suggested_stop
        portfolio_risk = (h.shares * risk_per_share) / config.portfolio.total_value * 100

        # ---- Explanation ----
        explanation = _build_holding_explanation(
            h.ticker, decision, total, trend_score, fundamental_score,
            rs_score, macro_score, current_price, pnl_pct, sector,
        )

        if decision in ("TRIM 25%", "EXIT"):
            actions.append(f"{decision} {h.ticker}: score {total}/10, P&L {pnl_pct:+.1f}%")

        holdings_out.append(HoldingHealth(
            ticker=h.ticker,
            shares=h.shares,
            avg_cost=h.avg_cost,
            current_price=current_price,
            unrealized_pnl_pct=round(pnl_pct, 2),
            trend_score=trend_score,
            fundamental_score=fundamental_score,
            relative_strength_score=rs_score,
            macro_alignment_score=macro_score,
            total_score=total,
            decision=decision,
            explanation=explanation,
            pct_from_50ma=round(pct_50, 2),
            pct_from_200ma=round(pct_200, 2),
            suggested_stop=round(suggested_stop, 2),
            risk_per_share=round(risk_per_share, 2),
            position_value=round(position_value, 2),
            risk_as_pct_of_portfolio=round(portfolio_risk, 2),
            trend_details=trend_details,
            fundamental_details=fund_details,
            rs_details=rs_details,
            macro_details=macro_details,
        ))

    total_pnl = 0.0
    if total_invested > 0:
        total_pnl = (total_current - total_invested) / total_invested * 100

    return PortfolioHealthResult(
        holdings=holdings_out,
        total_invested=round(total_invested, 2),
        total_current_value=round(total_current, 2),
        total_pnl_pct=round(total_pnl, 2),
        actions_required=actions,
    )


def _empty_holding(h: Holding, portfolio_value: float) -> HoldingHealth:
    """Create a zero-scored holding when data is unavailable."""
    return HoldingHealth(
        ticker=h.ticker, shares=h.shares, avg_cost=h.avg_cost,
        current_price=0, unrealized_pnl_pct=0,
        trend_score=0, fundamental_score=0, relative_strength_score=0,
        macro_alignment_score=0, total_score=0,
        decision="EXIT", explanation="",
        pct_from_50ma=0, pct_from_200ma=0, suggested_stop=0,
        risk_per_share=0, position_value=0, risk_as_pct_of_portfolio=0,
    )


def _build_holding_explanation(
    ticker: str, decision: str, total: int,
    trend: int, fund: int, rs: int, macro: int,
    price: float, pnl: float, sector: str,
) -> str:
    """Plain-English explanation of the holding decision."""
    strength = []
    weakness = []

    if trend >= 2:
        strength.append("strong uptrend")
    elif trend == 0:
        weakness.append("weak trend structure")

    if fund >= 2:
        strength.append("solid fundamentals")
    elif fund == 0:
        weakness.append("deteriorating fundamentals")

    if rs >= 1:
        strength.append("outperforming the market")
    else:
        weakness.append("underperforming vs S&P 500")

    if macro >= 1:
        strength.append(f"{sector} sector aligned with current regime")

    parts = []
    if strength:
        parts.append(f"Strengths: {', '.join(strength)}.")
    if weakness:
        parts.append(f"Concerns: {', '.join(weakness)}.")

    return (
        f"{ticker} at ${price:.2f} (P&L: {pnl:+.1f}%) scores {total}/10. "
        f"{decision}. {' '.join(parts)}"
    )
