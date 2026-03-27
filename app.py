"""
Alpha Engine Dashboard — Public Home Page.
Entry point for the Streamlit multi-page app.

Layout (top to bottom):
  1. Pipeline Activity — research picks, predictor vetoes, risk guard blocks, market status
  2. Current Holdings — NAV, per-position detail with P&L
  3. Alpha Performance — cumulative alpha chart, summary stats, market context
"""

import json
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
    load_population_json,
    load_order_book_summary,
)
from loaders.signal_loader import (
    signals_to_df,
    get_signal_counts,
)
from loaders.db_loader import get_macro_snapshots

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Alpha Engine — Nous Ergon",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _is_market_open() -> bool:
    """Return True if US market is currently open (9:30 AM - 4:00 PM ET, weekdays)."""
    from zoneinfo import ZoneInfo
    now_et = datetime.now(ZoneInfo("US/Eastern"))
    if now_et.weekday() >= 5:  # weekend
        return False
    market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now_et <= market_close


def _most_recent_trading_date(trades_df: pd.DataFrame | None) -> str | None:
    """Return the most recent date with trades, or None."""
    if trades_df is None or trades_df.empty or "date" not in trades_df.columns:
        return None
    dates = pd.to_datetime(trades_df["date"]).dt.date.unique()
    return str(max(dates)) if len(dates) > 0 else None


def _safe_column(df: pd.DataFrame, *candidates: str) -> str | None:
    """Return the first column name that exists in df."""
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _color_return(val):
    try:
        v = float(val)
        if v > 0:
            return "color: #155724; background-color: #d4edda"
        elif v < 0:
            return "color: #721c24; background-color: #f8d7da"
    except (ValueError, TypeError):
        pass
    return ""


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------


