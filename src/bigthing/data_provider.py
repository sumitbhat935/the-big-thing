from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd
import yfinance as yf


@dataclass
class MarketData:
    intraday: Dict[str, pd.DataFrame]


class YahooProvider:
    def get_intraday(self, tickers: List[str], period: str, interval: str) -> MarketData:
        if not tickers:
            return MarketData(intraday={})

        data = yf.download(
            tickers=tickers,
            period=period,
            interval=interval,
            group_by="ticker",
            auto_adjust=False,
            progress=False,
            threads=True,
        )

        intraday: Dict[str, pd.DataFrame] = {}
        if isinstance(data.columns, pd.MultiIndex):
            for ticker in tickers:
                if ticker in data.columns.get_level_values(0):
                    df = data[ticker].copy()
                    df.columns = [c.lower() for c in df.columns]
                    intraday[ticker] = df.dropna(how="all")
        else:
            df = data.copy()
            df.columns = [c.lower() for c in df.columns]
            intraday[tickers[0]] = df.dropna(how="all")

        return MarketData(intraday=intraday)

    def get_latest_prices(self, tickers: List[str]) -> Dict[str, float]:
        if not tickers:
            return {}
        data = yf.download(
            tickers=tickers,
            period="1d",
            interval="1m",
            group_by="ticker",
            auto_adjust=False,
            progress=False,
            threads=True,
        )
        prices: Dict[str, float] = {}
        if isinstance(data.columns, pd.MultiIndex):
            for ticker in tickers:
                if ticker in data.columns.get_level_values(0):
                    series = data[ticker]["Close"].dropna()
                    if not series.empty:
                        prices[ticker] = float(series.iloc[-1])
        else:
            series = data["Close"].dropna()
            if not series.empty:
                prices[tickers[0]] = float(series.iloc[-1])
        return prices
