"""Technical analysis utilities for daily-timeframe data.

All helpers operate on pandas Series/DataFrames with daily OHLCV columns.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    """Simple moving average."""
    return series.rolling(window=period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential moving average."""
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder's smoothing)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta.clip(upper=0))
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def rsi_latest(series: pd.Series, period: int = 14) -> float:
    """Return the latest RSI value."""
    r = rsi(series, period).dropna()
    return float(r.iloc[-1]) if not r.empty else float("nan")


def slope(series: pd.Series, window: int = 20) -> float:
    """Linear regression slope over the last `window` bars.

    Returns slope normalized by the mean price (percentage per bar).
    """
    s = series.dropna().tail(window)
    if s.size < max(window // 2, 5):
        return 0.0
    x = np.arange(s.size, dtype=float)
    y = s.values.astype(float)
    m, _ = np.polyfit(x, y, 1)
    mean_price = float(np.mean(y))
    if mean_price == 0:
        return 0.0
    return float(m / mean_price)


def is_above_ma(series: pd.Series, period: int) -> bool:
    """Check if the latest close is above its SMA."""
    ma = sma(series, period)
    if ma.dropna().empty:
        return False
    return bool(series.iloc[-1] > ma.iloc[-1])


def ma_trending_up(series: pd.Series, period: int, lookback: int = 20) -> bool:
    """Check if the SMA itself has been trending upward over `lookback` bars."""
    ma = sma(series, period).dropna()
    if len(ma) < lookback:
        return False
    recent = ma.tail(lookback)
    return bool(recent.iloc[-1] > recent.iloc[0])


def higher_highs(series: pd.Series, window: int = 20, min_swings: int = 2) -> bool:
    """Detect a higher-highs pattern in recent data.

    Looks for at least `min_swings` local highs that are successively higher.
    """
    s = series.dropna().tail(window * 2)
    if s.size < window:
        return False

    # Find local peaks (higher than neighbors within a 5-bar window)
    peaks = []
    arr = s.values
    for i in range(2, len(arr) - 2):
        if arr[i] > arr[i - 1] and arr[i] > arr[i - 2] and arr[i] > arr[i + 1] and arr[i] > arr[i + 2]:
            peaks.append(float(arr[i]))

    if len(peaks) < min_swings:
        return False

    # Check that peaks are ascending
    for i in range(1, len(peaks)):
        if peaks[i] <= peaks[i - 1]:
            return False
    return True


def lower_highs(series: pd.Series, window: int = 20, min_swings: int = 2) -> bool:
    """Detect a lower-highs pattern (bearish structure)."""
    s = series.dropna().tail(window * 2)
    if s.size < window:
        return False

    peaks = []
    arr = s.values
    for i in range(2, len(arr) - 2):
        if arr[i] > arr[i - 1] and arr[i] > arr[i - 2] and arr[i] > arr[i + 1] and arr[i] > arr[i + 2]:
            peaks.append(float(arr[i]))

    if len(peaks) < min_swings:
        return False

    for i in range(1, len(peaks)):
        if peaks[i] >= peaks[i - 1]:
            return False
    return True


def pct_from_ma(series: pd.Series, period: int) -> float:
    """Current price as a percentage distance from its SMA."""
    ma = sma(series, period)
    if ma.dropna().empty:
        return 0.0
    latest = float(series.iloc[-1])
    ma_val = float(ma.iloc[-1])
    if ma_val == 0:
        return 0.0
    return (latest - ma_val) / ma_val * 100


def relative_strength(stock: pd.Series, benchmark: pd.Series, days: int = 60) -> float:
    """Relative performance of stock vs benchmark over `days`.

    Returns the difference in percentage returns.
    """
    if len(stock) < days or len(benchmark) < days:
        return 0.0
    stock_ret = (float(stock.iloc[-1]) - float(stock.iloc[-days])) / float(stock.iloc[-days])
    bench_ret = (float(benchmark.iloc[-1]) - float(benchmark.iloc[-days])) / float(benchmark.iloc[-days])
    return (stock_ret - bench_ret) * 100


def atr(df: pd.DataFrame, period: int = 14) -> float:
    """Average True Range (latest value)."""
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr_series = tr.rolling(window=period, min_periods=period).mean()
    return float(atr_series.iloc[-1]) if not atr_series.dropna().empty else 0.0
