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


# ── Per-position lifecycle rollup (ROADMAP L137) ────────────────────────────


_ENTRY_ACTIONS = ("ENTER", "SHORT_OPEN")
_EXIT_ACTIONS = ("EXIT", "REDUCE", "COVER", "SELL")


def compute_position_lifecycles(trades_df: pd.DataFrame | None) -> pd.DataFrame:
    """Aggregate ``trades.db`` rows into per-position-lifecycle records.

    A position-lifecycle is: one entry trade + N exit trades that link
    to it via ``entry_trade_id``. Closes when the entry's full size has
    been exited; partial exits (REDUCE) leave the lifecycle open.

    Returns columns:

      ticker | sector | entry_date | exit_date | holding_days
      | entry_price | shares_entered | n_exits | total_realized_pnl
      | total_realized_return_pct | total_realized_alpha_pct
      | status ("closed" | "open" | "open_partial")

    Closes the gap that L137 calls out: per-trade ``realized_pnl`` lives
    in ``trades.db`` (single fill), daily portfolio NAV decomposition
    lives in ``eod_pnl.csv``, but no view rolls them up to position
    lifecycle. Per the home endnote, that's the wording PR #100 had to
    reframe to "per-trade realized P&L" — this rollup re-enables
    "per-position P&L attribution" defensibly.

    Empty DataFrame on missing data; never raises.
    """
    if trades_df is None or trades_df.empty:
        return pd.DataFrame()
    if not {"trade_id", "action", "ticker"}.issubset(trades_df.columns):
        return pd.DataFrame()

    df = trades_df.copy()
    df["action_upper"] = df["action"].astype(str).str.upper()

    entries = df[df["action_upper"].isin(_ENTRY_ACTIONS)].copy()
    if entries.empty:
        return pd.DataFrame()

    exits = df[df["action_upper"].isin(_EXIT_ACTIONS)].copy()
    if "entry_trade_id" not in exits.columns:
        exits = exits.iloc[0:0]  # no linkage available — every entry stays open

    lifecycles: list[dict] = []
    for _, entry in entries.iterrows():
        trade_id = entry.get("trade_id")
        if not trade_id:
            continue
        linked = (
            exits[exits["entry_trade_id"] == trade_id]
            if not exits.empty and "entry_trade_id" in exits.columns
            else pd.DataFrame()
        )

        entry_date = pd.to_datetime(entry.get("date"), errors="coerce")
        entry_shares = pd.to_numeric(entry.get("shares"), errors="coerce") or 0
        entry_price = pd.to_numeric(
            entry.get("fill_price")
            or entry.get("price_at_order"),
            errors="coerce",
        )

        if linked.empty:
            lifecycles.append(
                {
                    "ticker": entry.get("ticker"),
                    "sector": entry.get("sector"),
                    "entry_date": entry_date,
                    "exit_date": pd.NaT,
                    "holding_days": None,
                    "entry_price": (float(entry_price) if pd.notna(entry_price) else None),
                    "shares_entered": int(entry_shares) if entry_shares else 0,
                    "n_exits": 0,
                    "total_realized_pnl": 0.0,
                    "total_realized_return_pct": None,
                    "total_realized_alpha_pct": None,
                    "status": "open",
                }
            )
            continue

        linked_dates = pd.to_datetime(linked["date"], errors="coerce")
        last_exit_date = linked_dates.max()
        shares_exited = pd.to_numeric(linked.get("shares"), errors="coerce").fillna(0).sum()
        total_pnl = pd.to_numeric(
            linked.get("realized_pnl"), errors="coerce",
        ).fillna(0.0).sum()
        # Weighted-average realized_return_pct + realized_alpha_pct across
        # exits, weighted by shares exited. Skipped (None) if any column is
        # absent or weights sum to zero.
        def _weighted_pct(col: str) -> float | None:
            if col not in linked.columns:
                return None
            vals = pd.to_numeric(linked[col], errors="coerce")
            weights = pd.to_numeric(linked.get("shares"), errors="coerce")
            valid = vals.notna() & weights.notna() & (weights > 0)
            if not valid.any():
                return None
            w_sum = float(weights[valid].sum())
            if w_sum == 0:
                return None
            return float((vals[valid] * weights[valid]).sum() / w_sum)

        is_closed = entry_shares and shares_exited >= entry_shares
        status = "closed" if is_closed else "open_partial"

        holding_days = None
        if pd.notna(entry_date) and pd.notna(last_exit_date):
            holding_days = int((last_exit_date - entry_date).days)

        lifecycles.append(
            {
                "ticker": entry.get("ticker"),
                "sector": entry.get("sector"),
                "entry_date": entry_date,
                "exit_date": last_exit_date if is_closed else pd.NaT,
                "holding_days": holding_days if is_closed else None,
                "entry_price": (float(entry_price) if pd.notna(entry_price) else None),
                "shares_entered": int(entry_shares) if entry_shares else 0,
                "n_exits": int(len(linked)),
                "total_realized_pnl": round(float(total_pnl), 2),
                "total_realized_return_pct": _weighted_pct("realized_return_pct"),
                "total_realized_alpha_pct": _weighted_pct("realized_alpha_pct"),
                "status": status,
            }
        )

    result = pd.DataFrame(lifecycles)
    if not result.empty and "entry_date" in result.columns:
        result = result.sort_values("entry_date", ascending=False, na_position="last").reset_index(drop=True)
    return result
