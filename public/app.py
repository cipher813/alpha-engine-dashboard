"""
Nous Ergon — Public Portfolio Page
https://nousergon.ai

Layout (top to bottom):
  1. Performance — KPI metrics + NAV vs SPY chart + alpha stats
  2. Current Holdings — positions with value
  3. Order Book / Trades — market-aware view
  4. Daily Decisions — predictor vetoes + risk guard blocks
  5. Research Population — weekly picks
"""

import json
import os
from datetime import date, datetime

import pandas as pd
import streamlit as st
import yaml

from components.header import render_header, render_footer
from components.phase_indicator import render_phase_indicator, render_phase_caption
from components.styles import inject_base_css, inject_metric_css
from components.uptime_kpi import render_uptime_kpi
from loaders.s3_loader import (
    load_eod_pnl,
    load_trades_full,
    load_population_json,
    load_predictions_json,
    load_order_book_summary,
    load_predictor_metrics,
    load_uptime_history,
)
from charts.nav_chart import make_nav_chart, make_alpha_histogram

_CURRENT_PHASE = "Reliability Hardening"
_UPTIME_WINDOW_SESSIONS = 20

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
# Helpers
# ---------------------------------------------------------------------------


def _is_market_open() -> bool:
    from zoneinfo import ZoneInfo
    now_et = datetime.now(ZoneInfo("US/Eastern"))
    if now_et.weekday() >= 5:
        return False
    market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now_et <= market_close


def _most_recent_trading_date(trades_df: pd.DataFrame | None) -> str | None:
    if trades_df is None or trades_df.empty or "date" not in trades_df.columns:
        return None
    dates = pd.to_datetime(trades_df["date"]).dt.date.unique()
    return str(max(dates)) if len(dates) > 0 else None


# ---------------------------------------------------------------------------
# Shared CSS + Header
# ---------------------------------------------------------------------------

inject_base_css()
inject_metric_css()
render_header(current_page="Home")

# ---------------------------------------------------------------------------
# Phase Indicator (hero framing — above the fold)
# ---------------------------------------------------------------------------

render_phase_indicator(current_phase=_CURRENT_PHASE)
render_phase_caption(current_phase=_CURRENT_PHASE)

st.divider()

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

today = date.today().isoformat()
eod = load_eod_pnl()
trades_df = load_trades_full()
population_data = load_population_json()
predictions_data = load_predictions_json()
predictor_metrics = load_predictor_metrics()
order_book_summary = load_order_book_summary(today)
uptime_history = load_uptime_history(max_sessions=_UPTIME_WINDOW_SESSIONS)

# ---------------------------------------------------------------------------
# Section 0: Reliability — current-phase primary KPI
# ---------------------------------------------------------------------------

render_uptime_kpi(uptime_history)

st.divider()

if eod is None or eod.empty:
    st.warning("Portfolio data temporarily unavailable. Please check back later.")
    st.stop()

# Parse and prepare
eod["date"] = pd.to_datetime(eod["date"])
eod = eod.sort_values("date").reset_index(drop=True)

eod["port_ret"] = pd.to_numeric(eod["daily_return_pct"], errors="coerce").fillna(0.0) / 100.0
eod["spy_ret"] = pd.to_numeric(eod["spy_return_pct"], errors="coerce").fillna(0.0) / 100.0
eod["daily_alpha"] = pd.to_numeric(eod["daily_alpha_pct"], errors="coerce").fillna(0.0) / 100.0

# Inception date
_inception_override = _cfg.get("inception_date")
if _inception_override:
    inception_date = pd.Timestamp(_inception_override)
    eod = eod[eod["date"] >= inception_date].reset_index(drop=True)
else:
    inception_date = eod["date"].iloc[0]

# Day 0 = inception baseline
eod_active = eod.iloc[1:].reset_index(drop=True) if len(eod) > 1 else eod
latest = eod.iloc[-1]
nav = latest["portfolio_nav"]

# Cumulative returns — direct from NAV and spy_close (no daily chaining)
nav_0 = eod["portfolio_nav"].iloc[0]
eod["port_cum"] = eod["portfolio_nav"] / nav_0 - 1

