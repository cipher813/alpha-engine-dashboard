"""
Shared accuracy and statistical utilities.

Centralizes Wilson CI and drawdown calculations used by Signal Quality,
Backtester, and chart modules.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def wilson_ci(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Compute Wilson score confidence interval (pure arithmetic, no scipy).

    Returns (lower, upper) as proportions in [0, 1].
    """
    if total == 0:
        return 0.0, 0.0
    p_hat = successes / total
    denominator = 1 + z * z / total
    centre = (p_hat + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((p_hat * (1 - p_hat) + z * z / (4 * total)) / total) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def compute_drawdown(daily_ret: pd.Series) -> pd.Series:
    """Compute drawdown series from daily returns (decimal scale)."""
    cum_ret = (1 + daily_ret).cumprod()
    peak = cum_ret.cummax()
    return (cum_ret - peak) / peak


def compute_sharpe(daily_ret: pd.Series, min_rows: int = 30) -> float | None:
    """Compute annualized Sharpe ratio. Returns None if fewer than min_rows."""
    valid = daily_ret.dropna()
    if len(valid) < min_rows:
        return None
    return float(valid.mean() / valid.std() * np.sqrt(252))


def find_drawdown_episodes(drawdown: pd.Series, dates: pd.Series) -> list[dict]:
    """Identify contiguous drawdown episodes from a drawdown series.

    Returns list of dicts with Start, Trough, Depth, Recovery, days metrics.
    """
    episodes = []
    in_dd = False
    start_idx = None
    trough_idx = None
    trough_val = 0.0

    for i in range(len(drawdown)):
        dd = drawdown.iloc[i]
        if dd < 0 and not in_dd:
            in_dd = True
            start_idx = i
            trough_idx = i
            trough_val = dd
        elif dd < 0 and in_dd:
            if dd < trough_val:
                trough_idx = i
                trough_val = dd
        elif dd >= 0 and in_dd:
            episodes.append({
                "Start": dates.iloc[start_idx].strftime("%Y-%m-%d"),
                "Trough": dates.iloc[trough_idx].strftime("%Y-%m-%d"),
                "Depth": f"{trough_val * 100:.2f}%",
                "Recovery": dates.iloc[i].strftime("%Y-%m-%d"),
                "Days to Trough": (dates.iloc[trough_idx] - dates.iloc[start_idx]).days,
                "Days to Recovery": (dates.iloc[i] - dates.iloc[trough_idx]).days,
                "Status": "Recovered",
            })
            in_dd = False

    # Handle ongoing drawdown
    if in_dd:
        episodes.append({
            "Start": dates.iloc[start_idx].strftime("%Y-%m-%d"),
            "Trough": dates.iloc[trough_idx].strftime("%Y-%m-%d"),
            "Depth": f"{trough_val * 100:.2f}%",
            "Recovery": "—",
            "Days to Trough": (dates.iloc[trough_idx] - dates.iloc[start_idx]).days,
            "Days to Recovery": (dates.iloc[-1] - dates.iloc[trough_idx]).days,
            "Status": "Active",
        })

    return episodes
