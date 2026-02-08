"""Module 3: Opportunity Scanner.

Screens the S&P 500 + NASDAQ-100 universe for swing/position trade candidates
using daily-timeframe filters and a composite scoring model.

Outputs top 5-10 candidates with entry zones, stops, and scenario analysis.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .config import AppConfig, ScannerConfig
from .data_provider import MarketData, StockDaily, FundamentalData
from .regime import RegimeResult
from .utils import (
    is_above_ma,
    ma_trending_up,
    rsi_latest,
    relative_strength,
    atr,
    slope,
    sma,
    pct_from_ma,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    """A single opportunity candidate."""
    ticker: str
    sector: str
    current_price: float
    composite_score: float  # 0-100

    # Sub-scores (0-100 each, before weighting)
    trend_strength: float
    fundamental_growth: float
    rel_strength: float
    volume_expansion: float
    valuation_vs_growth: float

    # Trade plan
    entry_zone_low: float
    entry_zone_high: float
    suggested_stop: float
    risk_per_share: float
    position_size_shares: int
    capital_required: float

    # Scenario analysis (6-week)
    bull_scenario: str
    base_scenario: str
    bear_scenario: str
    six_month_outlook: str

    # Metadata
    rsi: float
    pct_from_50ma: float
    pct_from_200ma: float
    avg_volume_ratio: float
    earnings_growth: Optional[float]
    revenue_growth: Optional[float]
    next_earnings: Optional[str]


@dataclass
class ScannerResult:
    """Output of the Opportunity Scanner."""
    candidates: List[Candidate]
    universe_scanned: int
    passed_filter: int
    regime: str
    regime_multiplier: float


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

def scan_opportunities(
    config: AppConfig,
    market_data: MarketData,
    regime: RegimeResult,
) -> ScannerResult:
    """Screen and rank opportunity candidates."""
    cfg = config.scanner
    passed: List[dict] = []

    spy_daily = market_data.daily.get(config.regime.spy_ticker)
    spy_close = spy_daily.df["close"] if spy_daily else pd.Series(dtype=float)

    for ticker, stock in market_data.daily.items():
        # Skip holdings already in portfolio
        held_tickers = {h.ticker for h in config.portfolio.holdings}
        if ticker in held_tickers:
            continue

        close = stock.df["close"]
        if len(close) < 200:
            continue

        fund = market_data.fundamentals.get(ticker)

        # ---- FILTERS ----

        # 1. Price above 200 MA
        if not is_above_ma(close, 200):
            continue

        # 2. 50 MA rising
        if not ma_trending_up(close, 50, lookback=20):
            continue

        # 3. RSI between min and max
        current_rsi = rsi_latest(close, cfg.rsi_period)
        if np.isnan(current_rsi) or not (cfg.rsi_min <= current_rsi <= cfg.rsi_max):
            continue

        # 4. Volume expansion
        vol = stock.df["volume"]
        if len(vol) < cfg.volume_lookback:
            continue
        recent_vol = float(vol.iloc[-5:].mean())
        avg_vol = float(vol.iloc[-cfg.volume_lookback:].mean())
        vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 0
        if vol_ratio < cfg.volume_expansion_threshold:
            continue

        # 5. Positive earnings growth
        if fund and fund.earnings_growth is not None:
            if fund.earnings_growth <= 0:
                continue
        # If no fundamental data, still allow (benefit of doubt)

        # 6. No earnings within blackout window
        if fund and fund.next_earnings_date:
            try:
                earnings_dt = pd.Timestamp(fund.next_earnings_date)
                today = pd.Timestamp(datetime.now().date())
                days_to_earnings = (earnings_dt - today).days
                if 0 <= days_to_earnings <= cfg.earnings_blackout_days:
                    continue
            except Exception:
                pass

        # ---- PASSED ALL FILTERS ----
        passed.append({
            "ticker": ticker,
            "stock": stock,
            "fund": fund,
            "rsi": current_rsi,
            "vol_ratio": vol_ratio,
        })

    logger.info(
        "Scanner: %d / %d passed filters", len(passed), len(market_data.daily)
    )

    # ---- SCORE & RANK ----
    scored: List[Candidate] = []
    for item in passed:
        candidate = _score_candidate(
            item, config, market_data, regime, spy_close,
        )
        if candidate:
            scored.append(candidate)

    scored.sort(key=lambda c: c.composite_score, reverse=True)
    top = scored[: cfg.top_n]

    return ScannerResult(
        candidates=top,
        universe_scanned=len(market_data.daily),
        passed_filter=len(passed),
        regime=regime.classification,
        regime_multiplier=regime.multiplier,
    )


# ---------------------------------------------------------------------------
# Scoring helper
# ---------------------------------------------------------------------------

def _score_candidate(
    item: dict,
    config: AppConfig,
    market_data: MarketData,
    regime: RegimeResult,
    spy_close: pd.Series,
) -> Optional[Candidate]:
    """Compute composite score and trade plan for a candidate."""
    cfg = config.scanner
    ticker = item["ticker"]
    stock: StockDaily = item["stock"]
    fund: Optional[FundamentalData] = item["fund"]
    current_rsi = item["rsi"]
    vol_ratio = item["vol_ratio"]

    close = stock.df["close"]
    current_price = float(close.iloc[-1])

    # ---- Sub-scores (each 0-100) ----

    # Trend Strength (slope + MA alignment)
    s = slope(close, window=50) * 10000  # amplify small slopes
    trend_raw = min(max(s, 0), 100)

    # Fundamental Growth
    fund_raw = 50.0  # default
    if fund:
        eg = fund.earnings_growth if fund.earnings_growth is not None else 0
        rg = fund.revenue_growth if fund.revenue_growth is not None else 0
        fund_raw = min((eg * 100 + rg * 100) / 2 + 50, 100)
        fund_raw = max(fund_raw, 0)

    # Relative Strength
    rs = 50.0
    if not spy_close.empty and len(close) >= 60:
        rs_val = relative_strength(close, spy_close, days=60)
        rs = min(max(rs_val + 50, 0), 100)

    # Volume Expansion
    vol_raw = min((vol_ratio - 1.0) * 200 + 50, 100)
    vol_raw = max(vol_raw, 0)

    # Valuation vs Growth (simple PE/Growth ratio)
    val_raw = 50.0
    if fund and fund.forward_pe and fund.earnings_growth:
        peg = fund.forward_pe / (fund.earnings_growth * 100) if fund.earnings_growth > 0 else 99
        if peg < 1:
            val_raw = 80
        elif peg < 2:
            val_raw = 60
        elif peg < 3:
            val_raw = 40
        else:
            val_raw = 20

    # ---- Composite ----
    composite = (
        trend_raw * cfg.weight_trend
        + fund_raw * cfg.weight_fundamental
        + rs * cfg.weight_relative_strength
        + vol_raw * cfg.weight_volume
        + val_raw * cfg.weight_valuation
    )

    # ---- Trade Plan ----
    current_atr = atr(stock.df)
    suggested_stop = current_price - (2 * current_atr) if current_atr > 0 else current_price * 0.92
    risk_per_share = current_price - suggested_stop

    # Entry zone: current price down to 50 MA
    ma50 = sma(close, 50)
    ma50_val = float(ma50.iloc[-1]) if not ma50.dropna().empty else current_price * 0.97
    entry_low = round(min(ma50_val, current_price * 0.98), 2)
    entry_high = round(current_price, 2)

    # Position size = (1% of portfolio * regime multiplier) / risk per share
    max_risk = config.portfolio.total_value * (config.portfolio.max_risk_per_trade_pct / 100) * regime.multiplier
    pos_size = int(max_risk / risk_per_share) if risk_per_share > 0 else 0
    capital_req = pos_size * current_price

    # ---- Scenario Analysis ----
    bull, base, bear = _scenario_analysis(current_price, current_atr, fund)
    outlook = _six_month_outlook(ticker, trend_raw, fund_raw, rs, regime.classification)

    sector = fund.sector if fund else "Unknown"

    return Candidate(
        ticker=ticker,
        sector=sector,
        current_price=round(current_price, 2),
        composite_score=round(composite, 2),
        trend_strength=round(trend_raw, 1),
        fundamental_growth=round(fund_raw, 1),
        rel_strength=round(rs, 1),
        volume_expansion=round(vol_raw, 1),
        valuation_vs_growth=round(val_raw, 1),
        entry_zone_low=entry_low,
        entry_zone_high=entry_high,
        suggested_stop=round(suggested_stop, 2),
        risk_per_share=round(risk_per_share, 2),
        position_size_shares=pos_size,
        capital_required=round(capital_req, 2),
        bull_scenario=bull,
        base_scenario=base,
        bear_scenario=bear,
        six_month_outlook=outlook,
        rsi=round(current_rsi, 1),
        pct_from_50ma=round(pct_from_ma(close, 50), 2),
        pct_from_200ma=round(pct_from_ma(close, 200), 2),
        avg_volume_ratio=round(vol_ratio, 2),
        earnings_growth=fund.earnings_growth if fund else None,
        revenue_growth=fund.revenue_growth if fund else None,
        next_earnings=fund.next_earnings_date if fund else None,
    )


def _scenario_analysis(price: float, atr_val: float, fund: Optional[FundamentalData]):
    """6-week bull/base/bear scenario."""
    # ATR-based range estimation (6 weeks ~ 30 trading days)
    move_30d = atr_val * np.sqrt(30) if atr_val > 0 else price * 0.08

    bull_target = price + move_30d * 1.5
    base_target = price + move_30d * 0.3
    bear_target = price - move_30d

    bull = (
        f"Bull (30% probability): Price reaches ${bull_target:.2f} (+{((bull_target/price)-1)*100:.1f}%) "
        f"on continued momentum and favorable earnings."
    )
    base = (
        f"Base (50% probability): Price consolidates around ${base_target:.2f} "
        f"({((base_target/price)-1)*100:+.1f}%) with normal volatility."
    )
    bear = (
        f"Bear (20% probability): Price pulls back to ${bear_target:.2f} "
        f"({((bear_target/price)-1)*100:+.1f}%) on broader market weakness or negative catalysts."
    )
    return bull, base, bear


def _six_month_outlook(
    ticker: str, trend: float, fund: float, rs: float, regime: str
) -> str:
    """Generate a 6-month outlook summary."""
    avg = (trend + fund + rs) / 3
    if avg >= 65 and regime in ("RISK_ON", "NEUTRAL"):
        return (
            f"{ticker} has above-average trend strength, solid fundamentals, and "
            f"favorable relative strength. In the current {regime} environment, "
            f"the probability of meaningful appreciation over 6 months is elevated, "
            f"though market-wide corrections remain a risk."
        )
    elif avg >= 40:
        return (
            f"{ticker} shows moderate potential with mixed signals across trend, "
            f"fundamentals, and relative strength. Position sizing should reflect "
            f"this uncertainty. Monitor for improvement in weaker sub-scores."
        )
    else:
        return (
            f"{ticker} scores below average. While it passed technical filters, "
            f"fundamental or relative strength concerns limit conviction. "
            f"Consider smaller position or wait for a higher-confidence setup."
        )
