"""
Nous Ergon — Public Portfolio Page
https://nousergon.ai

Displays portfolio performance vs S&P 500, cumulative alpha,
and current holdings. All data is read-only from S3 (server-side).
"""

import json

import pandas as pd
import streamlit as st

from loaders.s3_loader import load_eod_pnl
from charts.nav_chart import make_nav_chart, make_alpha_histogram

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
# Custom CSS
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    /* Hide Streamlit default header and footer for cleaner public look */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Metric styling */
    [data-testid="stMetric"] {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 8px;
        padding: 12px 16px;
    }
    [data-testid="stMetricLabel"] {
        font-size: 12px;
        color: #888;
    }
    [data-testid="stMetricValue"] {
        font-size: 24px;
    }

    /* Subtle link styling */
    a { color: #1a73e8; }
    a:hover { color: #4a9af5; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown(
    """
    <div style="text-align: center; padding: 20px 0 10px 0;">
        <h1 style="margin-bottom: 0; font-size: 2.5em; letter-spacing: 2px;">
            NOUS ERGON
        </h1>
        <p style="color: #888; font-size: 14px; margin-top: 4px; font-style: italic;">
            &nu;&omicron;&upsilon;&sigmaf; &epsilon;&rho;&gamma;&omicron;&nu; &mdash; mind at work
        </p>
        <p style="color: #aaa; font-size: 13px; margin-top: 8px;">
            AI-driven autonomous trading system generating alpha over the S&amp;P 500
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

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

inception_date = eod["date"].iloc[0]
latest = eod.iloc[-1]
nav = latest["portfolio_nav"]

# Cumulative returns
eod["port_cum"] = (1 + eod["port_ret"]).cumprod() - 1
eod["spy_cum"] = (1 + eod["spy_ret"]).cumprod() - 1
cumulative_alpha_bps = (eod["port_cum"].iloc[-1] - eod["spy_cum"].iloc[-1]) * 10_000

# Alpha days
up_days = (eod["daily_alpha"] > 0).sum()
down_days = (eod["daily_alpha"] < 0).sum()
flat_days = (eod["daily_alpha"] == 0).sum()
total_days = len(eod)

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
st.plotly_chart(fig_nav, use_container_width=True)

# ---------------------------------------------------------------------------
# Alpha Stats
# ---------------------------------------------------------------------------

st.markdown("### Alpha Performance")

col_a, col_b, col_c, col_d = st.columns(4)

win_rate = up_days / total_days * 100 if total_days > 0 else 0
avg_up_bps = eod.loc[eod["daily_alpha"] > 0, "daily_alpha"].mean() * 10_000 if up_days > 0 else 0
avg_down_bps = eod.loc[eod["daily_alpha"] < 0, "daily_alpha"].mean() * 10_000 if down_days > 0 else 0

col_a.metric("Win Rate", f"{win_rate:.1f}%")
col_b.metric("Avg Up-Alpha Day", f"+{avg_up_bps:.0f} bps")
col_c.metric("Avg Down-Alpha Day", f"{avg_down_bps:.0f} bps")
col_d.metric("Trading Days", f"{total_days}")

# Daily alpha bar chart
fig_alpha = make_alpha_histogram(eod)
st.plotly_chart(fig_alpha, use_container_width=True)

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
    if isinstance(positions, dict) and positions:
        rows = []
        for ticker, info in positions.items():
            rows.append({
                "Ticker": ticker,
                "Shares": info.get("shares", "—"),
                "Value": f"${info.get('market_value', 0):,.0f}",
                "Sector": info.get("sector", "—") or "—",
            })
        pos_df = pd.DataFrame(rows)
        st.dataframe(pos_df, use_container_width=True, hide_index=True)
    elif isinstance(positions, list) and positions:
        pos_df = pd.DataFrame(positions)
        if "ticker" in pos_df.columns:
            display = pos_df[["ticker"]].copy()
            display.columns = ["Ticker"]
            if "market_value" in pos_df.columns:
                display["Value"] = pos_df["market_value"].apply(
                    lambda v: f"${v:,.0f}" if isinstance(v, (int, float)) else v
                )
            if "sector" in pos_df.columns:
                display["Sector"] = pos_df["sector"]
            st.dataframe(display, use_container_width=True, hide_index=True)
        else:
            st.info("Position data format not recognized.")
    else:
        st.info("No open positions.")
except Exception:
    st.info("Position data unavailable.")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.divider()

st.markdown(
    """
    <div style="text-align: center; padding: 8px 0 20px 0;">
        <p style="color: #666; font-size: 12px;">
            Paper trading account &mdash; not financial advice
            &nbsp;&bull;&nbsp;
            <a href="/About" target="_self">About the model</a>
            &nbsp;&bull;&nbsp;
            <a href="https://dashboard.nousergon.ai" target="_blank">Full dashboard &rarr;</a>
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)
