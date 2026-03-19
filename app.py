"""
Alpha Engine Dashboard — Home / System Status page.
Entry point for the Streamlit multi-page app.
"""

import sys
import os
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

# Ensure project root is on sys.path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loaders.s3_loader import (
    load_config,
    load_eod_pnl,
    load_signals_json,
    load_trades_full,
    load_predictor_metrics,
    load_predictor_params,
    load_predictions_json,
    check_key_exists,
    get_recent_s3_errors,
)
from loaders.signal_loader import (
    get_available_signal_dates,
    signals_to_df,
    get_buy_candidates_df,
    get_signal_counts,
)
from loaders.db_loader import get_macro_snapshots

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Alpha Engine Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SIGNAL_COLORS = {
    "ENTER": "#d4edda",
    "EXIT": "#f8d7da",
    "REDUCE": "#fff3cd",
    "HOLD": "#f8f9fa",
}

SIGNAL_TEXT_COLORS = {
    "ENTER": "#155724",
    "EXIT": "#721c24",
    "REDUCE": "#856404",
    "HOLD": "#495057",
}

SIGNAL_BADGES = {
    "ENTER": "🟢",
    "EXIT": "🔴",
    "REDUCE": "🟡",
    "HOLD": "⚪",
}

VETO_COLOR = "#f5c6cb"


def _status_badge(ok: bool | None) -> str:
    if ok is True:
        return "🟢"
    elif ok is False:
        return "🔴"
    return "🟡"


def _color_signal_row(row: pd.Series) -> list[str]:
    """Return background-color CSS for each cell in a row based on signal type."""
    veto_val = str(row.get("Veto", ""))
    if veto_val.startswith("VETOED"):
        return [f"background-color: {VETO_COLOR}" for _ in row]
    sig = str(row.get("signal", "HOLD")).upper()
    color = SIGNAL_COLORS.get(sig, SIGNAL_COLORS["HOLD"])
    return [f"background-color: {color}" for _ in row]


def _fmt_pct(val, decimals=2) -> str:
    try:
        return f"{float(val):+.{decimals}f}%"
    except Exception:
        return "—"


def _fmt_dollar(val) -> str:
    try:
        return f"${float(val):,.2f}"
    except Exception:
        return "—"


def _is_weekend_gap(today_dt: date, last_date: date) -> bool:
    """Return True if the gap between today and last_date is just a weekend."""
    # If today is Monday and last_date is Friday, that's a normal weekend gap
    if today_dt.weekday() == 0 and last_date.weekday() == 4:
        return (today_dt - last_date).days <= 3
    return False


# ---------------------------------------------------------------------------
# System Health checks
# ---------------------------------------------------------------------------


def _check_research_lambda() -> tuple[bool | None, str]:
    """
    Check if today's signals.json was written (proxy for Research Lambda health).
    48-hour escalation: yellow after 1 day, red after 2 days.
    """
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("America/Los_Angeles"))
    today_dt = now.date()
    cfg = load_config()
    bucket = cfg["s3"]["research_bucket"]

    # Check today
    key_today = cfg["paths"]["signals"].format(date=today_dt.isoformat())
    if check_key_exists(bucket, key_today):
        return True, "Signals written today"

    # Before 7 AM PT, yesterday is acceptable
    if now.hour < 7:
        yesterday = today_dt - timedelta(days=1)
        key_yday = cfg["paths"]["signals"].format(date=yesterday.isoformat())
        if check_key_exists(bucket, key_yday):
            return True, "Yesterday's signals (pre-market)"

    # Check yesterday
    yesterday = today_dt - timedelta(days=1)
    key_yday = cfg["paths"]["signals"].format(date=yesterday.isoformat())
    if check_key_exists(bucket, key_yday):
        return None, "Yesterday's signals present (today missing)"

    # Check two days ago
    two_days = today_dt - timedelta(days=2)
    key_2d = cfg["paths"]["signals"].format(date=two_days.isoformat())
    if check_key_exists(bucket, key_2d):
        # Check weekend: Friday signals on Sunday is fine
        if _is_weekend_gap(today_dt, two_days):
            return None, f"Last signals: {two_days.isoformat()} (weekend)"
        return False, "No signals for 48+ hours"

    return False, "No recent signals found"


