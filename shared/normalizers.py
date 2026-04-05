"""
Shared return normalization utilities.

Centralizes the decimal-vs-percent detection logic that was previously
duplicated in app.py, 1_Portfolio.py, nav_chart.py, alpha_chart.py,
and accuracy_chart.py.
"""

from __future__ import annotations

import pandas as pd


def to_decimal_series(series: pd.Series) -> pd.Series:
    """Convert a return series to decimal scale (0.05 for 5%).

    If max absolute value > 1.0, assumes percent scale and divides by 100.
    Returns a new Series (does not modify in place).
    """
    s = pd.to_numeric(series, errors="coerce").fillna(0.0)
    if len(s) > 0 and s.abs().max() > 1.0:
        s = s / 100.0
    return s


def to_decimal_scalar(val) -> float | None:
    """Convert a single return value to decimal scale.

    Values with abs > 2 are treated as percent (e.g. 5.2 -> 0.052).
    """
    try:
        v = float(val)
        return v / 100 if abs(v) > 2 else v
    except (ValueError, TypeError):
        return None
