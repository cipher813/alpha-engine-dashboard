"""
Shared position parsing and P&L enrichment.

Centralizes the positions_snapshot parsing and P&L calculation that was
previously duplicated in app.py and pages/1_Portfolio.py.
"""

from __future__ import annotations

import json
import logging

import pandas as pd

from loaders.utils import safe_column

logger = logging.getLogger(__name__)


def parse_positions_snapshot(eod_df: pd.DataFrame | None) -> pd.DataFrame | None:
    """Extract positions DataFrame from the latest eod_pnl snapshot column."""
    if eod_df is None or eod_df.empty or "positions_snapshot" not in eod_df.columns:
        return None
    latest_row = eod_df.iloc[-1]
    try:
        snapshot_raw = latest_row["positions_snapshot"]
        if pd.notna(snapshot_raw) and snapshot_raw:
            positions_data = json.loads(str(snapshot_raw))
            if isinstance(positions_data, list):
                return pd.DataFrame(positions_data)
            elif isinstance(positions_data, dict):
                return pd.DataFrame([positions_data])
    except Exception as e:
        logger.warning("Failed to parse positions snapshot: %s", e)
    return None


def enrich_positions(
    positions_df: pd.DataFrame,
    signals_df: pd.DataFrame | None = None,
    trades_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Merge positions with signals and trade history, compute P&L columns.

    Args:
        positions_df: Raw positions from parse_positions_snapshot()
        signals_df: Flattened signals DataFrame (from signals_to_df), optional
        trades_df: Full trade log DataFrame, optional

    Returns:
        Enriched DataFrame with entry_price, current_price, unrealized_pnl,
        return_pct, days_held, score, signal, conviction columns added where
        source data is available.
    """
    df = positions_df.copy()

    # Merge signal scores
    if signals_df is not None and not signals_df.empty:
        if "ticker" in signals_df.columns and "ticker" in df.columns:
            merge_cols = [c for c in ["ticker", "score", "signal", "conviction"] if c in signals_df.columns]
            df = df.merge(signals_df[merge_cols], on="ticker", how="left", suffixes=("", "_signal"))

    # Merge entry price from most recent ENTER trade
    if trades_df is not None and not trades_df.empty:
        action_col = safe_column(trades_df, "action", "signal")
        if action_col and "ticker" in trades_df.columns and "ticker" in df.columns:
            enter_trades = trades_df[trades_df[action_col].str.upper() == "ENTER"].copy()
            if not enter_trades.empty and "date" in enter_trades.columns:
                enter_trades["date"] = pd.to_datetime(enter_trades["date"])
                latest_entry = enter_trades.sort_values("date").groupby("ticker").last().reset_index()
                price_col = safe_column(latest_entry, "price", "fill_price", "price_at_order")
                if price_col:
                    df = df.merge(
                        latest_entry[["ticker", price_col, "date"]].rename(
                            columns={price_col: "entry_price", "date": "entry_date"}
                        ),
                        on="ticker", how="left",
                    )

    # Compute P&L columns
    if "market_value" in df.columns and "shares" in df.columns:
        df["shares"] = pd.to_numeric(df["shares"], errors="coerce")
        df["market_value"] = pd.to_numeric(df["market_value"], errors="coerce")
        df["current_price"] = df["market_value"] / df["shares"]

        if "entry_price" in df.columns:
            df["entry_price"] = pd.to_numeric(df["entry_price"], errors="coerce")
            df["unrealized_pnl"] = (df["current_price"] - df["entry_price"]) * df["shares"]
            df["return_pct"] = df["current_price"] / df["entry_price"] - 1

        if "entry_date" in df.columns:
            df["days_held"] = (pd.Timestamp.now() - pd.to_datetime(df["entry_date"])).dt.days

    return df