def _check_ib_gateway(eod_df: pd.DataFrame | None, trades_df: pd.DataFrame | None = None,
                       signals_data: dict | None = None) -> tuple[bool | None, str]:
    """
    Check IB Gateway health via presence of today's eod_pnl entry.
    48-hour escalation with weekend awareness. Detects executor failures.
    """
    if eod_df is None or eod_df.empty:
        return False, "No eod_pnl data"
    if "date" not in eod_df.columns:
        return False, "No date column in eod_pnl"

    eod_df = eod_df.copy()
    eod_df["date"] = pd.to_datetime(eod_df["date"])
    today_dt = date.today()

    today_rows = eod_df[eod_df["date"].dt.date == today_dt]
    if not today_rows.empty:
        # Check for executor failure: P&L recorded but no trades when signals have ENTER candidates
        if trades_df is not None and not trades_df.empty and signals_data:
            from loaders.signal_loader import signals_to_df
            sig_df = signals_to_df(signals_data)
            has_enter = not sig_df.empty and "signal" in sig_df.columns and (sig_df["signal"] == "ENTER").any()
            if has_enter and "date" in trades_df.columns:
                trades_today = trades_df[pd.to_datetime(trades_df["date"]).dt.date == today_dt]
                if trades_today.empty:
                    return None, "P&L recorded but no trades executed"
        return True, "Today's P&L recorded"

    # Check yesterday
    yesterday = today_dt - timedelta(days=1)
    yday_rows = eod_df[eod_df["date"].dt.date == yesterday]
    if not yday_rows.empty:
        return None, "Last updated yesterday"

    # Check two days ago with weekend awareness
    two_days = today_dt - timedelta(days=2)
    twoday_rows = eod_df[eod_df["date"].dt.date == two_days]
    if not twoday_rows.empty:
        if _is_weekend_gap(today_dt, two_days):
            return None, f"Last P&L: {two_days.isoformat()} (weekend)"
        return False, "No P&L for 48+ hours"

    return False, "No recent P&L data"


def _check_backtester() -> tuple[bool | None, str]:
    """
    Check if a backtest was run recently (within 7 days).
    Also checks metrics.json for failure status.
    """
    from loaders.s3_loader import list_backtest_dates, load_backtest_file
    dates = list_backtest_dates()
    if not dates:
        return None, "No backtests found"
    latest = dates[0]

    # Check for failure status in metrics.json
    metrics = load_backtest_file(latest, "metrics.json")
    if isinstance(metrics, dict):
        status = metrics.get("status", "")
        if status in ("failed", "error"):
            return False, f"Last run FAILED: {latest}"

    try:
        delta = (pd.Timestamp.now() - pd.Timestamp(latest)).days
        if delta <= 7:
            return True, f"Last run: {latest}"
        elif delta <= 30:
            return None, f"Last run: {latest} ({delta}d ago)"
        return False, f"Stale — {latest} ({delta}d ago)"
    except Exception:
        return None, f"Last: {latest}"


def _check_predictor(metrics: dict) -> tuple[bool | None, str]:
    """Check predictor health via metrics/latest.json hit rate and freshness."""
    if not metrics:
        return False, "No metrics found"
    from zoneinfo import ZoneInfo
    today = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d")
    last_run = metrics.get("last_run_utc", "")[:10]
    hit_rate = metrics.get("hit_rate_30d_rolling")
    if last_run != today:
        return False, f"Not run today (last: {last_run or 'unknown'})"
    if hit_rate is None:
        return None, "Hit rate not yet available (need 30+ days)"
    if hit_rate >= 0.52:
        return True, f"Hit rate {hit_rate:.1%}"
    elif hit_rate >= 0.48:
        return None, f"Hit rate {hit_rate:.1%} (degraded)"
    return False, f"Hit rate {hit_rate:.1%} (below threshold)"


def _check_signal_quality(signals_data: dict | None) -> tuple[bool | None, str]:
    """
    Check signal quality via stale flag count in today's signals.
    """
    if not signals_data:
        return False, "Signals not available"
    df = signals_to_df(signals_data)
    if df.empty:
        return None, "Empty signal universe"
    total = len(df)
    stale = int(df["stale"].sum()) if "stale" in df.columns else 0
    stale_pct = stale / total * 100 if total > 0 else 0
    if stale_pct < 10:
        return True, f"{total} signals, {stale} stale ({stale_pct:.0f}%)"
    elif stale_pct < 30:
        return None, f"{total} signals, {stale} stale ({stale_pct:.0f}%)"
    return False, f"{total} signals, {stale} stale ({stale_pct:.0f}%) — HIGH"


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------


