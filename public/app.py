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

_logo_path = os.path.join(os.path.dirname(__file__), "assets", "NousErgonLogo_260319.png")
if os.path.exists(_logo_path):
    import base64
    with open(_logo_path, "rb") as _img_f:
        _logo_b64 = base64.b64encode(_img_f.read()).decode()
    st.markdown(
        f"""
        <div style="text-align: center; padding: 20px 0 0 0;">
            <img src="data:image/png;base64,{_logo_b64}"
                 alt="Nous Ergon: Alpha Engine"
                 style="max-width: 600px; width: 90%; margin-bottom: 8px;" />
            <div style="margin-top: 14px; font-size: 13px; letter-spacing: 1px;">
                <a href="/About" target="_self" style="color: #ccc; text-decoration: none; margin: 0 16px;">About</a>
                <a href="https://nous-ergon.hashnode.dev" target="_blank" style="color: #ccc; text-decoration: none; margin: 0 16px;">Blog</a>
                <a href="https://github.com/cipher813/alpha-engine" target="_blank" style="color: #ccc; text-decoration: none; margin: 0 16px;">GitHub</a>
                <a href="https://dashboard.nousergon.ai" target="_blank" style="color: #ccc; text-decoration: none; margin: 0 16px;">Dashboard</a>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        """
        <div style="text-align: center; padding: 20px 0 0 0;">
            <h1 style="margin-bottom: 0; font-size: 2.5em; letter-spacing: 2px;">
                Nous Ergon: Alpha Engine
            </h1>
            <p style="color: #888; font-size: 14px; margin-top: 4px; font-style: italic;">
                &nu;&omicron;&upsilon;&sigmaf; &epsilon;&rho;&gamma;&omicron;&nu; <span style="color:#666; font-size:12px;">(noose air-gone)</span>
            </p>
            <p style="color: #aaa; font-size: 14px; margin-top: 6px;">
                Intelligence at work
            </p>
            <p style="color: #999; font-size: 13px; margin-top: 8px;">
                AI-driven autonomous trading system
            </p>
            <div style="margin-top: 14px; font-size: 13px; letter-spacing: 1px;">
                <a href="/About" target="_self" style="color: #ccc; text-decoration: none; margin: 0 16px;">About</a>
                <a href="https://nous-ergon.hashnode.dev" target="_blank" style="color: #ccc; text-decoration: none; margin: 0 16px;">Blog</a>
                <a href="https://github.com/cipher813/alpha-engine" target="_blank" style="color: #ccc; text-decoration: none; margin: 0 16px;">GitHub</a>
                <a href="https://dashboard.nousergon.ai" target="_blank" style="color: #ccc; text-decoration: none; margin: 0 16px;">Dashboard</a>
            </div>
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

# Inception date: configurable override for account resets, else auto-detect
_inception_override = _cfg.get("inception_date")
if _inception_override:
    inception_date = pd.Timestamp(_inception_override)
    eod = eod[eod["date"] >= inception_date].reset_index(drop=True)
else:
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
        st.dataframe(pos_df, use_container_width=True, hide_index=True)
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
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)
