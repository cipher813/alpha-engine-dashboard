"""
Alpha Engine Dashboard — Home / System Status page.
Entry point for the Streamlit multi-page app.
"""

import sys
import os
from datetime import date

import pandas as pd
import streamlit as st

# Ensure project root is on sys.path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loaders.s3_loader import (
    load_config,
    load_eod_pnl,
    load_signals_json,
    load_trades_full,
    check_key_exists,
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


def _status_badge(ok: bool | None) -> str:
    if ok is True:
        return "🟢"
    elif ok is False:
        return "🔴"
    return "🟡"


def _color_signal_row(row: pd.Series) -> list[str]:
    """Return background-color CSS for each cell in a row based on signal type."""
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


# ---------------------------------------------------------------------------
# System Health checks
# ---------------------------------------------------------------------------


def _check_research_lambda() -> tuple[bool | None, str]:
    """
    Check if today's signals.json was written (proxy for Research Lambda health).
    """
    today = date.today().isoformat()
    cfg = load_config()
    key = cfg["paths"]["signals"].format(date=today)
    bucket = cfg["s3"]["research_bucket"]
    exists = check_key_exists(bucket, key)
    if exists:
        return True, "Signals written today"
    # Check yesterday
    yesterday = pd.Timestamp.now() - pd.Timedelta(days=1)
    key_yday = cfg["paths"]["signals"].format(date=yesterday.strftime("%Y-%m-%d"))
    exists_yday = check_key_exists(bucket, key_yday)
    if exists_yday:
        return None, "Yesterday's signals present (today missing)"
    return False, "No recent signals found"


def _check_ib_gateway(eod_df: pd.DataFrame | None) -> tuple[bool | None, str]:
    """
    Check IB Gateway health via presence of today's eod_pnl entry.
    """
    if eod_df is None or eod_df.empty:
        return False, "No eod_pnl data"
    if "date" in eod_df.columns:
        eod_df["date"] = pd.to_datetime(eod_df["date"])
        today_rows = eod_df[eod_df["date"].dt.date == date.today()]
        if not today_rows.empty:
            return True, "Today's P&L recorded"
        yesterday = (pd.Timestamp.now() - pd.Timedelta(days=1)).date()
        yday_rows = eod_df[eod_df["date"].dt.date == yesterday]
        if not yday_rows.empty:
            return None, "Last updated yesterday"
    return False, "No recent P&L data"


def _check_backtester() -> tuple[bool | None, str]:
    """
    Check if a backtest was run recently (within 7 days).
    """
    from loaders.s3_loader import list_backtest_dates
    dates = list_backtest_dates()
    if not dates:
        return None, "No backtests found"
    latest = dates[0]
    try:
        delta = (pd.Timestamp.now() - pd.Timestamp(latest)).days
        if delta <= 7:
            return True, f"Last run: {latest}"
        elif delta <= 30:
            return None, f"Last run: {latest} ({delta}d ago)"
        return False, f"Stale — {latest} ({delta}d ago)"
    except Exception:
        return None, f"Last: {latest}"


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
        signals_data = load_signals_json(today)
        macro_df = get_macro_snapshots()

    # -----------------------------------------------------------------------
    # Section 1: System Health
    # -----------------------------------------------------------------------
    st.header("System Health")

    lambda_ok, lambda_msg = _check_research_lambda()
    ib_ok, ib_msg = _check_ib_gateway(eod_df)
    bt_ok, bt_msg = _check_backtester()
    sq_ok, sq_msg = _check_signal_quality(signals_data)

    col1, col2, col3, col4 = st.columns(4)

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
    # Section 3: Today's Signals
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

            # Select display columns
            display_cols = [
                c for c in [
                    "ticker", "sector", "signal", "score", "conviction",
                    "rating", "technical", "news", "research",
                    "price_target_upside", "thesis_summary", "stale"
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
