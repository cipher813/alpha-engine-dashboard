"""
Signal data loading and flattening utilities for the Alpha Engine Dashboard.
Wraps s3_loader functions to provide structured DataFrames from signals.json.
"""

from datetime import date, datetime

import pandas as pd
import streamlit as st

from loaders.s3_loader import (
    load_config,
    list_s3_prefixes,
    download_s3_json,
)


def _research_bucket() -> str:
    return load_config()["s3"]["research_bucket"]


def _signals_key(date_str: str) -> str:
    return load_config()["paths"]["signals"].format(date=date_str)


def _ttl(key: str) -> int:
    return load_config()["cache_ttl"].get(key, 900)


# ---------------------------------------------------------------------------
# Date discovery
# ---------------------------------------------------------------------------


@st.cache_data(ttl=900)
def get_available_signal_dates() -> list[str]:
    """
    List s3://alpha-engine-research/signals/ and return all available date
    strings (YYYY-MM-DD) sorted descending (most recent first).
    """
    prefix = "signals/"
    dates = list_s3_prefixes(_research_bucket(), prefix)
    return sorted(dates, reverse=True)


# ---------------------------------------------------------------------------
# Signal loading
# ---------------------------------------------------------------------------


@st.cache_data(ttl=900)
def load_signals(date_str: str | None = None) -> dict | None:
    """
    Load signals.json for *date_str* (YYYY-MM-DD). Defaults to today's date.
    Returns the parsed dict or None if not found.
    """
    if date_str is None:
        date_str = date.today().isoformat()
    key = _signals_key(date_str)
    return download_s3_json(_research_bucket(), key)


# ---------------------------------------------------------------------------
# Flattening helpers
# ---------------------------------------------------------------------------


def _extract_sub_scores(entry: dict) -> tuple[float | None, float | None, float | None]:
    """
    Extract (technical, news, research) sub-scores from a signal entry.
    Handles both nested sub_scores dict and flat top-level keys.
    """
    sub = entry.get("sub_scores", {})
    if isinstance(sub, dict) and sub:
        technical = sub.get("technical")
        news = sub.get("news")
        research = sub.get("research")
    else:
        technical = entry.get("technical")
        news = entry.get("news")
        research = entry.get("research")
    return technical, news, research


def signals_to_df(signals_data: dict | None) -> pd.DataFrame:
    """
    Flatten the universe[] list from signals_data into a DataFrame.

    Columns: ticker, sector, signal, rating, score, conviction,
             technical, news, research, price_target_upside, thesis_summary, stale
    """
    if not signals_data:
        return pd.DataFrame()

    universe = signals_data.get("universe", [])
    if not universe:
        return pd.DataFrame()

    rows = []
    for entry in universe:
        technical, news, research = _extract_sub_scores(entry)
        rows.append(
            {
                "ticker": entry.get("ticker"),
                "sector": entry.get("sector"),
                "signal": entry.get("signal"),
                "rating": entry.get("rating"),
                "score": entry.get("score"),
                "conviction": entry.get("conviction"),
                "technical": technical,
                "news": news,
                "research": research,
                "price_target_upside": entry.get("price_target_upside"),
                "thesis_summary": entry.get("thesis_summary"),
                "stale": entry.get("stale", False),
            }
        )

    df = pd.DataFrame(rows)
    # Ensure numeric columns are numeric
    for col in ["score", "conviction", "technical", "news", "research", "price_target_upside"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def get_buy_candidates_df(signals_data: dict | None) -> pd.DataFrame:
    """
    Flatten the buy_candidates[] list from signals_data into a DataFrame.
    Same column structure as signals_to_df.
    """
    if not signals_data:
        return pd.DataFrame()

    candidates = signals_data.get("buy_candidates", [])
    if not candidates:
        return pd.DataFrame()

    rows = []
    for entry in candidates:
        technical, news, research = _extract_sub_scores(entry)
        rows.append(
            {
                "ticker": entry.get("ticker"),
                "sector": entry.get("sector"),
                "signal": entry.get("signal"),
                "rating": entry.get("rating"),
                "score": entry.get("score"),
                "conviction": entry.get("conviction"),
                "technical": technical,
                "news": news,
                "research": research,
                "price_target_upside": entry.get("price_target_upside"),
                "thesis_summary": entry.get("thesis_summary"),
                "stale": entry.get("stale", False),
            }
        )

    df = pd.DataFrame(rows)
    for col in ["score", "conviction", "technical", "news", "research", "price_target_upside"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def get_sector_ratings_df(signals_data: dict | None) -> pd.DataFrame:
    """
    Flatten the sector_ratings dict from signals_data into a DataFrame.
    Returns columns: sector, rating (and any other keys present).
    """
    if not signals_data:
        return pd.DataFrame()

    sector_ratings = signals_data.get("sector_ratings", {})
    if not sector_ratings:
        return pd.DataFrame()

    if isinstance(sector_ratings, dict):
        rows = []
        for sector, value in sector_ratings.items():
            if isinstance(value, dict):
                row = {"sector": sector, **value}
            else:
                row = {"sector": sector, "rating": value}
            rows.append(row)
        return pd.DataFrame(rows)
    elif isinstance(sector_ratings, list):
        return pd.DataFrame(sector_ratings)

    return pd.DataFrame()


# ---------------------------------------------------------------------------
# Signal count helpers
# ---------------------------------------------------------------------------


def get_signal_counts(signals_data: dict | None) -> dict:
    """
    Return a dict with counts for ENTER, EXIT, REDUCE, HOLD signals
    from the universe list.
    """
    df = signals_to_df(signals_data)
    counts = {"ENTER": 0, "EXIT": 0, "REDUCE": 0, "HOLD": 0}
    if df.empty or "signal" not in df.columns:
        return counts
    vc = df["signal"].value_counts()
    for k in counts:
        counts[k] = int(vc.get(k, 0))
    return counts
