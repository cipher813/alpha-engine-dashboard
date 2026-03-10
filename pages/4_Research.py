"""
Research page — Per-ticker score history, conviction, performance outcomes, thesis timeline.
"""

import sys
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loaders.db_loader import (
    get_distinct_symbols,
    get_score_history,
    get_investment_thesis,
    get_top_recent_symbols,
    query_research_db,
)

st.set_page_config(page_title="Research — Alpha Engine", layout="wide")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BEAT_ICONS = {1: "✅", 0: "❌", True: "✅", False: "❌"}


def _beat_icon(val) -> str:
    if pd.isna(val):
        return "⏳"
    try:
        return BEAT_ICONS.get(val, "⏳")
    except Exception:
        return "⏳"


def _score_history_chart(score_df: pd.DataFrame, ticker: str) -> go.Figure:
    """Composite score line + sub-score faint lines + signal markers."""
    fig = go.Figure()

    if "score_date" in score_df.columns:
        score_df = score_df.copy()
        score_df["score_date"] = pd.to_datetime(score_df["score_date"])

    # Sub-score faint lines
    sub_colors = {"technical": "#aec7e8", "news": "#ffbb78", "research": "#98df8a"}
    for col, color in sub_colors.items():
        if col in score_df.columns:
            fig.add_trace(
                go.Scatter(
                    x=score_df["score_date"],
                    y=pd.to_numeric(score_df[col], errors="coerce"),
                    mode="lines",
                    name=col.capitalize(),
                    line=dict(color=color, width=1.5, dash="dot"),
                    opacity=0.7,
                    hovertemplate=f"<b>%{{x|%Y-%m-%d}}</b><br>{col.capitalize()}: %{{y:.1f}}<extra></extra>",
                )
            )

    # Composite score main line
    if "composite_score" in score_df.columns:
        fig.add_trace(
            go.Scatter(
                x=score_df["score_date"],
                y=pd.to_numeric(score_df["composite_score"], errors="coerce"),
                mode="lines+markers",
                name="Composite Score",
                line=dict(color="#1f77b4", width=2.5),
                marker=dict(size=6),
                hovertemplate="<b>%{x|%Y-%m-%d}</b><br>Composite: %{y:.1f}<extra></extra>",
            )
        )

    # Signal markers if signal column present
    if "signal" in score_df.columns and "composite_score" in score_df.columns:
        for sig, symbol, color in [
            ("ENTER", "triangle-up", "#2ca02c"),
            ("EXIT", "triangle-down", "#d62728"),
            ("REDUCE", "circle", "#ff7f0e"),
        ]:
            mask = score_df["signal"].str.upper() == sig if "signal" in score_df.columns else pd.Series([False] * len(score_df))
            if mask.any():
                fig.add_trace(
                    go.Scatter(
                        x=score_df.loc[mask, "score_date"],
                        y=pd.to_numeric(score_df.loc[mask, "composite_score"], errors="coerce"),
                        mode="markers",
                        name=sig,
                        marker=dict(symbol=symbol, size=12, color=color),
                        hovertemplate=f"<b>%{{x|%Y-%m-%d}}</b><br>Signal: {sig}<extra></extra>",
                    )
                )

    fig.update_layout(
        title=f"{ticker} — Score History",
        xaxis=dict(title="Date", showgrid=True, gridcolor="rgba(0,0,0,0.07)"),
        yaxis=dict(title="Score", range=[0, 100], showgrid=True, gridcolor="rgba(0,0,0,0.07)"),
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=60, b=40, l=60, r=20),
    )
    return fig


def _conviction_history_chart(score_df: pd.DataFrame, ticker: str) -> go.Figure:
    """Conviction history line chart."""
    if "conviction" not in score_df.columns:
        fig = go.Figure()
        fig.update_layout(title=f"{ticker} — Conviction History (no data)")
        return fig

    fig = go.Figure(
        go.Scatter(
            x=pd.to_datetime(score_df.get("score_date", [])),
            y=pd.to_numeric(score_df["conviction"], errors="coerce"),
            mode="lines+markers",
            name="Conviction",
            line=dict(color="#9467bd", width=2.5),
            marker=dict(size=6),
            hovertemplate="<b>%{x|%Y-%m-%d}</b><br>Conviction: %{y:.1f}<extra></extra>",
        )
    )
    fig.update_layout(
        title=f"{ticker} — Conviction History",
        xaxis=dict(title="Date", showgrid=True, gridcolor="rgba(0,0,0,0.07)"),
        yaxis=dict(title="Conviction", range=[0, 100], showgrid=True, gridcolor="rgba(0,0,0,0.07)"),
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(t=60, b=40, l=60, r=20),
        showlegend=False,
    )
    return fig


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

st.title("Research")

# ---- Symbol search ----
all_symbols = get_distinct_symbols()

