"""Pure transforms for the Attractiveness Trends page (no Streamlit) — so the
cross-repo consumer contract with crucible-research
``scoring/attractiveness_trajectory.py`` (``scanner/universe/trajectory/latest.json``,
``schema_version=1``) and the attractiveness-history parquet is unit-testable
independently of the Streamlit chrome in ``views/40_Attractiveness_Trends.py``.
"""
from __future__ import annotations

import pandas as pd

# Per-ticker columns the producer emits (see crucible-research
# scoring/attractiveness_trajectory.build_trajectory).
TRAJECTORY_COLS = [
    "ticker", "sector", "attr_slope", "attr_slope_z", "n_points", "slope_significant",
    "price_ret", "sector_rel_price_ret", "price_mom_z", "pre_repricing_score",
    "rising", "pre_repricing", "rising_rank", "pre_repricing_rank",
]

_META_KEYS = ("schema_version", "as_of", "window_weeks", "method", "orthogonalization_beta",
              "n_universe", "n_rising", "n_pre_repricing", "provisional_ic")


def trajectory_meta(artifact: dict) -> dict:
    """Top-level signal metadata for the page header. Empty-safe."""
    a = artifact or {}
    return {k: a.get(k) for k in _META_KEYS}


def flatten_trajectory(artifact: dict) -> pd.DataFrame:
    """Trajectory artifact → a per-ticker DataFrame (the leaderboard substrate).
    Missing columns degrade to None; empty artifact → empty frame."""
    stocks = (artifact or {}).get("stocks") or []
    df = pd.DataFrame(stocks)
    if df.empty:
        return df
    for c in TRAJECTORY_COLS:
        if c not in df.columns:
            df[c] = None
    return df[TRAJECTORY_COLS]


def pre_repricing_table(df: pd.DataFrame, top_n: int | None = None) -> pd.DataFrame:
    """Rising-attractiveness names whose price lags (residual top decile),
    ordered by pre_repricing_rank."""
    if df.empty:
        return df
    out = df[df["pre_repricing"] == True].sort_values("pre_repricing_rank")  # noqa: E712
    return out.head(top_n) if top_n else out


def rising_table(df: pd.DataFrame, top_n: int | None = None) -> pd.DataFrame:
    """All names with a significant positive attractiveness trend, by rising_rank."""
    if df.empty:
        return df
    out = df[df["rising"] == True].sort_values("rising_rank")  # noqa: E712
    return out.head(top_n) if top_n else out


def ticker_series(history_df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Per-stock attractiveness time-series (date-indexed) for the chart, from
    the history parquet. Empty frame when the ticker / history is absent."""
    if history_df is None or history_df.empty or "ticker" not in history_df.columns:
        return pd.DataFrame()
    d = history_df[history_df["ticker"] == ticker].copy()
    if d.empty:
        return pd.DataFrame()
    d["as_of"] = pd.to_datetime(d["as_of"])
    cols = [c for c in ("attractiveness_score", "attractiveness_raw") if c in d.columns]
    return d.sort_values("as_of").set_index("as_of")[cols]