spy_close = pd.to_numeric(eod.get("spy_close"), errors="coerce")
if spy_close.notna().sum() >= 2:
    spy_0 = spy_close.dropna().iloc[0]
    eod["spy_cum"] = spy_close / spy_0 - 1
    # Forward-fill for any rows missing spy_close
    eod["spy_cum"] = eod["spy_cum"].ffill().fillna(0.0)
else:
    # Fallback to cumprod if spy_close is entirely missing
    eod["spy_cum"] = 0.0
    if len(eod_active) > 0:
        eod_active["spy_cum"] = (1 + eod_active["spy_ret"]).cumprod() - 1
        eod.loc[eod.index[1:], "spy_cum"] = eod_active["spy_cum"].values

cumulative_alpha_bps = (eod["port_cum"].iloc[-1] - eod["spy_cum"].iloc[-1]) * 10_000 if len(eod) > 0 else 0

# Alpha days
up_days = (eod_active["daily_alpha"] > 0).sum()
down_days = (eod_active["daily_alpha"] < 0).sum()
total_days = len(eod_active)

# ===========================================================================
# Section 1: Performance — Secondary KPIs (Phase 3 primary metric)
# ===========================================================================

st.markdown("### Portfolio Performance — Secondary Metric")
st.caption(
    "Alpha is tracked but not optimized until uptime reaches 99%. "
    "Phase 2 crashes skew short-run results; these numbers will become the headline KPI in Phase 3."
)

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

# NAV vs SPY chart
_perf_date = eod["date"].iloc[-1].strftime("%Y-%m-%d")
st.markdown("### Portfolio vs S&P 500")
st.caption(f"As of {_perf_date}")
fig_nav = make_nav_chart(eod)
st.plotly_chart(fig_nav, width="stretch")

# Alpha stats
st.markdown("### Alpha Performance")
st.caption(f"As of {_perf_date}")

col_a, col_b, col_c, col_d = st.columns(4)
win_rate = up_days / total_days * 100 if total_days > 0 else 0
avg_up_bps = eod_active.loc[eod_active["daily_alpha"] > 0, "daily_alpha"].mean() * 10_000 if up_days > 0 else 0
avg_down_bps = eod_active.loc[eod_active["daily_alpha"] < 0, "daily_alpha"].mean() * 10_000 if down_days > 0 else 0

col_a.metric("Win Rate", f"{win_rate:.1f}%")
col_b.metric("Avg Up-Alpha Day", f"+{avg_up_bps:.0f} bps")
col_c.metric("Avg Down-Alpha Day", f"{avg_down_bps:.0f} bps")
col_d.metric("Trading Days", f"{total_days}")

fig_alpha = make_alpha_histogram(eod)
st.plotly_chart(fig_alpha, width="stretch")

st.divider()

# ===========================================================================
# Section 2: Current Holdings
# ===========================================================================

st.markdown("### Current Holdings")
st.caption(f"As of {_perf_date}")