st.subheader("Ticker Search")
search_col, select_col = st.columns([1, 2])
with search_col:
    text_search = st.text_input("Search ticker", placeholder="e.g. AAPL")
with select_col:
    filtered_symbols = [s for s in all_symbols if text_search.upper() in s.upper()] if text_search else all_symbols
    selected_ticker = st.selectbox(
        "Select from available tickers",
        options=[""] + filtered_symbols,
        help="Type in search box to filter",
    )

# -----------------------------------------------------------------------
# Default: Top 10 by most recent score
# -----------------------------------------------------------------------
if not selected_ticker:
    st.subheader("Top 10 by Most Recent Score")
    top_df = get_top_recent_symbols(10)
    if not top_df.empty:
        display_cols = [
            c for c in [
                "symbol", "score_date", "composite_score",
                "beat_spy_10d", "beat_spy_30d", "return_10d", "return_30d"
            ]
            if c in top_df.columns
        ]
        display_df = top_df[display_cols].copy()
        for col in ["beat_spy_10d", "beat_spy_30d"]:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(_beat_icon)
        for col in ["composite_score", "return_10d", "return_30d"]:
            if col in display_df.columns:
                display_df[col] = pd.to_numeric(display_df[col], errors="coerce").round(2)
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("No data in research DB yet.")
    st.stop()

# -----------------------------------------------------------------------
# Ticker Detail
# -----------------------------------------------------------------------
st.divider()
st.header(f"{selected_ticker}")

with st.spinner(f"Loading data for {selected_ticker}..."):
    score_df = get_score_history(selected_ticker)
    thesis_df = get_investment_thesis(selected_ticker)

if score_df.empty:
    st.warning(f"No score history found for {selected_ticker}.")
else:
    score_df["score_date"] = pd.to_datetime(score_df["score_date"])
    score_df = score_df.sort_values("score_date")

    # Try to pull sub-scores if available in a broader query
    full_score_df = query_research_db(
        "SELECT * FROM score_performance WHERE symbol = ? ORDER BY score_date",
        params=(selected_ticker,),
    )
    if not full_score_df.empty:
        score_df = full_score_df
        score_df["score_date"] = pd.to_datetime(score_df["score_date"])

    # ---- Score history chart ----
    st.subheader("Score History")
    score_fig = _score_history_chart(score_df, selected_ticker)
    st.plotly_chart(score_fig, use_container_width=True)

    # ---- Conviction history chart ----
    st.subheader("Conviction History")
    if "conviction" in score_df.columns:
        conv_fig = _conviction_history_chart(score_df, selected_ticker)
        st.plotly_chart(conv_fig, use_container_width=True)
    else:
        st.info("No conviction data in score_performance table.")

    # ---- Performance outcomes table ----
    st.subheader("Performance Outcomes")
    outcome_cols = [
        c for c in [
            "score_date", "composite_score",
            "beat_spy_10d", "beat_spy_30d",
            "return_10d", "return_30d", "spy_10d_return", "spy_30d_return"
        ]
        if c in score_df.columns
    ]
    if outcome_cols:
        outcome_df = score_df[outcome_cols].copy().sort_values("score_date", ascending=False)
        for col in ["beat_spy_10d", "beat_spy_30d"]:
            if col in outcome_df.columns:
                outcome_df[col] = outcome_df[col].apply(_beat_icon)
        for col in ["return_10d", "return_30d", "spy_10d_return", "spy_30d_return"]:
            if col in outcome_df.columns:
                outcome_df[col] = pd.to_numeric(outcome_df[col], errors="coerce").apply(
                    lambda x: f"{x*100:+.2f}%" if pd.notna(x) else "⏳"
                )
        st.dataframe(outcome_df, use_container_width=True, hide_index=True)

# ---- Thesis summary timeline ----
st.subheader("Thesis Summary Timeline")

if thesis_df is not None and not thesis_df.empty:
    # Sort by date descending
    date_col = next((c for c in ["date", "created_at", "updated_at", "thesis_date"] if c in thesis_df.columns), None)
    if date_col:
        thesis_df[date_col] = pd.to_datetime(thesis_df[date_col])
        thesis_df = thesis_df.sort_values(date_col, ascending=False)

    for _, row in thesis_df.iterrows():
        date_val = str(row.get(date_col, "Unknown date")) if date_col else "Unknown date"
        thesis_text = row.get("thesis_summary", row.get("thesis", ""))
        signal = row.get("signal", "")
        score = row.get("composite_score", row.get("score", ""))

        header = f"{date_val}"
        if signal:
            header += f" — {signal}"
        if pd.notna(score) and score != "":
            try:
                header += f" (Score: {float(score):.1f})"
            except Exception:
                pass

        with st.expander(header):
            if thesis_text:
                st.write(thesis_text)
            else:
                st.write("No thesis text available.")
else:
    st.info(f"No investment thesis records found for {selected_ticker}.")
