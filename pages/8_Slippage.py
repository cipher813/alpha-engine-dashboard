"""
Slippage Monitor page — tracks execution quality by comparing price_at_order vs fill_price.

Now that the executor captures fill_price, fill_time, and filled_shares on every order,
this page surfaces execution quality metrics that were previously invisible.
"""

import sys
import os

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loaders.s3_loader import load_trades_full

st.set_page_config(page_title="Slippage Monitor — Alpha Engine", layout="wide")

st.title("Execution Slippage Monitor")

# ---- Load data ----
with st.spinner("Loading trade data..."):
    trades_df = load_trades_full()

if trades_df is None or trades_df.empty:
    st.warning("trades_full.csv not available yet.")
    st.stop()

# Normalize columns
trades_df.columns = [c.strip().lower().replace(" ", "_") for c in trades_df.columns]

# Check required columns exist
if "fill_price" not in trades_df.columns or "price_at_order" not in trades_df.columns:
    st.info(
        "Slippage data not yet available. The executor needs to run with "
        "fill confirmation enabled (deployed 2026-03-17) before slippage "
        "metrics can be computed."
    )
    st.stop()

# Parse and filter
trades_df["fill_price"] = pd.to_numeric(trades_df["fill_price"], errors="coerce")
trades_df["price_at_order"] = pd.to_numeric(trades_df["price_at_order"], errors="coerce")

# Only analyze trades with both prices
has_both = trades_df["fill_price"].notna() & trades_df["price_at_order"].notna()
slippage_df = trades_df[has_both].copy()

if slippage_df.empty:
    st.info("No trades with fill price data yet. Slippage metrics will appear after the next live trading session.")
    st.stop()

# Compute slippage in basis points
# Positive slippage = paid more than expected (bad for BUY) or received less (bad for SELL)
action_col = next((c for c in ["action", "signal"] if c in slippage_df.columns), None)

slippage_df["slippage_bps"] = (
    (slippage_df["fill_price"] - slippage_df["price_at_order"])
    / slippage_df["price_at_order"]
    * 10_000
).round(2)

# For SELL/EXIT/REDUCE, negative slippage is bad (received less than expected)
# Normalize: positive = unfavorable for all actions
if action_col:
    sell_mask = slippage_df[action_col].str.upper().isin(["SELL", "EXIT", "REDUCE"])
    slippage_df.loc[sell_mask, "slippage_bps"] = -slippage_df.loc[sell_mask, "slippage_bps"]

# Parse dates
date_col = next((c for c in ["date", "trade_date"] if c in slippage_df.columns), None)
if date_col:
    slippage_df[date_col] = pd.to_datetime(slippage_df[date_col])

# ---------------------------------------------------------------------------
# Summary Metrics
# ---------------------------------------------------------------------------
st.subheader("Summary")

m1, m2, m3, m4, m5 = st.columns(5)

with m1:
    st.metric("Trades with Fill Data", f"{len(slippage_df):,}")

with m2:
    mean_slip = slippage_df["slippage_bps"].mean()
    st.metric("Mean Slippage", f"{mean_slip:+.1f} bps")

with m3:
    median_slip = slippage_df["slippage_bps"].median()
    st.metric("Median Slippage", f"{median_slip:+.1f} bps")

with m4:
    p95_slip = slippage_df["slippage_bps"].quantile(0.95)
    st.metric("P95 Slippage", f"{p95_slip:+.1f} bps")

with m5:
    pct_negative = (slippage_df["slippage_bps"] > 0).mean() * 100
    st.metric("% Unfavorable", f"{pct_negative:.0f}%")

# ---------------------------------------------------------------------------
# Slippage Distribution
# ---------------------------------------------------------------------------
st.subheader("Slippage Distribution (bps)")

fig_hist = px.histogram(
    slippage_df,
    x="slippage_bps",
    nbins=50,
    title="Slippage Distribution (positive = unfavorable)",
    labels={"slippage_bps": "Slippage (bps)"},
    color_discrete_sequence=["#1f77b4"],
)
fig_hist.add_vline(x=0, line_dash="dash", line_color="red", annotation_text="Zero")
fig_hist.update_layout(height=350)
st.plotly_chart(fig_hist, use_container_width=True)

# ---------------------------------------------------------------------------
# Slippage by Action
# ---------------------------------------------------------------------------
if action_col:
    st.subheader("Slippage by Action")

    action_stats = (
        slippage_df.groupby(action_col)["slippage_bps"]
        .agg(["mean", "median", "std", "count"])
        .round(2)
        .reset_index()
    )
    action_stats.columns = ["Action", "Mean (bps)", "Median (bps)", "Std Dev", "Count"]
    st.dataframe(action_stats, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Slippage by Regime
# ---------------------------------------------------------------------------
regime_col = next((c for c in ["market_regime", "regime"] if c in slippage_df.columns), None)
if regime_col:
    st.subheader("Slippage by Market Regime")

    regime_stats = (
        slippage_df.groupby(regime_col)["slippage_bps"]
        .agg(["mean", "median", "count"])
        .round(2)
        .reset_index()
    )
    regime_stats.columns = ["Regime", "Mean (bps)", "Median (bps)", "Count"]
    st.dataframe(regime_stats, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Slippage Over Time
# ---------------------------------------------------------------------------
if date_col:
    st.subheader("Slippage Over Time")

    daily_slip = (
        slippage_df.groupby(slippage_df[date_col].dt.date)["slippage_bps"]
        .mean()
        .reset_index()
    )
    daily_slip.columns = ["Date", "Mean Slippage (bps)"]

    fig_time = px.line(
        daily_slip,
        x="Date",
        y="Mean Slippage (bps)",
        title="Daily Mean Slippage",
    )
    fig_time.add_hline(y=0, line_dash="dash", line_color="gray")
    fig_time.update_layout(height=350)
    st.plotly_chart(fig_time, use_container_width=True)

# ---------------------------------------------------------------------------
# Worst Slippage Events
# ---------------------------------------------------------------------------
st.subheader("Worst Slippage Events")

ticker_col = next((c for c in ["ticker", "symbol"] if c in slippage_df.columns), None)
display_cols = [c for c in [date_col, ticker_col, action_col, "price_at_order", "fill_price", "slippage_bps", "shares"] if c and c in slippage_df.columns]

worst = slippage_df.nlargest(20, "slippage_bps")[display_cols]
st.dataframe(worst, use_container_width=True, hide_index=True)