def main():
    st.title("📈 Alpha Engine")
    st.caption("Autonomous equity portfolio — LLM research + GBM predictions + quantitative execution")

    # ---- Load data ----
    today = date.today().isoformat()

    with st.spinner("Loading data..."):
        eod_df = load_eod_pnl()
        trades_df = load_trades_full()
        signals_data = load_signals_json(today)
        macro_df = get_macro_snapshots()
        population_data = load_population_json()
        predictions_data = load_predictions_json()
        order_book_summary = load_order_book_summary(today)

    # ===================================================================
    # Section 1: Pipeline Activity
    # ===================================================================
    st.header("Pipeline Activity")

    # --- 1a. Research Picks (Weekly) ---
    st.subheader("Research Population (Weekly)")
    if population_data and population_data.get("population"):
        pop = population_data["population"]
        pop_date = population_data.get("date", "unknown")
        regime = population_data.get("market_regime", "unknown")

        regime_emoji = {"bull": "🐂", "bear": "🐻", "neutral": "➡️", "caution": "⚠️"}.get(
            str(regime).lower(), "📊"
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Market Regime", f"{regime_emoji} {str(regime).title()}")
        with c2:
            st.metric("Universe Size", str(len(pop)))
        with c3:
            st.metric("Last Refreshed", pop_date)

        pop_df = pd.DataFrame(pop)
        # Show tickers grouped by sector with entry date
        display_cols = [c for c in ["ticker", "sector", "long_term_rating", "conviction", "entry_date"]
                        if c in pop_df.columns]
        if display_cols:
            pop_display = pop_df[display_cols].sort_values("sector")
            st.dataframe(pop_display, use_container_width=True, hide_index=True)
    else:
        st.info("Population data not available. Research pipeline may not have run yet.")

    # --- 1b. Predictor Vetoes (Daily) ---
    st.subheader("Predictor Vetoes (Daily)")
    if predictions_data:
        pred_list = list(predictions_data.values())
        # Filter to population tickers if available
        if population_data and population_data.get("population"):
            pop_tickers = {p["ticker"] for p in population_data["population"]}
            pred_list = [p for p in pred_list if p.get("ticker") in pop_tickers]

        vetoed = [p for p in pred_list if p.get("gbm_veto")]
        if vetoed:
            veto_df = pd.DataFrame(vetoed)[["ticker", "predicted_alpha", "combined_rank"]]
            veto_df["predicted_alpha"] = veto_df["predicted_alpha"].apply(
                lambda x: f"{x*100:+.2f}%" if pd.notna(x) else "—"
            )
            veto_df.columns = ["Ticker", "Predicted Alpha", "Rank"]
            st.warning(f"{len(vetoed)} ticker(s) vetoed — negative predicted alpha + bottom-half rank")
            st.dataframe(veto_df, use_container_width=True, hide_index=True)
        else:
            n_preds = len(pred_list)
            st.success(f"No vetoes today ({n_preds} tickers predicted)")
    else:
        st.info("Predictor data not available for today.")

    # --- 1c. Risk Guard Blocks (Daily) ---
    st.subheader("Risk Guard (Daily)")
    if order_book_summary:
        approved = order_book_summary.get("entries_approved", [])
        blocked = order_book_summary.get("entries_blocked", [])
        exits = order_book_summary.get("exits", [])
        covers = order_book_summary.get("covers", [])

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Approved", str(len(approved)))
        with c2:
            st.metric("Blocked", str(len(blocked)))
        with c3:
            st.metric("Exits", str(len(exits)))
        with c4:
            st.metric("Covers", str(len(covers)))

        if approved:
            st.success("Approved entries: " + ", ".join(a["ticker"] for a in approved))
        if blocked:
            blocked_df = pd.DataFrame(blocked)
            blocked_df.columns = ["Ticker", "Reason"]
            st.dataframe(blocked_df, use_container_width=True, hide_index=True)
        if covers:
            st.warning("Short covers: " + ", ".join(c["ticker"] for c in covers))
    else:
        st.info("Order book summary not available for today.")

    # --- 1d. Market Status / Trades ---
    st.subheader("Trades" if not _is_market_open() else "Order Book (Market Open)")
    if trades_df is not None and not trades_df.empty and "date" in trades_df.columns:
        trades_df_copy = trades_df.copy()
        trades_df_copy["date"] = pd.to_datetime(trades_df_copy["date"]).dt.date

        if _is_market_open():
            # Show today's order book entries
            if order_book_summary:
                approved = order_book_summary.get("entries_approved", [])
                if approved:
                    st.info("Pending entries: " + ", ".join(a["ticker"] for a in approved))
                else:
                    st.info("No pending entries in order book")
            else:
                st.info("No order book data available")
        else:
            # Show most recent trading day's buys/sells
            recent_date = _most_recent_trading_date(trades_df)
            if recent_date:
                recent_trades = trades_df_copy[trades_df_copy["date"] == date.fromisoformat(recent_date)]
                if not recent_trades.empty:
                    action_col = _safe_column(recent_trades, "action", "signal")
                    display_cols = ["ticker"]
                    if action_col:
                        display_cols.append(action_col)
                    st.caption(f"Trades from {recent_date}")
                    st.dataframe(
                        recent_trades[display_cols].reset_index(drop=True),
                        use_container_width=True, hide_index=True,
                    )
                else:
                    st.info("No recent trades.")
            else:
                st.info("No trade history available.")
    else:
        st.info("Trade data not available.")

    st.divider()

    # ===================================================================
    # Section 2: Current Holdings
    # ===================================================================
    st.header("Current Holdings")

    # Portfolio NAV
    nav = None
    daily_ret_norm = alpha_norm = None
    if eod_df is not None and not eod_df.empty:
        eod_df_copy = eod_df.copy()
        eod_df_copy["date"] = pd.to_datetime(eod_df_copy["date"])
        today_rows = eod_df_copy[eod_df_copy["date"].dt.date == date.today()]
        latest_row = today_rows.iloc[-1] if not today_rows.empty else eod_df_copy.iloc[-1]

        nav = latest_row.get("portfolio_nav")

        def _norm(v):
            try:
                v = float(v)
                return v / 100 if abs(v) > 2 else v
            except Exception:
                return None

        daily_ret_norm = _norm(latest_row.get("daily_return_pct"))
        alpha_norm = _norm(latest_row.get("daily_alpha_pct"))

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Portfolio NAV", _fmt_dollar(nav) if nav else "—")
        with c2:
            st.metric("Daily Return", f"{daily_ret_norm*100:+.2f}%" if daily_ret_norm is not None else "—")
        with c3:
            st.metric("Daily Alpha vs SPY", f"{alpha_norm*100:+.2f}%" if alpha_norm is not None else "—")

    # Positions table
    positions_df = None
    if eod_df is not None and not eod_df.empty and "positions_snapshot" in eod_df.columns:
        eod_df_copy = eod_df.copy()
        eod_df_copy["date"] = pd.to_datetime(eod_df_copy["date"])
        latest_row = eod_df_copy.iloc[-1]
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
        # Merge with signals for score/conviction
        if signals_data:
            sig_df = signals_to_df(signals_data)
            if not sig_df.empty and "ticker" in sig_df.columns and "ticker" in positions_df.columns:
                positions_df = positions_df.merge(
                    sig_df[["ticker", "score", "signal", "conviction"]],
                    on="ticker", how="left", suffixes=("", "_signal"),
                )

        # Merge with trades for entry_price and entry_date
        if trades_df is not None and not trades_df.empty:
            action_col = _safe_column(trades_df, "action", "signal")
            if action_col:
                enter_trades = trades_df[trades_df[action_col].str.upper() == "ENTER"].copy()
                if not enter_trades.empty and "ticker" in enter_trades.columns and "ticker" in positions_df.columns:
                    if "date" in enter_trades.columns:
                        enter_trades["date"] = pd.to_datetime(enter_trades["date"])
                        latest_entry = enter_trades.sort_values("date").groupby("ticker").last().reset_index()
                        price_col = _safe_column(latest_entry, "price", "fill_price", "price_at_order")
                        if price_col:
                            positions_df = positions_df.merge(
                                latest_entry[["ticker", price_col, "date"]].rename(
                                    columns={price_col: "entry_price", "date": "entry_date"}
                                ),
                                on="ticker", how="left",
                            )

        # Compute P&L
        if "market_value" in positions_df.columns and "shares" in positions_df.columns:
            positions_df["shares"] = pd.to_numeric(positions_df["shares"], errors="coerce")
            positions_df["market_value"] = pd.to_numeric(positions_df["market_value"], errors="coerce")
            positions_df["current_price"] = positions_df["market_value"] / positions_df["shares"]

            if "entry_price" in positions_df.columns:
                positions_df["entry_price"] = pd.to_numeric(positions_df["entry_price"], errors="coerce")
                positions_df["unrealized_pnl"] = (
                    (positions_df["current_price"] - positions_df["entry_price"]) * positions_df["shares"]
                )
                positions_df["return_pct"] = positions_df["current_price"] / positions_df["entry_price"] - 1

            if "entry_date" in positions_df.columns:
                positions_df["days_held"] = (
                    pd.Timestamp.now() - pd.to_datetime(positions_df["entry_date"])
                ).dt.days

        # P&L summary
        if "unrealized_pnl" in positions_df.columns:
            total_pnl = positions_df["unrealized_pnl"].sum()
            pos_count = len(positions_df)
            avg_days = positions_df["days_held"].mean() if "days_held" in positions_df.columns else None

            pc1, pc2, pc3 = st.columns(3)
            with pc1:
                st.metric("Total Unrealized P&L", _fmt_dollar(total_pnl))
            with pc2:
                st.metric("Positions", str(pos_count))
            with pc3:
                st.metric("Avg Days Held", f"{avg_days:.0f}" if avg_days is not None else "—")

        # Positions table
        display_cols = [
            c for c in [
                "ticker", "sector", "shares", "entry_price", "current_price",
                "unrealized_pnl", "return_pct", "days_held", "score", "signal",
            ]
            if c in positions_df.columns
        ]

        if display_cols:
            display_pos = positions_df[display_cols].copy()
            styled = display_pos.style
            if "return_pct" in display_pos.columns:
                styled = styled.map(_color_return, subset=["return_pct"])
                styled = styled.format({"return_pct": "{:.1%}"}, na_rep="—")
            if "unrealized_pnl" in display_pos.columns:
                styled = styled.format({"unrealized_pnl": "${:,.2f}"}, na_rep="—")
            if "entry_price" in display_pos.columns:
                styled = styled.format({"entry_price": "${:.2f}"}, na_rep="—")
            if "current_price" in display_pos.columns:
                styled = styled.format({"current_price": "${:.2f}"}, na_rep="—")
            if "score" in display_pos.columns:
                styled = styled.format({"score": "{:.1f}"}, na_rep="—")
            st.dataframe(styled, use_container_width=True, hide_index=True)
    else:
        st.info("No positions data available.")

    st.divider()

    # ===================================================================
    # Section 3: Alpha Performance + Market Context
    # ===================================================================
    st.header("Performance")

    if eod_df is not None and not eod_df.empty:
        try:
            from charts.alpha_chart import make_alpha_chart
            alpha_fig = make_alpha_chart(eod_df)
            st.plotly_chart(alpha_fig, use_container_width=True)
        except Exception:
            st.info("Alpha chart not available.")

        # Summary stats
        eod_copy = eod_df.copy()
        eod_copy["date"] = pd.to_datetime(eod_copy["date"])

        if "daily_return_pct" in eod_copy.columns and "daily_alpha_pct" in eod_copy.columns:
            returns = pd.to_numeric(eod_copy["daily_return_pct"], errors="coerce").dropna()
            alphas = pd.to_numeric(eod_copy["daily_alpha_pct"], errors="coerce").dropna()

            # Normalize if stored as percent
            if returns.abs().max() > 2:
                returns = returns / 100
            if alphas.abs().max() > 2:
                alphas = alphas / 100

            cumulative_ret = (1 + returns).prod() - 1
            sharpe = (returns.mean() / returns.std() * (252 ** 0.5)) if len(returns) >= 30 and returns.std() > 0 else None
            max_dd = (returns.cumsum() - returns.cumsum().cummax()).min()

            sc1, sc2, sc3, sc4 = st.columns(4)
            with sc1:
                st.metric("Total Return", f"{cumulative_ret*100:+.1f}%" if pd.notna(cumulative_ret) else "—")
            with sc2:
                st.metric("Sharpe Ratio", f"{sharpe:.2f}" if sharpe is not None else "—")
            with sc3:
                st.metric("Max Drawdown", f"{max_dd*100:.1f}%" if pd.notna(max_dd) else "—")
            with sc4:
                st.metric("Cumulative Alpha", f"{alphas.sum()*100:+.1f}%" if not alphas.empty else "—")
    else:
        st.info("Performance data not available.")

    # Market Context
    st.subheader("Market Context")
    if macro_df is not None and not macro_df.empty:
        macro_df_copy = macro_df.copy()
        macro_df_copy["date"] = pd.to_datetime(macro_df_copy["date"])
        today_macro = macro_df_copy[macro_df_copy["date"].dt.date == date.today()]
        if today_macro.empty:
            today_macro = macro_df_copy.tail(1)

        if not today_macro.empty:
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
    else:
        st.info("Macro data not available.")


if __name__ == "__main__":
    main()
else:
    main()