def main():
    st.title("📈 Alpha Engine Dashboard")
    st.caption(f"As of {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')} UTC")

    # ---- Load data ----
    today = date.today().isoformat()

    with st.spinner("Loading data..."):
        eod_df = load_eod_pnl()
        trades_df = load_trades_full()
        signals_data = load_signals_json(today)
        macro_df = get_macro_snapshots()
        predictor_metrics = load_predictor_metrics()

    # -----------------------------------------------------------------------
    # Section 1: System Health
    # -----------------------------------------------------------------------
    st.header("System Health")

    lambda_ok, lambda_msg = _check_research_lambda()
    ib_ok, ib_msg = _check_ib_gateway(eod_df, trades_df, signals_data)
    bt_ok, bt_msg = _check_backtester()
    sq_ok, sq_msg = _check_signal_quality(signals_data)
    pred_ok, pred_msg = _check_predictor(predictor_metrics)

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        badge = _status_badge(lambda_ok)
        st.metric(label=f"{badge} Research Lambda", value=lambda_msg)

    with col2:
        badge = _status_badge(ib_ok)
        st.metric(label=f"{badge} IB Gateway", value=ib_msg)

    with col3:
        badge = _status_badge(bt_ok)
        st.metric(label=f"{badge} Backtester", value=bt_msg)

    with col4:
        badge = _status_badge(sq_ok)
        st.metric(label=f"{badge} Signal Quality", value=sq_msg)

    with col5:
        badge = _status_badge(pred_ok)
        st.metric(label=f"{badge} Predictor", value=pred_msg)

    # S3 error display (Gap #13)
    s3_errors = get_recent_s3_errors()
    if s3_errors:
        recent_cutoff = (datetime.utcnow() - timedelta(minutes=15)).isoformat()
        recent_errors = [e for e in s3_errors if e["timestamp"] >= recent_cutoff]

        if recent_errors:
            st.error(f"{len(recent_errors)} S3 errors in the last 15 minutes")

        with st.expander(f"S3 Errors ({len(s3_errors)} total)", expanded=bool(recent_errors)):
            error_df = pd.DataFrame(s3_errors[-20:])  # Show last 20
            st.dataframe(error_df, use_container_width=True, hide_index=True)

    st.divider()

    # -----------------------------------------------------------------------
    # Section 2: Today's Snapshot
    # -----------------------------------------------------------------------
    st.header("Today's Snapshot")

    nav = daily_ret_norm = spy_ret_norm = alpha_norm = None

    if eod_df is None or eod_df.empty:
        st.warning("Portfolio data not available yet.")
        today_row = None
    else:
        eod_df["date"] = pd.to_datetime(eod_df["date"])
        today_rows = eod_df[eod_df["date"].dt.date == date.today()]
        today_row = today_rows.iloc[-1] if not today_rows.empty else eod_df.iloc[-1]

        nav = today_row.get("portfolio_nav")
        daily_ret = today_row.get("daily_return_pct")
        spy_ret = today_row.get("spy_return_pct")
        alpha = today_row.get("daily_alpha_pct")

        # Detect percent vs decimal
        def _norm(v):
            try:
                v = float(v)
                return v / 100 if abs(v) > 2 else v
            except Exception:
                return None

        daily_ret_norm = _norm(daily_ret)
        spy_ret_norm = _norm(spy_ret)
        alpha_norm = _norm(alpha)

    signal_counts = get_signal_counts(signals_data) if signals_data else {}
    total_signals = sum(signal_counts.values())
    signal_summary = (
        f"ENTER: {signal_counts.get('ENTER', 0)} | EXIT: {signal_counts.get('EXIT', 0)} | "
        f"HOLD: {signal_counts.get('HOLD', 0)}"
    )

    snap_col1, snap_col2, snap_col3, snap_col4 = st.columns(4)

    with snap_col1:
        st.metric(
            "Portfolio NAV",
            _fmt_dollar(nav) if nav is not None else "—",
        )

    with snap_col2:
        if daily_ret_norm is not None:
            st.metric(
                "Daily Return",
                f"{daily_ret_norm * 100:+.2f}%",
            )
        else:
            st.metric("Daily Return", "—")

    with snap_col3:
        if alpha_norm is not None:
            st.metric(
                "vs SPY (Alpha)",
                f"{alpha_norm * 100:+.2f}%",
            )
        else:
            st.metric("vs SPY (Alpha)", "—")

    with snap_col4:
        st.metric("Signal Count", f"{total_signals}", delta=signal_summary)

    st.divider()

    # -----------------------------------------------------------------------
    # Section 3: Today's Signals (with veto status — Gap #2)
    # -----------------------------------------------------------------------
    st.header("Today's Signals")

    if not signals_data:
        st.warning("Signals not available for today. Check Research Lambda status.")
    else:
        buy_df = get_buy_candidates_df(signals_data)

        if buy_df.empty:
            st.info("No buy candidates in today's signals.")
        else:
            buy_df = buy_df.sort_values("score", ascending=False).reset_index(drop=True)

            # Format stale flag
            if "stale" in buy_df.columns:
                buy_df["stale"] = buy_df["stale"].apply(lambda x: "⚠" if x else "")

            # Add veto status
            predictions = load_predictions_json()
            predictor_params = load_predictor_params()
            veto_threshold = predictor_params.get("veto_confidence", 0.65)

            if predictions and "ticker" in buy_df.columns:
                def _veto_status(ticker):
                    pred = predictions.get(ticker, {})
                    if not pred:
                        return ""
                    direction = pred.get("predicted_direction", "")
                    conf = pred.get("prediction_confidence") or 0.0
                    if direction == "DOWN" and conf >= veto_threshold:
                        return f"VETOED ({conf:.0%})"
                    return ""

                buy_df["Veto"] = buy_df["ticker"].apply(_veto_status)

                vetoed_count = buy_df["Veto"].str.startswith("VETOED").sum()
                if vetoed_count > 0:
                    st.warning(f"{vetoed_count} of {len(buy_df)} buy candidates vetoed by predictor")

            # Select display columns
            display_cols = [
                c for c in [
                    "ticker", "sector", "signal", "score", "conviction",
                    "rating", "technical", "news", "research",
                    "Veto", "price_target_upside", "thesis_summary", "stale"
                ]
                if c in buy_df.columns
            ]
            display_df = buy_df[display_cols].copy()

            # Apply signal color styling
            styled = display_df.style.apply(_color_signal_row, axis=1)

            # Format numeric columns
            for col in ["score", "conviction", "technical", "news", "research"]:
                if col in display_df.columns:
                    styled = styled.format({col: "{:.1f}"}, na_rep="—")
            if "price_target_upside" in display_df.columns:
                styled = styled.format({"price_target_upside": "{:.1%}"}, na_rep="—")

            st.dataframe(styled, use_container_width=True, hide_index=True)

    st.divider()

    # -----------------------------------------------------------------------
    # Section 4: Market Context
    # -----------------------------------------------------------------------
    st.header("Market Context")

    if macro_df is None or macro_df.empty:
        st.warning("Macro data not available.")
    else:
        macro_df["date"] = pd.to_datetime(macro_df["date"])
        today_macro = macro_df[macro_df["date"].dt.date == date.today()]

        if today_macro.empty:
            # Use most recent available
            today_macro = macro_df.tail(1)

        if today_macro.empty:
            st.info("No macro snapshot for today.")
        else:
            row = today_macro.iloc[-1]
            regime = row.get("market_regime", row.get("regime", "—"))
            vix = row.get("vix", "—")
            yield_10yr = row.get("yield_10yr", row.get("10yr_yield", "—"))

            mc1, mc2, mc3 = st.columns(3)
            with mc1:
                regime_emoji = {"bull": "🐂", "bear": "🐻", "neutral": "➡️", "caution": "⚠️"}.get(
                    str(regime).lower(), "📊"
                )
                st.metric("Regime", f"{regime_emoji} {str(regime).title()}")
            with mc2:
                try:
                    st.metric("VIX", f"{float(vix):.1f}")
                except Exception:
                    st.metric("VIX", str(vix))
            with mc3:
                try:
                    st.metric("10yr Yield", f"{float(yield_10yr):.2f}%")
                except Exception:
                    st.metric("10yr Yield", str(yield_10yr))


if __name__ == "__main__":
    main()
else:
    main()
