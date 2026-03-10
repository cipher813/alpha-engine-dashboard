"""
Portfolio page — NAV chart, drawdown, positions, summary stats.
"""

import json
import sys
import os
from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loaders.s3_loader import load_config, load_eod_pnl, load_trades_full, load_signals_json
from loaders.signal_loader import signals_to_df
from charts.nav_chart import make_nav_chart
from charts.alpha_chart import make_alpha_chart

st.set_page_config(page_title="Portfolio — Alpha Engine", layout="wide")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_decimal(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").fillna(0.0)
    if s.abs().mean() > 1.0:
        s = s / 100.0
    return s


def _compute_drawdown(daily_ret: pd.Series) -> pd.Series:
    """Compute drawdown series from daily returns (decimal scale)."""
    cum_ret = (1 + daily_ret).cumprod()
    peak = cum_ret.cummax()
    drawdown = (cum_ret - peak) / peak
    return drawdown


def _compute_sharpe(daily_ret: pd.Series) -> float | None:
    """Compute annualized Sharpe ratio. Requires >= 30 rows."""
    valid = daily_ret.dropna()
    if len(valid) < 30:
        return None
    return float(valid.mean() / valid.std() * np.sqrt(252))


def _fmt_pct(val, decimals=2, sign=True) -> str:
    try:
        v = float(val) * 100
        fmt = f"{v:+.{decimals}f}%" if sign else f"{v:.{decimals}f}%"
        return fmt
    except Exception:
        return "—"


def _fmt_dollar(val) -> str:
    try:
        return f"${float(val):,.2f}"
    except Exception:
        return "—"


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

st.title("Portfolio Overview")
st.caption(f"Last updated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')} UTC")

cfg = load_config()
circuit_breaker = cfg.get("drawdown_circuit_breaker", -0.08)

# Load data
with st.spinner("Loading portfolio data..."):
    eod_df = load_eod_pnl()
    trades_df = load_trades_full()
    today = date.today().isoformat()
    signals_data = load_signals_json(today)

if eod_df is None or eod_df.empty:
    st.warning("Portfolio data (eod_pnl.csv) not available yet.")
    st.stop()

eod_df["date"] = pd.to_datetime(eod_df["date"])
eod_df = eod_df.sort_values("date").reset_index(drop=True)

daily_ret = _to_decimal(eod_df["daily_return_pct"])
spy_ret = _to_decimal(eod_df["spy_return_pct"])

# ---------------------------------------------------------------------------
# Section 1: NAV vs SPY
# ---------------------------------------------------------------------------
st.header("NAV vs SPY — Cumulative Return")
nav_fig = make_nav_chart(eod_df)
st.plotly_chart(nav_fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Section 2: Daily Alpha
# ---------------------------------------------------------------------------
st.header("Daily Alpha")
alpha_fig = make_alpha_chart(eod_df)
st.plotly_chart(alpha_fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Section 3: Drawdown
# ---------------------------------------------------------------------------
st.header("Drawdown")

drawdown = _compute_drawdown(daily_ret)
drawdown_pct = drawdown * 100

drawdown_fig = go.Figure()

drawdown_fig.add_trace(
    go.Scatter(
        x=eod_df["date"],
        y=drawdown_pct,
        fill="tozeroy",
        mode="lines",
        fillcolor="rgba(214,39,40,0.25)",
        line=dict(color="#d62728", width=1.5),
        name="Drawdown",
        hovertemplate="<b>%{x|%Y-%m-%d}</b><br>Drawdown: %{y:.2f}%<extra></extra>",
    )
)

# Circuit breaker line
drawdown_fig.add_hline(
    y=circuit_breaker * 100,
    line=dict(color="#ff7f0e", width=2, dash="dash"),
    annotation_text=f"Circuit Breaker ({circuit_breaker * 100:.0f}%)",
    annotation_position="top right",
    annotation_font_color="#ff7f0e",
)

drawdown_fig.update_layout(
    xaxis=dict(title="Date", showgrid=True, gridcolor="rgba(0,0,0,0.07)"),
    yaxis=dict(
        title="Drawdown (%)",
        ticksuffix="%",
        showgrid=True,
        gridcolor="rgba(0,0,0,0.07)",
        zeroline=True,
        zerolinecolor="rgba(0,0,0,0.3)",
    ),
    plot_bgcolor="white",
    paper_bgcolor="white",
    margin=dict(t=20, b=40, l=60, r=20),
    showlegend=False,
)

# Circuit breaker breach alert
max_dd = drawdown_pct.min()
if max_dd <= circuit_breaker * 100:
    st.error(
        f"Circuit breaker breached! Max drawdown: {max_dd:.2f}% "
        f"(threshold: {circuit_breaker * 100:.0f}%)"
    )

st.plotly_chart(drawdown_fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Section 4: Current Positions
# ---------------------------------------------------------------------------
st.header("Current Positions")

positions_df = None

# Parse positions_snapshot from the latest eod_pnl row
latest_row = eod_df.iloc[-1]
if "positions_snapshot" in eod_df.columns:
    try:
        snapshot_raw = latest_row["positions_snapshot"]
        if pd.notna(snapshot_raw) and snapshot_raw:
            positions_data = json.loads(str(snapshot_raw))
            if isinstance(positions_data, list):
                positions_df = pd.DataFrame(positions_data)
            elif isinstance(positions_data, dict):
                positions_df = pd.DataFrame([positions_data])
    except Exception:
        positions_df = None

if positions_df is not None and not positions_df.empty:
    # Join with today's signals for score
    if signals_data:
        sig_df = signals_to_df(signals_data)
        if not sig_df.empty and "ticker" in sig_df.columns:
            ticker_col = "ticker" if "ticker" in positions_df.columns else None
            if ticker_col:
                positions_df = positions_df.merge(
                    sig_df[["ticker", "score", "signal", "conviction"]],
                    on="ticker",
                    how="left",
                    suffixes=("", "_signal"),
                )

    # Join with trades to show return since entry
    if trades_df is not None and not trades_df.empty:
        enter_trades = trades_df[trades_df.get("action", trades_df.get("signal", "")).str.upper() == "ENTER"] if "action" in trades_df.columns or "signal" in trades_df.columns else pd.DataFrame()
        if not enter_trades.empty:
            ticker_col = "ticker" if "ticker" in enter_trades.columns else None
            if ticker_col and "ticker" in positions_df.columns:
                # Get most recent ENTER price per ticker
                if "date" in enter_trades.columns:
                    enter_trades["date"] = pd.to_datetime(enter_trades["date"])
                    latest_entry = enter_trades.sort_values("date").groupby("ticker").last().reset_index()
                    price_col = "price" if "price" in latest_entry.columns else None
                    if price_col:
                        positions_df = positions_df.merge(
                            latest_entry[["ticker", price_col, "date"]].rename(
                                columns={price_col: "entry_price", "date": "entry_date"}
                            ),
                            on="ticker",
                            how="left",
                        )

    st.dataframe(positions_df, use_container_width=True, hide_index=True)
else:
    st.info("No positions snapshot available in today's data.")

# ---------------------------------------------------------------------------
# Section 5: Portfolio Summary Stats
# ---------------------------------------------------------------------------
st.header("Portfolio Summary Stats")

total_return = ((1 + daily_ret).prod() - 1)
sharpe = _compute_sharpe(daily_ret)
max_drawdown = drawdown.min()
best_day = daily_ret.max()
worst_day = daily_ret.min()
days_positive = int((daily_ret > 0).sum())
days_negative = int((daily_ret < 0).sum())
alpha_series = _to_decimal(eod_df["daily_alpha_pct"]) if "daily_alpha_pct" in eod_df.columns else pd.Series(dtype=float)
avg_daily_alpha = alpha_series.mean() if not alpha_series.empty else None

stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
stat_col5, stat_col6, stat_col7, stat_col8 = st.columns(4)

with stat_col1:
    st.metric("Total Return", _fmt_pct(total_return))

with stat_col2:
    if sharpe is not None:
        st.metric("Sharpe Ratio", f"{sharpe:.2f}")
    else:
        st.metric("Sharpe Ratio", f"Need ≥30 days ({len(daily_ret)} available)")

with stat_col3:
    st.metric("Max Drawdown", _fmt_pct(max_drawdown))

with stat_col4:
    st.metric("Best Day", _fmt_pct(best_day))

with stat_col5:
    st.metric("Worst Day", _fmt_pct(worst_day))

with stat_col6:
    st.metric("Days Positive", f"{days_positive}")

with stat_col7:
    st.metric("Days Negative", f"{days_negative}")

with stat_col8:
    if avg_daily_alpha is not None:
        st.metric("Avg Daily Alpha", _fmt_pct(avg_daily_alpha))
    else:
        st.metric("Avg Daily Alpha", "—")
