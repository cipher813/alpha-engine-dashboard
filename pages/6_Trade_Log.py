"""
Trade Log page — Filterable trade history with pagination, CSV export, and outcome join.
"""

import sys
import os
from datetime import date, timedelta

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loaders.s3_loader import load_trades_full
from loaders.db_loader import get_score_performance

st.set_page_config(page_title="Trade Log — Alpha Engine", layout="wide")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PAGE_SIZE = 25

BEAT_ICONS = {1: "✅", 0: "❌", True: "✅", False: "❌"}


def _beat_icon(val) -> str:
    if pd.isna(val):
        return "⏳"
    return BEAT_ICONS.get(val, "⏳")


def _to_decimal_maybe(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    return s


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

st.title("Trade Log")

# ---- Load data ----
with st.spinner("Loading trade data..."):
    trades_df = load_trades_full()
    perf_df = get_score_performance()

if trades_df is None or trades_df.empty:
    from loaders.s3_loader import get_recent_s3_errors
    recent = get_recent_s3_errors()
    if recent:
        st.error(f"Trade data unavailable — S3 error: {recent[-1].get('error_type', '?')}: {recent[-1].get('message', '')[:100]}")
    else:
        st.warning("trades_full.csv not available yet — no trades have been executed.")
    st.stop()

# Normalize columns
trades_df.columns = [c.strip().lower().replace(" ", "_") for c in trades_df.columns]

# Parse dates
date_col = next((c for c in ["date", "trade_date", "timestamp"] if c in trades_df.columns), None)
if date_col:
    trades_df[date_col] = pd.to_datetime(trades_df[date_col])
    trades_df = trades_df.sort_values(date_col, ascending=False).reset_index(drop=True)

# Determine action/signal column
action_col = next((c for c in ["action", "signal", "trade_type"] if c in trades_df.columns), None)
ticker_col = next((c for c in ["ticker", "symbol"] if c in trades_df.columns), None)
score_col = next((c for c in ["score", "composite_score"] if c in trades_df.columns), None)
regime_col = next((c for c in ["regime", "market_regime"] if c in trades_df.columns), None)
sector_col = next((c for c in ["sector"] if c in trades_df.columns), None)
size_col = next((c for c in ["position_size", "size", "quantity", "shares"] if c in trades_df.columns), None)

# -----------------------------------------------------------------------
# Filter Controls
# -----------------------------------------------------------------------
st.subheader("Filters")

f_col1, f_col2, f_col3 = st.columns([2, 2, 2])
f_col4, f_col5 = st.columns([2, 2])

with f_col1:
    if date_col:
        min_date = trades_df[date_col].min().date() if not trades_df.empty else date.today() - timedelta(days=365)
        max_date = trades_df[date_col].max().date() if not trades_df.empty else date.today()
        date_from = st.date_input("From Date", value=min_date, min_value=min_date, max_value=max_date)
        date_to = st.date_input("To Date", value=max_date, min_value=min_date, max_value=max_date)
    else:
        date_from = date_to = None

with f_col2:
    if action_col:
        all_actions = sorted(trades_df[action_col].dropna().unique().tolist())
        selected_actions = st.multiselect("Action / Signal", options=all_actions, default=[])
    else:
        selected_actions = []

with f_col3:
    ticker_filter = st.text_input("Ticker (contains)", placeholder="e.g. AAPL")

with f_col4:
    if regime_col:
        all_regimes = sorted(trades_df[regime_col].dropna().unique().tolist())
        selected_regimes = st.multiselect("Regime", options=all_regimes, default=[])
    else:
        selected_regimes = []

with f_col5:
    if score_col:
        trades_df[score_col] = pd.to_numeric(trades_df[score_col], errors="coerce")
        min_score_val = int(trades_df[score_col].min(skipna=True) or 0)
        min_score_filter = st.slider("Min Score", min_value=0, max_value=100, value=0, step=5)
    else:
        min_score_filter = 0

# ---- Apply filters ----
filtered = trades_df.copy()

if date_col and date_from and date_to:
    filtered = filtered[
        (filtered[date_col].dt.date >= date_from) & (filtered[date_col].dt.date <= date_to)
    ]

if selected_actions and action_col:
    filtered = filtered[filtered[action_col].isin(selected_actions)]

if ticker_filter and ticker_col:
    filtered = filtered[
        filtered[ticker_col].str.upper().str.contains(ticker_filter.upper(), na=False)
    ]

if selected_regimes and regime_col:
    filtered = filtered[filtered[regime_col].isin(selected_regimes)]

if score_col and min_score_filter > 0:
    filtered = filtered[filtered[score_col].fillna(0) >= min_score_filter]

# ---- Outcome join for ENTER trades ----
if perf_df is not None and not perf_df.empty and action_col and ticker_col:
    perf_df.columns = [c.strip().lower().replace(" ", "_") for c in perf_df.columns]
    perf_ticker_col = next((c for c in ["symbol", "ticker"] if c in perf_df.columns), None)
    perf_date_col = next((c for c in ["score_date", "date"] if c in perf_df.columns), None)

    if perf_ticker_col and perf_date_col:
        perf_df[perf_date_col] = pd.to_datetime(perf_df[perf_date_col]).dt.date.astype(str)
        if date_col:
            filtered["_join_date"] = filtered[date_col].dt.date.astype(str)
        perf_subset = perf_df[[perf_ticker_col, perf_date_col, "beat_spy_10d", "beat_spy_30d"]].rename(
            columns={
                perf_ticker_col: ticker_col,
                perf_date_col: "_join_date",
            }
        )
        if "_join_date" in filtered.columns:
            enter_mask = filtered[action_col].str.upper() == "ENTER"
            enter_rows = filtered[enter_mask].merge(
                perf_subset, on=[ticker_col, "_join_date"], how="left"
            )
            non_enter_rows = filtered[~enter_mask].copy()
            non_enter_rows["beat_spy_10d"] = None
            non_enter_rows["beat_spy_30d"] = None
            filtered = pd.concat([enter_rows, non_enter_rows], ignore_index=True)

            if date_col in filtered.columns:
                filtered = filtered.sort_values(date_col, ascending=False)

st.caption(f"Showing {len(filtered):,} of {len(trades_df):,} trades")

# -----------------------------------------------------------------------
# Trade Table with Pagination
# -----------------------------------------------------------------------
st.subheader("Trade History")

# Format beat columns if present
display_filtered = filtered.copy()
for col in ["beat_spy_10d", "beat_spy_30d"]:
    if col in display_filtered.columns:
        display_filtered[col] = display_filtered[col].apply(_beat_icon)
if "_join_date" in display_filtered.columns:
    display_filtered = display_filtered.drop(columns=["_join_date"])

total_pages = max(1, (len(display_filtered) + PAGE_SIZE - 1) // PAGE_SIZE)
page_num = st.number_input(
    f"Page (1–{total_pages})",
    min_value=1,
    max_value=total_pages,
    value=1,
    step=1,
)
start = (page_num - 1) * PAGE_SIZE
end = start + PAGE_SIZE
page_df = display_filtered.iloc[start:end]

st.dataframe(page_df, use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------
# Download Button
# -----------------------------------------------------------------------
csv_data = filtered.drop(columns=["_join_date"], errors="ignore").to_csv(index=False)
st.download_button(
    label="Download Filtered Trades (CSV)",
    data=csv_data,
    file_name="trades_filtered.csv",
    mime="text/csv",
)

st.divider()

# -----------------------------------------------------------------------
# Trade Summary Stats
# -----------------------------------------------------------------------
st.subheader("Trade Summary Stats")

s_col1, s_col2, s_col3, s_col4 = st.columns(4)

with s_col1:
    st.metric("Total Trades", f"{len(filtered):,}")

    if action_col:
        action_counts = filtered[action_col].value_counts()
        action_summary = ", ".join([f"{k}: {v}" for k, v in action_counts.items()])
        st.caption(f"By action: {action_summary}")

with s_col2:
    if score_col:
        avg_score = pd.to_numeric(filtered[score_col], errors="coerce").mean()
        st.metric("Avg Score", f"{avg_score:.1f}" if pd.notna(avg_score) else "—")
    else:
        st.metric("Avg Score", "—")

with s_col3:
    if regime_col:
        most_common_regime = filtered[regime_col].value_counts().idxmax() if not filtered[regime_col].empty else "—"
        st.metric("Most Common Regime", str(most_common_regime))
    else:
        st.metric("Most Common Regime", "—")

with s_col4:
    if size_col:
        avg_size = pd.to_numeric(filtered[size_col], errors="coerce").mean()
        st.metric("Avg Position Size", f"{avg_size:.2f}" if pd.notna(avg_size) else "—")
    else:
        st.metric("Avg Position Size", "—")

# Most active sectors
if sector_col and not filtered.empty:
    st.subheader("Most Active Sectors")
    sector_counts = filtered[sector_col].value_counts().head(5).reset_index()
    sector_counts.columns = ["Sector", "Trade Count"]
    st.dataframe(sector_counts, use_container_width=True, hide_index=True)
