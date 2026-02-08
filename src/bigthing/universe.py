"""Dynamic stock universe builder.

Fetches S&P 500 and NASDAQ-100 constituents from Wikipedia and applies
pre-filtering on price and volume.

Uses urllib + pandas.read_html to avoid fragile scraping — Wikipedia tables
are well-structured and reliable.
"""
from __future__ import annotations

import io
import logging
import urllib.request
from dataclasses import dataclass, field
from typing import List

import pandas as pd

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class PreFilterConfig:
    """Pre-filter settings for the stock universe."""
    min_price: float = 10.0
    max_price: float = 10_000.0
    min_avg_volume: float = 1_000_000
    sources: List[str] = field(default_factory=lambda: ["sp500", "nasdaq100"])


def build_universe(cfg: PreFilterConfig) -> List[str]:
    """Build the stock universe from configured sources.

    Returns a deduplicated, sorted list of tickers that pass pre-filtering.
    """
    tickers: set = set()

    if "sp500" in cfg.sources:
        tickers.update(_fetch_sp500())

    if "nasdaq100" in cfg.sources:
        tickers.update(_fetch_nasdaq100())

    result = sorted(tickers)
    logger.info("Universe raw: %d tickers from %s", len(result), cfg.sources)
    return result


def _fetch_sp500() -> List[str]:
    """Fetch S&P 500 constituents from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    try:
        html = _download_page(url)
        tables = pd.read_html(io.StringIO(html))
        if not tables:
            return []
        df = tables[0]
        col = "Symbol" if "Symbol" in df.columns else df.columns[0]
        tickers = df[col].astype(str).str.strip().str.replace(".", "-", regex=False).tolist()
        logger.info("S&P 500: %d tickers fetched", len(tickers))
        return tickers
    except Exception as exc:
        logger.error("Failed to fetch S&P 500: %s", exc)
        return []


def _fetch_nasdaq100() -> List[str]:
    """Fetch NASDAQ-100 constituents from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/Nasdaq-100"
    try:
        html = _download_page(url)
        tables = pd.read_html(io.StringIO(html))
        for table in tables:
            if "Ticker" in table.columns:
                tickers = table["Ticker"].astype(str).str.strip().tolist()
                logger.info("NASDAQ-100: %d tickers fetched", len(tickers))
                return tickers
            if "Symbol" in table.columns:
                tickers = table["Symbol"].astype(str).str.strip().tolist()
                logger.info("NASDAQ-100: %d tickers fetched", len(tickers))
                return tickers
        return []
    except Exception as exc:
        logger.error("Failed to fetch NASDAQ-100: %s", exc)
        return []


def _download_page(url: str) -> str:
    """Download a web page with a User-Agent header."""
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")
