"""
Signals page — Full signal universe table with filters, ticker detail, sector ratings.
"""

import sys
import os
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loaders.signal_loader import (
    get_available_signal_dates,
    load_signals,
    signals_to_df,
    get_sector_ratings_df,
)
from loaders.db_loader import get_macro_snapshots, get_score_history, get_score_performance

st.set_page_config(page_title="Signals — Alpha Engine", layout="wide")

# ---------------------------------------------------------------------------
# Color coding
# ---------------------------------------------------------------------------

SIGNAL_COLORS = {
    "ENTER": "#d4edda",
    "EXIT": "#f8d7da",
    "REDUCE": "#fff3cd",
    "HOLD": "#f8f9fa",
}


def _color_signal_row(row: pd.Series) -> list[str]:
    sig = str(row.get("signal", "HOLD")).upper()
    color = SIGNAL_COLORS.get(sig, SIGNAL_COLORS["HOLD"])
    return [f"background-color: {color}" for _ in row]


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

st.title("Signal Universe")

# ---- Date selector ----
available_dates = get_available_signal_dates()
today_str = date.today().isoformat()

if not available_dates:
    st.warning("No signal dates available in S3.")
    st.stop()

default_idx = 0
if today_str in available_dates:
    default_idx = available_dates.index(today_str)

selected_date = st.selectbox(
    "Select Signal Date",
    options=available_dates,
    index=default_idx,
    help="Pick the date whose signals.json to view",
)

# ---- Load signals ----
with st.spinner(f"Loading signals for {selected_date}..."):
    signals_data = load_signals(selected_date)

if not signals_data:
    st.warning(f"No signals available for {selected_date}.")
    st.stop()

# ---- Market regime chip row ----
macro_df = get_macro_snapshots()
if macro_df is not None and not macro_df.empty:
    macro_df["date"] = pd.to_datetime(macro_df["date"])
    day_macro = macro_df[macro_df["date"].dt.strftime("%Y-%m-%d") == selected_date]
    if day_macro.empty:
        # fallback: use most recent before selected_date
        past = macro_df[macro_df["date"].dt.strftime("%Y-%m-%d") <= selected_date]
        day_macro = past.tail(1)
    if not day_macro.empty:
        macro_row = day_macro.iloc[-1]
        regime = macro_row.get("regime", "—")
        vix = macro_row.get("vix", "—")
        yield_10yr = macro_row.get("yield_10yr", macro_row.get("10yr_yield", "—"))
        regime_emoji = {"bull": "🐂", "bear": "🐻", "neutral": "➡️", "caution": "⚠️"}.get(
            str(regime).lower(), "📊"
        )
        mc1, mc2, mc3, mc4 = st.columns(4)
        with mc1:
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
        with mc4:
            universe = signals_data.get("universe", [])
            st.metric("Universe Size", str(len(universe)))

st.divider()

# ---- Build signal DataFrame ----
sig_df = signals_to_df(signals_data)

if sig_df.empty:
    st.info("Signal universe is empty for this date.")
    st.stop()

# -----------------------------------------------------------------------
# Filters
# -----------------------------------------------------------------------
st.subheader("Filters")

filter_col1, filter_col2, filter_col3 = st.columns([2, 2, 2])

with filter_col1:
    sectors = sorted(sig_df["sector"].dropna().unique().tolist()) if "sector" in sig_df.columns else []
    selected_sectors = st.multiselect("Sector", options=sectors, default=[])

with filter_col2:
    signal_types = sorted(sig_df["signal"].dropna().unique().tolist()) if "signal" in sig_df.columns else []
    selected_signals = st.multiselect("Signal Type", options=signal_types, default=[])

with filter_col3:
    min_score = st.slider(
        "Min Score",
        min_value=0,
        max_value=100,
        value=0,
        step=5,
    )

# Apply filters
filtered_df = sig_df.copy()
if selected_sectors:
    filtered_df = filtered_df[filtered_df["sector"].isin(selected_sectors)]
if selected_signals:
    filtered_df = filtered_df[filtered_df["signal"].isin(selected_signals)]
if "score" in filtered_df.columns:
    filtered_df = filtered_df[pd.to_numeric(filtered_df["score"], errors="coerce").fillna(0) >= min_score]

filtered_df = filtered_df.sort_values("score", ascending=False).reset_index(drop=True)

# Format stale flag
if "stale" in filtered_df.columns:
    filtered_df["stale"] = filtered_df["stale"].apply(lambda x: "⚠" if x else "")

st.caption(f"Showing {len(filtered_df)} of {len(sig_df)} signals")

# -----------------------------------------------------------------------
# Main signal table
# -----------------------------------------------------------------------
st.subheader("Signal Table")

