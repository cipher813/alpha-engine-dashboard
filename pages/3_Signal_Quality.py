"""
Signal Quality page — Accuracy trends, bucket/regime charts, alpha distribution,
scoring weight history.
"""

import sys
import os

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loaders.db_loader import get_score_performance, get_macro_snapshots
from loaders.s3_loader import load_scoring_weights, load_scoring_weights_history
from charts.accuracy_chart import (
    make_accuracy_trend_chart,
    make_accuracy_by_bucket_chart,
    make_accuracy_by_regime_chart,
    make_alpha_distribution_chart,
)
from charts.attribution_chart import make_weight_history_chart

st.set_page_config(page_title="Signal Quality — Alpha Engine", layout="wide")

# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

st.title("Signal Quality & Accuracy")
st.caption("Historical accuracy of Alpha Engine signals vs SPY")

# ---- Load data ----
with st.spinner("Loading signal performance data..."):
    perf_df = get_score_performance()
    macro_df = get_macro_snapshots()
    current_weights = load_scoring_weights()
    weight_history = load_scoring_weights_history()

# ---- Data availability banner ----
if perf_df is None or perf_df.empty:
    st.warning(
        "score_performance table is empty or research.db is unavailable. "
        "Signal quality metrics will not be available until the Research Lambda "
        "has run and populated outcome data."
    )
    st.stop()

# Check if enough outcome data is populated
beat_10d_col = "beat_spy_10d" if "beat_spy_10d" in perf_df.columns else None
populated_rows = 0
if beat_10d_col:
    populated_rows = int(perf_df[beat_10d_col].notna().sum())

if populated_rows < 20:
    st.info(
        f"Only {populated_rows} signals have 10d outcome data populated "
        f"(need ≥ 20 for meaningful accuracy stats). Charts will update as outcomes accrue."
    )

# -----------------------------------------------------------------------
# Section 1: Accuracy vs Time
# -----------------------------------------------------------------------
st.header("Accuracy Trend Over Time")
trend_fig = make_accuracy_trend_chart(perf_df)
st.plotly_chart(trend_fig, use_container_width=True)

# -----------------------------------------------------------------------
# Section 2: Accuracy by Score Bucket
# -----------------------------------------------------------------------
st.header("Accuracy by Score Bucket")
bucket_fig = make_accuracy_by_bucket_chart(perf_df)
st.plotly_chart(bucket_fig, use_container_width=True)

# -----------------------------------------------------------------------
# Section 3: Accuracy by Market Regime
# -----------------------------------------------------------------------
st.header("Accuracy by Market Regime")
if macro_df is None or macro_df.empty:
    st.warning("Macro data not available — cannot show regime breakdown.")
else:
    regime_fig = make_accuracy_by_regime_chart(perf_df, macro_df)
    st.plotly_chart(regime_fig, use_container_width=True)

# -----------------------------------------------------------------------
# Section 4: Alpha Distribution
# -----------------------------------------------------------------------
st.header("Alpha Distribution (10d Return vs SPY)")
dist_fig = make_alpha_distribution_chart(perf_df)
st.plotly_chart(dist_fig, use_container_width=True)

st.divider()

# -----------------------------------------------------------------------
# Section 5: Scoring Weight History
# -----------------------------------------------------------------------
st.header("Scoring Weights")

# Current weights metric cards
if current_weights:
    def _to_pct(val) -> str:
        try:
            v = float(val)
            if v <= 1.0:
                v = v * 100
            return f"{v:.1f}%"
        except Exception:
            return str(val)

    w_col1, w_col2, w_col3 = st.columns(3)
    with w_col1:
        st.metric("Technical Weight", _to_pct(current_weights.get("technical", "—")))
    with w_col2:
        st.metric("News Weight", _to_pct(current_weights.get("news", "—")))
    with w_col3:
        st.metric("Research Weight", _to_pct(current_weights.get("research", "—")))

    updated = current_weights.get("updated_at", current_weights.get("date", "unknown"))
    st.caption(f"Weights last updated: {updated}")
else:
    st.warning("scoring_weights.json not found in S3.")

# Weight history line chart
if weight_history:
    st.subheader("Weight History")
    weight_fig = make_weight_history_chart(weight_history)
    st.plotly_chart(weight_fig, use_container_width=True)
else:
    st.info("No scoring weight history files found in S3.")
