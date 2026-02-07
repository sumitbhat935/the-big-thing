from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd

from .utils import get_morning_window, split_by_date, slope


def compute_rsi(series: pd.Series, period: int = 14) -> float:
    if series.size < period + 1:
        return float("nan")
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1])


def compute_vwap(df: pd.DataFrame) -> float:
    if df.empty:
        return float("nan")
    price = df["close"]
    vol = df["volume"]
    if vol.sum() == 0:
        return float("nan")
    return float((price * vol).sum() / vol.sum())


def compute_factors(
    df: pd.DataFrame,
    morning_minutes: int,
    volume_lookback_days: int = 5,
) -> Dict[str, Optional[float]]:
    if df.empty:
        return {
            "gap_pct": None,
            "early_return": None,
            "volume_spike": None,
            "trend_slope": None,
            "rsi": None,
            "vwap_pct": None,
        }

    days = split_by_date(df)
    if len(days) < 2:
        return {
            "gap_pct": None,
            "early_return": None,
            "volume_spike": None,
            "trend_slope": None,
            "rsi": None,
            "vwap_pct": None,
        }

    sorted_days = sorted(days.keys())
    today = days[sorted_days[-1]]
    prev = days[sorted_days[-2]]

    today_morning = get_morning_window(today, morning_minutes)
    if today_morning.empty:
        return {
            "gap_pct": None,
            "early_return": None,
            "volume_spike": None,
            "trend_slope": None,
            "rsi": None,
            "vwap_pct": None,
        }

    today_open = float(today_morning["open"].iloc[0])
    today_last = float(today_morning["close"].iloc[-1])
    prev_close = float(prev["close"].dropna().iloc[-1])

    gap_pct = (today_open - prev_close) / prev_close if prev_close else None
    early_return = (today_last - today_open) / today_open if today_open else None

    morning_vol = float(today_morning["volume"].sum())
    past_days = sorted_days[-(volume_lookback_days + 1) : -1]
    past_morning_vols = []
    for d in past_days:
        past_morning = get_morning_window(days[d], morning_minutes)
        if not past_morning.empty:
            past_morning_vols.append(float(past_morning["volume"].sum()))
    volume_spike = None
    if past_morning_vols:
        avg_vol = float(np.mean(past_morning_vols))
        if avg_vol > 0:
            volume_spike = morning_vol / avg_vol

    trend_slope = slope(today_morning["close"])
    rsi = compute_rsi(today_morning["close"])
    vwap = compute_vwap(today_morning)
    vwap_pct = (today_last - vwap) / vwap if vwap and not np.isnan(vwap) else None

    return {
        "gap_pct": gap_pct,
        "early_return": early_return,
        "volume_spike": volume_spike,
        "trend_slope": trend_slope,
        "rsi": rsi,
        "vwap_pct": vwap_pct,
    }