display_cols = [
    c for c in [
        "ticker", "sector", "signal", "score", "conviction",
        "rating", "technical", "news", "research",
        "price_target_upside", "stale", "thesis_summary"
    ]
    if c in filtered_df.columns
]
display_df = filtered_df[display_cols].copy()

styled = display_df.style.apply(_color_signal_row, axis=1)
for col in ["score", "conviction", "technical", "news", "research"]:
    if col in display_df.columns:
        styled = styled.format({col: "{:.1f}"}, na_rep="—")
if "price_target_upside" in display_df.columns:
    styled = styled.format({"price_target_upside": "{:.1%}"}, na_rep="—")

st.dataframe(styled, use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------
# Ticker Detail Expander
# -----------------------------------------------------------------------
st.subheader("Ticker Detail")

tickers = sorted(filtered_df["ticker"].dropna().unique().tolist()) if "ticker" in filtered_df.columns else []
selected_ticker = st.selectbox("Select ticker for detail view", options=[""] + tickers)

if selected_ticker:
    ticker_row = filtered_df[filtered_df["ticker"] == selected_ticker].iloc[0] if not filtered_df[filtered_df["ticker"] == selected_ticker].empty else None

    with st.expander(f"Detail: {selected_ticker}", expanded=True):
        if ticker_row is not None:
            # Thesis summary
            thesis = ticker_row.get("thesis_summary", "")
            if thesis:
                st.markdown(f"**Thesis Summary:** {thesis}")

            # Sub-score bar chart
            sub_scores = {}
            for s in ["technical", "news", "research"]:
                val = ticker_row.get(s)
                if pd.notna(val):
                    try:
                        sub_scores[s.capitalize()] = float(val)
                    except Exception:
                        pass

            if sub_scores:
                sub_fig = go.Figure(
                    go.Bar(
                        x=list(sub_scores.values()),
                        y=list(sub_scores.keys()),
                        orientation="h",
                        marker_color=["#1f77b4", "#ff7f0e", "#2ca02c"],
                        text=[f"{v:.1f}" for v in sub_scores.values()],
                        textposition="outside",
                    )
                )
                sub_fig.update_layout(
                    title=f"{selected_ticker} Sub-Score Breakdown",
                    xaxis=dict(title="Score", range=[0, 100]),
                    yaxis=dict(title=""),
                    plot_bgcolor="white",
                    paper_bgcolor="white",
                    height=200,
                    margin=dict(t=40, b=30, l=100, r=60),
                )
                st.plotly_chart(sub_fig, use_container_width=True)

            # 30-day score history from research DB
            score_hist = get_score_history(selected_ticker)
            if not score_hist.empty and "score_date" in score_hist.columns:
                score_hist["score_date"] = pd.to_datetime(score_hist["score_date"])
                score_hist = score_hist.sort_values("score_date")
                # Last 30 rows approx
                score_hist = score_hist.tail(30)

                hist_fig = go.Figure()
                if "composite_score" in score_hist.columns:
                    hist_fig.add_trace(
                        go.Scatter(
                            x=score_hist["score_date"],
                            y=score_hist["composite_score"],
                            mode="lines+markers",
                            name="Composite Score",
                            line=dict(color="#1f77b4", width=2.5),
                            hovertemplate="<b>%{x|%Y-%m-%d}</b><br>Score: %{y:.1f}<extra></extra>",
                        )
                    )
                hist_fig.update_layout(
                    title=f"{selected_ticker} 30-Day Score History",
                    xaxis=dict(title="Date"),
                    yaxis=dict(title="Score", range=[0, 100]),
                    plot_bgcolor="white",
                    paper_bgcolor="white",
                    height=250,
                    margin=dict(t=40, b=30, l=60, r=20),
                )
                st.plotly_chart(hist_fig, use_container_width=True)

                # Signal / performance history table
                perf_cols = [
                    c for c in ["score_date", "composite_score", "beat_spy_10d", "beat_spy_30d",
                                 "return_10d", "return_30d"]
                    if c in score_hist.columns
                ]
                if perf_cols:
                    perf_display = score_hist[perf_cols].copy()
                    for bool_col in ["beat_spy_10d", "beat_spy_30d"]:
                        if bool_col in perf_display.columns:
                            perf_display[bool_col] = perf_display[bool_col].map(
                                lambda x: "✅" if x == 1 or x is True else ("❌" if x == 0 or x is False else "⏳")
                            )
                    st.dataframe(perf_display, use_container_width=True, hide_index=True)
            else:
                st.info(f"No score history found for {selected_ticker} in research DB.")

# -----------------------------------------------------------------------
# Sector Ratings
# -----------------------------------------------------------------------
st.divider()
st.subheader("Sector Ratings")

sector_df = get_sector_ratings_df(signals_data)
if not sector_df.empty:
    st.dataframe(sector_df, use_container_width=True, hide_index=True)
else:
    st.info("No sector ratings in this signal file.")
