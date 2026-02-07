from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd


def get_morning_window(df: pd.DataFrame, minutes: int) -> pd.DataFrame:
    if df.empty:
        return df
    start = df.index.min()
    end = start + pd.Timedelta(minutes=minutes)
    return df[(df.index >= start) & (df.index <= end)]


def split_by_date(df: pd.DataFrame) -> Dict[pd.Timestamp, pd.DataFrame]:
    if df.empty:
        return {}
    dates = df.index.normalize()
    grouped = {}
    for date in sorted(dates.unique()):
        grouped[date] = df[dates == date]
    return grouped


def slope(series: pd.Series) -> float:
    if series.size < 2:
        return 0.0
    x = np.arange(series.size, dtype=float)
    y = series.astype(float).values
    m, _ = np.polyfit(x, y, 1)
    return float(m)
