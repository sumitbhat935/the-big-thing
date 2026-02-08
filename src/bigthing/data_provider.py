"""Data provider for BigThing v2.

Fetches daily OHLCV, fundamentals, and earnings data from Yahoo Finance
with retry logic, batching, and data validation.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf

from .config import DataConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class StockDaily:
    """Daily OHLCV data for a single ticker."""
    ticker: str
    df: pd.DataFrame  # columns: open, high, low, close, volume (lowercase)


@dataclass
class FundamentalData:
    """Key fundamental metrics for a single ticker."""
    ticker: str
    sector: str = "Unknown"
    industry: str = "Unknown"
    market_cap: float = 0.0
    revenue_growth: Optional[float] = None
    earnings_growth: Optional[float] = None
    profit_margin: Optional[float] = None
    forward_pe: Optional[float] = None
    trailing_pe: Optional[float] = None
    next_earnings_date: Optional[str] = None


@dataclass
class MarketData:
    """All data needed by the 4 modules."""
    daily: Dict[str, StockDaily] = field(default_factory=dict)
    fundamentals: Dict[str, FundamentalData] = field(default_factory=dict)
    coverage_pct: float = 0.0


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------

class DataProvider:
    """Reliable daily data provider with retry and validation."""

    def __init__(self, config: DataConfig, batch_size: int = 50):
        self.config = config
        self.batch_size = batch_size

    # ------------------------------------------------------------------ #
    # Daily OHLCV
    # ------------------------------------------------------------------ #

    def fetch_daily(self, tickers: List[str], lookback_days: int = 300) -> Dict[str, StockDaily]:
        """Fetch daily OHLCV for a list of tickers with retry logic."""
        if not tickers:
            return {}

        period = f"{lookback_days}d"
        result: Dict[str, StockDaily] = {}

        for i in range(0, len(tickers), self.batch_size):
            batch = tickers[i : i + self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (len(tickers) + self.batch_size - 1) // self.batch_size

            for attempt in range(1, self.config.max_retries + 1):
                try:
                    logger.info(
                        "Daily batch %d/%d (%d tickers), attempt %d ...",
                        batch_num, total_batches, len(batch), attempt,
                    )
                    data = yf.download(
                        tickers=batch,
                        period=period,
                        interval="1d",
                        group_by="ticker",
                        auto_adjust=False,
                        progress=False,
                        threads=True,
                    )
                    if data.empty:
                        raise ValueError("Empty download result")

                    self._parse_daily(data, batch, result)
                    break  # success

                except Exception as exc:
                    logger.warning(
                        "Batch %d attempt %d failed: %s", batch_num, attempt, exc
                    )
                    if attempt < self.config.max_retries:
                        time.sleep(self.config.retry_delay_seconds)
                    continue

        logger.info(
            "Daily download: %d / %d tickers succeeded", len(result), len(tickers)
        )
        return result

    # ------------------------------------------------------------------ #
    # Fundamentals (individual ticker lookups)
    # ------------------------------------------------------------------ #

    def fetch_fundamentals(self, tickers: List[str]) -> Dict[str, FundamentalData]:
        """Fetch fundamental data for each ticker."""
        result: Dict[str, FundamentalData] = {}

        for ticker in tickers:
            for attempt in range(1, self.config.max_retries + 1):
                try:
                    t = yf.Ticker(ticker)
                    info = t.info or {}

                    # Parse next earnings date
                    next_earnings = None
                    try:
                        cal = t.calendar
                        if cal is not None:
                            if isinstance(cal, dict) and "Earnings Date" in cal:
                                dates = cal["Earnings Date"]
                                if dates:
                                    next_earnings = str(dates[0])
                            elif isinstance(cal, pd.DataFrame) and "Earnings Date" in cal.index:
                                next_earnings = str(cal.loc["Earnings Date"].iloc[0])
                    except Exception:
                        pass

                    result[ticker] = FundamentalData(
                        ticker=ticker,
                        sector=str(info.get("sector", "Unknown")),
                        industry=str(info.get("industry", "Unknown")),
                        market_cap=float(info.get("marketCap", 0) or 0),
                        revenue_growth=_safe_float(info.get("revenueGrowth")),
                        earnings_growth=_safe_float(info.get("earningsGrowth")),
                        profit_margin=_safe_float(info.get("profitMargins")),
                        forward_pe=_safe_float(info.get("forwardPE")),
                        trailing_pe=_safe_float(info.get("trailingPE")),
                        next_earnings_date=next_earnings,
                    )
                    break  # success

                except Exception as exc:
                    logger.debug("Fundamentals %s attempt %d: %s", ticker, attempt, exc)
                    if attempt < self.config.max_retries:
                        time.sleep(self.config.retry_delay_seconds)
                    else:
                        result[ticker] = FundamentalData(ticker=ticker)

        logger.info(
            "Fundamentals: %d / %d tickers succeeded", len(result), len(tickers)
        )
        return result

    # ------------------------------------------------------------------ #
    # Full fetch with validation
    # ------------------------------------------------------------------ #

    def fetch_all(
        self,
        tickers: List[str],
        lookback_days: int = 300,
        fetch_fundamentals: bool = True,
    ) -> MarketData:
        """Fetch daily + fundamentals with data coverage validation.

        Raises ValueError if coverage is below the configured threshold.
        """
        daily = self.fetch_daily(tickers, lookback_days)

        fundamentals: Dict[str, FundamentalData] = {}
        if fetch_fundamentals:
            fundamentals = self.fetch_fundamentals(list(daily.keys()))

        coverage = (len(daily) / len(tickers) * 100) if tickers else 0
        logger.info("Data coverage: %.1f%% (%d/%d)", coverage, len(daily), len(tickers))

        if coverage < self.config.min_data_coverage_pct:
            raise ValueError(
                f"Data coverage {coverage:.1f}% is below the {self.config.min_data_coverage_pct}% "
                f"threshold. Aborting to prevent unreliable output."
            )

        return MarketData(
            daily=daily,
            fundamentals=fundamentals,
            coverage_pct=coverage,
        )

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_daily(
        data: pd.DataFrame,
        tickers: List[str],
        out: Dict[str, StockDaily],
    ) -> None:
        """Parse yfinance download into individual StockDaily objects."""
        if isinstance(data.columns, pd.MultiIndex):
            for ticker in tickers:
                try:
                    if ticker not in data.columns.get_level_values(0):
                        continue
                    df = data[ticker].copy()
                    df.columns = [c.lower() for c in df.columns]
                    df = df.dropna(how="all")
                    if not df.empty and len(df) >= 20:
                        out[ticker] = StockDaily(ticker=ticker, df=df)
                except Exception:
                    continue
        else:
            # Single ticker
            df = data.copy()
            df.columns = [c.lower() for c in df.columns]
            df = df.dropna(how="all")
            if not df.empty and len(df) >= 20:
                out[tickers[0]] = StockDaily(ticker=tickers[0], df=df)


def _safe_float(val: Any) -> Optional[float]:
    """Convert to float or return None."""
    if val is None:
        return None
    try:
        f = float(val)
        return f if not np.isnan(f) else None
    except (ValueError, TypeError):
        return None