try:
    snapshot_raw = latest.get("positions_snapshot", "{}")
    if pd.isna(snapshot_raw):
        snapshot_raw = "{}"
    positions = json.loads(snapshot_raw)

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
        cash = nav - total_invested
        rows.append({
            "Ticker": "CASH",
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

st.divider()

# ===========================================================================
# Section 3: Recent Trades
# ===========================================================================

# Show trades from most recent market session, but only if that session
# is today or after the most recent market close. Reset once market opens
# again (new session = no trades yet).
if trades_df is not None and not trades_df.empty and "date" in trades_df.columns:
    recent_date = _most_recent_trading_date(trades_df)
    if recent_date:
        recent_dt = date.fromisoformat(recent_date)
        # Show trades if: (a) market is closed and trades are from today or
        # the most recent trading day, or (b) market is open and trades are
        # from today (intraday fills)
        show_trades = False
        if _is_market_open():
            show_trades = (recent_dt == date.today())
        else:
            show_trades = True  # market closed — show last session

        if show_trades:
            trades_copy = trades_df.copy()
            trades_copy["date"] = pd.to_datetime(trades_copy["date"]).dt.date
            recent_trades = trades_copy[trades_copy["date"] == recent_dt]
            if not recent_trades.empty:
                st.markdown("### Recent Trades")
                display_cols = ["ticker"]
                for col in ["action", "signal"]:
                    if col in recent_trades.columns:
                        display_cols.append(col)
                        break
                st.caption(f"As of {recent_date}")
                st.dataframe(
                    recent_trades[display_cols].reset_index(drop=True),
                    width="stretch", hide_index=True,
                )
                st.divider()

# ===========================================================================
# Section 4: Research Population + Pipeline Decisions (combined table)
# ===========================================================================

st.markdown("### Investment Universe")
if population_data and population_data.get("population"):
    _pop_date = population_data.get("date", "unknown")
    st.caption(f"Research picks as of {_pop_date}")
    pop = population_data["population"]
    pop_date = population_data.get("date", "unknown")
    regime = population_data.get("market_regime", "unknown")

    # Last refreshed: most recent of population, predictor, or risk guard
    last_refreshed = pop_date
    _last_run = (predictor_metrics or {}).get("last_run_utc", "")[:10]
    if _last_run and _last_run > last_refreshed:
        last_refreshed = _last_run
    if order_book_summary:
        _ob_date = order_book_summary.get("date", "")
        if _ob_date and _ob_date > last_refreshed:
            last_refreshed = _ob_date

    regime_emoji = {"bull": "🐂", "bear": "🐻", "neutral": "➡️", "caution": "⚠️"}.get(
        str(regime).lower(), "📊"
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Market Regime", f"{regime_emoji} {str(regime).title()}")
    with col2:
        st.metric("Universe Size", str(len(pop)))
    with col3:
        st.metric("Last Refreshed", last_refreshed)

    # Build combined table: population + predictor veto + risk guard status
    pop_df = pd.DataFrame(pop)

    # Title-case conviction
    if "conviction" in pop_df.columns:
        pop_df["conviction"] = pop_df["conviction"].apply(
            lambda x: str(x).title() if pd.notna(x) else "—"
        )

    # Add predictor inference column
    if predictions_data:
        def _veto_label(ticker):
            pred = predictions_data.get(ticker, {})
            if pred.get("gbm_veto"):
                direction = pred.get("predicted_direction", "Down")
                return f"Vetoed: {direction.title()}"
            return "—"
        pop_df["Predictor Inference"] = pop_df["ticker"].apply(_veto_label)
    else:
        pop_df["Predictor Inference"] = "—"

    # Add risk guard column
    if order_book_summary:
        approved_tickers = {a["ticker"] for a in order_book_summary.get("entries_approved", [])}
        blocked_map = {b["ticker"]: b["reason"] for b in order_book_summary.get("entries_blocked", [])}

        def _risk_guard_label(ticker):
            if ticker in approved_tickers:
                return "Approved"
            if ticker in blocked_map:
                reason = blocked_map[ticker]
                # Clean up technical reason strings for display
                reason = reason.replace("Conviction '", "").replace("' not in allowed set", "")
                reason = reason.replace("('rising', 'stable')", "").strip()
                return f"Blocked: {reason.title()}" if reason else "Blocked"
            return "—"
        pop_df["Risk Guard"] = pop_df["ticker"].apply(_risk_guard_label)
    else:
        pop_df["Risk Guard"] = "—"

    # Add order book column
    if order_book_summary:
        ob_entries = {a["ticker"] for a in order_book_summary.get("entries_approved", [])}
        ob_exits = {e["ticker"] for e in order_book_summary.get("exits", [])}
        ob_covers = {c["ticker"] for c in order_book_summary.get("covers", [])}

        def _order_book_label(ticker):
            if ticker in ob_entries:
                return "Enter"
            if ticker in ob_exits:
                return "Exit"
            if ticker in ob_covers:
                return "Cover"
            return "—"
        pop_df["Order Book"] = pop_df["ticker"].apply(_order_book_label)
    else:
        pop_df["Order Book"] = "—"

    # Rename columns for display
    col_rename = {
        "ticker": "Ticker",
        "sector": "Sector",
        "conviction": "Research Conviction",
        "entry_date": "Entry Date",
    }
    display_cols = [c for c in [
        "ticker", "sector", "conviction", "entry_date", "Predictor Inference", "Risk Guard", "Order Book",
    ] if c in pop_df.columns]

    if display_cols:
        display_df = pop_df[display_cols].sort_values("sector").rename(columns=col_rename)
        st.dataframe(display_df, width="stretch", hide_index=True)
else:
    st.info("Population data not available. Research pipeline may not have run yet.")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

render_footer()
