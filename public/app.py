"""
Nous Ergon — Public Portfolio Page
https://nousergon.ai

Displays portfolio performance vs S&P 500, cumulative alpha,
and current holdings. All data is read-only from S3 (server-side).
"""

import json
import os

import pandas as pd
import streamlit as st
import yaml

from components.header import render_header, render_footer
from components.styles import inject_base_css, inject_metric_css
from loaders.s3_loader import load_eod_pnl
from charts.nav_chart import make_nav_chart, make_alpha_histogram

# Load config
_config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
with open(_config_path) as _f:
    _cfg = yaml.safe_load(_f)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Nous Ergon",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Shared CSS + Header
# ---------------------------------------------------------------------------

inject_base_css()
inject_metric_css()
render_header(current_page="Home")

st.divider()

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

eod = load_eod_pnl()

if eod is None or eod.empty:
    st.warning("Portfolio data temporarily unavailable. Please check back later.")
    st.stop()

# Parse and prepare
eod["date"] = pd.to_datetime(eod["date"])
eod = eod.sort_values("date").reset_index(drop=True)

# Returns in eod_pnl.csv are stored as percentages (e.g., 0.876 = 0.876%)
# Convert to decimals for cumulative return math
eod["port_ret"] = pd.to_numeric(eod["daily_return_pct"], errors="coerce").fillna(0.0) / 100.0
eod["spy_ret"] = pd.to_numeric(eod["spy_return_pct"], errors="coerce").fillna(0.0) / 100.0
eod["daily_alpha"] = pd.to_numeric(eod["daily_alpha_pct"], errors="coerce").fillna(0.0) / 100.0

# Inception date: configurable override for account resets, else auto-detect
_inception_override = _cfg.get("inception_date")
if _inception_override:
    inception_date = pd.Timestamp(_inception_override)
    eod = eod[eod["date"] >= inception_date].reset_index(drop=True)
else:
    inception_date = eod["date"].iloc[0]

# Day 0 = inception baseline — exclude from alpha/return calculations
# Alpha accumulates from day 1 onward
eod_active = eod.iloc[1:].reset_index(drop=True) if len(eod) > 1 else eod
latest = eod.iloc[-1]
nav = latest["portfolio_nav"]

# Cumulative returns (from day 1 onward)
eod_active["port_cum"] = (1 + eod_active["port_ret"]).cumprod() - 1
eod_active["spy_cum"] = (1 + eod_active["spy_ret"]).cumprod() - 1
cumulative_alpha_bps = (eod_active["port_cum"].iloc[-1] - eod_active["spy_cum"].iloc[-1]) * 10_000 if len(eod_active) > 0 else 0

# For charting, include day 0 as the zero baseline
eod["port_cum"] = 0.0
eod["spy_cum"] = 0.0
if len(eod) > 1:
    eod.loc[eod.index[1:], "port_cum"] = eod_active["port_cum"].values
    eod.loc[eod.index[1:], "spy_cum"] = eod_active["spy_cum"].values

# Alpha days (exclude day 0)
up_days = (eod_active["daily_alpha"] > 0).sum()
down_days = (eod_active["daily_alpha"] < 0).sum()
flat_days = (eod_active["daily_alpha"] == 0).sum()
total_days = len(eod_active)

# ---------------------------------------------------------------------------
# KPI Row
# ---------------------------------------------------------------------------

col1, col2, col3, col4 = st.columns(4)

col1.metric("Inception", inception_date.strftime("%b %d, %Y"))
col2.metric("Portfolio NAV", f"${nav:,.0f}")
col3.metric(
    "Cumulative Alpha",
    f"{cumulative_alpha_bps:+.0f} bps",
    delta="vs S&P 500",
    delta_color="off",
)
col4.metric("Alpha Days", f"{up_days} ▲  {down_days} ▼")

# ---------------------------------------------------------------------------
# NAV vs SPY Chart
# ---------------------------------------------------------------------------

st.markdown("### Portfolio vs S&P 500")
fig_nav = make_nav_chart(eod)
st.plotly_chart(fig_nav, width="stretch")

# ---------------------------------------------------------------------------
# Alpha Stats
# ---------------------------------------------------------------------------

st.markdown("### Alpha Performance")

col_a, col_b, col_c, col_d = st.columns(4)

win_rate = up_days / total_days * 100 if total_days > 0 else 0
avg_up_bps = eod_active.loc[eod_active["daily_alpha"] > 0, "daily_alpha"].mean() * 10_000 if up_days > 0 else 0
avg_down_bps = eod_active.loc[eod_active["daily_alpha"] < 0, "daily_alpha"].mean() * 10_000 if down_days > 0 else 0

col_a.metric("Win Rate", f"{win_rate:.1f}%")
col_b.metric("Avg Up-Alpha Day", f"+{avg_up_bps:.0f} bps")
col_c.metric("Avg Down-Alpha Day", f"{avg_down_bps:.0f} bps")
col_d.metric("Trading Days", f"{total_days}")

# Daily alpha bar chart
fig_alpha = make_alpha_histogram(eod)
st.plotly_chart(fig_alpha, width="stretch")

# ---------------------------------------------------------------------------
# Current Holdings
# ---------------------------------------------------------------------------

st.markdown("### Current Holdings")

try:
    snapshot_raw = latest.get("positions_snapshot", "{}")
    if pd.isna(snapshot_raw):
        snapshot_raw = "{}"
    positions = json.loads(snapshot_raw)

    # positions_snapshot can be:
    #   - dict: {"AAPL": {"shares": 100, "market_value": 15000, ...}, ...}
    #   - list: [{"ticker": "AAPL", "market_value": 15000, ...}, ...]
    #   - empty dict/list
    # Build rows from dict or list format
    rows = []
    total_invested = 0.0
    if isinstance(positions, dict) and positions:
        for ticker, info in positions.items():
            mv = info.get("market_value", 0) or 0
            total_invested += mv
            rows.append({
                "Ticker": ticker,
                "Shares": info.get("shares", "—"),
                "Value": f"${mv:,.0f}",
                "Sector": info.get("sector", "—") or "—",
            })
    elif isinstance(positions, list) and positions:
        for p in positions:
            mv = p.get("market_value", 0) or 0
            total_invested += mv
            rows.append({
                "Ticker": p.get("ticker", "?"),
                "Shares": p.get("shares", "—"),
                "Value": f"${mv:,.0f}",
                "Sector": p.get("sector", "—") or "—",
            })

    if rows:
        # Add cash row
        cash = nav - total_invested
        rows.append({
            "Ticker": "💵 CASH",
            "Shares": "—",
            "Value": f"${cash:,.0f}",
            "Sector": "—",
        })
        pos_df = pd.DataFrame(rows)
        pos_df["Shares"] = pos_df["Shares"].astype(str)
        st.dataframe(pos_df, width="stretch", hide_index=True)
    else:
        st.info("No open positions.")
except Exception:
    st.info("Position data unavailable.")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

render_footer()
