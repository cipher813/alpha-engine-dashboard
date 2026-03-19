"""
SQLite research.db loader for the Alpha Engine Dashboard.
Downloads research.db from S3 to /tmp and queries it via sqlite3.
"""

import logging
import sqlite3
import os

import pandas as pd
import streamlit as st

from loaders.s3_loader import load_config, download_s3_binary

logger = logging.getLogger(__name__)

_DB_LOCAL_PATH = "/tmp/research.db"
_DB_BUCKET_KEY = "research.db"


def _get_research_bucket() -> str:
    return load_config()["s3"]["research_bucket"]


def _get_db_path_key() -> str:
    return load_config()["paths"]["research_db"]


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------


@st.cache_resource(show_spinner=False)
def load_research_db() -> sqlite3.Connection | None:
    """
    Download research.db from S3 to /tmp/research.db and return a sqlite3
    connection. Returns None on failure. Cached as a resource (one connection
    per process).
    """
    try:
        bucket = _get_research_bucket()
        key = _get_db_path_key()
        success = download_s3_binary(bucket, key, _DB_LOCAL_PATH)
        if not success:
            return None
        conn = sqlite3.connect(_DB_LOCAL_PATH, check_same_thread=False)
        return conn
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Query helper
# ---------------------------------------------------------------------------


def query_research_db(sql: str, params=None) -> pd.DataFrame:
    """
    Execute *sql* against research.db and return a DataFrame.
    Returns an empty DataFrame on any failure.
    """
    conn = load_research_db()
    if conn is None:
        return pd.DataFrame()
    try:
        if params:
            return pd.read_sql_query(sql, conn, params=params)
        return pd.read_sql_query(sql, conn)
    except Exception as e:
        logger.warning("Query failed: %s — %s", sql[:100], e)
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Named queries
# ---------------------------------------------------------------------------


def _normalize_score_col(df: pd.DataFrame) -> pd.DataFrame:
    """Alias 'score' → 'composite_score' for backward compat with dashboard pages."""
    if not df.empty and "score" in df.columns and "composite_score" not in df.columns:
        df = df.rename(columns={"score": "composite_score"})
    return df


def get_score_performance() -> pd.DataFrame:
    """
    Return all rows from score_performance ordered by score_date ascending.
    Expected columns: score_date, symbol, composite_score, beat_spy_10d,
    beat_spy_30d, return_10d, return_30d, spy_10d_return, spy_30d_return, ...
    """
    sql = "SELECT * FROM score_performance ORDER BY score_date"
    return _normalize_score_col(query_research_db(sql))


def get_investment_thesis(symbol: str | None = None) -> pd.DataFrame:
    """
    Return rows from investment_thesis, optionally filtered by symbol.
    """
    if symbol:
        sql = "SELECT * FROM investment_thesis WHERE symbol = ?"
        return query_research_db(sql, params=(symbol,))
    return query_research_db("SELECT * FROM investment_thesis")


def get_macro_snapshots() -> pd.DataFrame:
    """
    Return all rows from macro_snapshots ordered by date ascending.
    Expected columns: date, regime, vix, yield_10yr, ...
    """
    sql = "SELECT * FROM macro_snapshots ORDER BY date"
    return query_research_db(sql)


def get_distinct_symbols() -> list[str]:
    """
    Return sorted list of distinct symbols from investment_thesis.
    """
    df = query_research_db(
        "SELECT DISTINCT symbol FROM investment_thesis ORDER BY symbol"
    )
    if df.empty or "symbol" not in df.columns:
        return []
    return df["symbol"].dropna().tolist()


def get_score_history(symbol: str) -> pd.DataFrame:
    """
    Return score history rows for a single symbol from score_performance.
    """
    sql = """
        SELECT score_date, score, beat_spy_10d, beat_spy_30d,
               return_10d, return_30d, spy_10d_return, spy_30d_return
        FROM score_performance
        WHERE symbol = ?
        ORDER BY score_date
    """
    return _normalize_score_col(query_research_db(sql, params=(symbol,)))


def get_top_recent_symbols(n: int = 10) -> pd.DataFrame:
    """
    Return the top *n* symbols by most recent score_date and highest composite_score.
    """
    sql = """
        SELECT sp.*
        FROM score_performance sp
        INNER JOIN (
            SELECT symbol, MAX(score_date) AS max_date
            FROM score_performance
            GROUP BY symbol
        ) latest ON sp.symbol = latest.symbol AND sp.score_date = latest.max_date
        ORDER BY sp.score DESC
        LIMIT ?
    """
    return _normalize_score_col(query_research_db(sql, params=(n,)))


def get_predictor_outcomes(symbol: str | None = None) -> pd.DataFrame:
    """Query predictor_outcomes table. Returns empty DataFrame if table missing."""
    if symbol:
        return query_research_db(
            "SELECT * FROM predictor_outcomes WHERE symbol = ? ORDER BY prediction_date DESC",
            params=(symbol,),
        )
    return query_research_db(
        "SELECT * FROM predictor_outcomes ORDER BY prediction_date DESC"
    )
