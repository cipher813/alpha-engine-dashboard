"""
Backtester page — Last run info, param sweep heatmap, signal quality, attribution,
weight recommendations, raw report.
"""

import sys
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loaders.s3_loader import load_backtest_file, list_backtest_dates, load_config
from charts.attribution_chart import make_attribution_chart

st.set_page_config(page_title="Backtester — Alpha Engine", layout="wide")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fmt_pct(val, decimals=2) -> str:
    try:
        v = float(val)
        if abs(v) > 2:
            v = v / 100
        return f"{v * 100:+.{decimals}f}%"
    except Exception:
        return str(val) if val is not None else "—"


def _fmt_float(val, decimals=3) -> str:
    try:
        return f"{float(val):.{decimals}f}"
    except Exception:
        return str(val) if val is not None else "—"


def _make_heatmap(sweep_df: pd.DataFrame, cb_value: float) -> go.Figure:
    """Build Sharpe heatmap for a given circuit breaker value."""
    sub = sweep_df[
        pd.to_numeric(sweep_df.get("drawdown_circuit_breaker", 0), errors="coerce") == cb_value
    ] if "drawdown_circuit_breaker" in sweep_df.columns else sweep_df

    if sub.empty:
        fig = go.Figure()
        fig.update_layout(title=f"No data for CB={cb_value}")
        return fig

    x_col = next((c for c in ["min_score", "min_score_threshold"] if c in sub.columns), None)
    y_col = next((c for c in ["max_position_pct", "max_position_size"] if c in sub.columns), None)
    z_col = next((c for c in ["sharpe", "sharpe_ratio"] if c in sub.columns), None)

    if not x_col or not y_col or not z_col:
        fig = go.Figure()
        fig.update_layout(title=f"CB={cb_value} — Missing columns (need min_score, max_position_pct, sharpe)")
        return fig

    pivot = sub.pivot_table(index=y_col, columns=x_col, values=z_col, aggfunc="mean")
    pivot = pivot.sort_index(ascending=False)

    fig = px.imshow(
        pivot,
        labels=dict(x="Min Score", y="Max Position %", color="Sharpe"),
        color_continuous_scale="RdYlGn",
        aspect="auto",
        title=f"Sharpe Ratio Heatmap (Circuit Breaker: {cb_value * 100:.0f}%)",
        text_auto=".2f",
    )
    fig.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(t=60, b=40, l=80, r=20),
        coloraxis_colorbar=dict(title="Sharpe"),
    )
    return fig


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

st.title("Backtester")

# ---- Date selector ----
backtest_dates = list_backtest_dates()
if not backtest_dates:
    st.warning("No backtest results found in S3. Run the backtester to populate results.")
    st.stop()

selected_date = st.selectbox(
    "Backtest Run Date",
    options=backtest_dates,
    help="Select which backtest run to view",
)

# ---- Load all files for selected date ----
with st.spinner(f"Loading backtest results for {selected_date}..."):
    metrics = load_backtest_file(selected_date, "metrics.json")
    sweep_df = load_backtest_file(selected_date, "param_sweep.csv")
    signal_quality_df = load_backtest_file(selected_date, "signal_quality.csv")
    attribution = load_backtest_file(selected_date, "attribution.json")
    report_md = load_backtest_file(selected_date, "report.md")

# -----------------------------------------------------------------------
# Section 1: Last Run Banner
# -----------------------------------------------------------------------
st.header("Last Run Summary")

if not metrics:
    st.warning("metrics.json not found for this backtest run.")
else:
    run_date = metrics.get("run_date", metrics.get("date", selected_date))
    strategy = metrics.get("strategy", metrics.get("strategy_name", "—"))
    universe_size = metrics.get("universe_size", metrics.get("num_signals", "—"))
    data_start = metrics.get("data_start", metrics.get("start_date", "—"))
    data_end = metrics.get("data_end", metrics.get("end_date", "—"))

    banner_col1, banner_col2, banner_col3 = st.columns(3)
    with banner_col1:
        st.metric("Run Date", str(run_date))
        st.metric("Strategy", str(strategy))
    with banner_col2:
        st.metric("Data Range", f"{data_start} → {data_end}")
        st.metric("Universe Size", str(universe_size))
    with banner_col3:
        runtime = metrics.get("runtime_seconds", metrics.get("runtime", "—"))
        st.metric("Runtime", f"{runtime}s" if runtime != "—" else "—")
        status = metrics.get("status", "—")
        st.metric("Status", str(status))

st.divider()

# -----------------------------------------------------------------------
# Section 2: Portfolio Simulation Stats
# -----------------------------------------------------------------------
st.header("Portfolio Simulation Stats")

if metrics:
    m_col1, m_col2, m_col3 = st.columns(3)
    m_col4, m_col5, m_col6 = st.columns(3)

    sim = metrics.get("simulation", metrics)  # some schemas nest under "simulation"

    with m_col1:
        st.metric("Total Return", _fmt_pct(sim.get("total_return")))
    with m_col2:
        st.metric("Sharpe Ratio", _fmt_float(sim.get("sharpe_ratio", sim.get("sharpe"))))
    with m_col3:
        st.metric("Max Drawdown", _fmt_pct(sim.get("max_drawdown")))
    with m_col4:
        st.metric("Win Rate", _fmt_pct(sim.get("win_rate")))
    with m_col5:
        st.metric("Avg Alpha", _fmt_pct(sim.get("avg_alpha", sim.get("mean_alpha"))))
    with m_col6:
        st.metric("Num Trades", str(sim.get("num_trades", sim.get("trade_count", "—"))))
else:
    st.info("No simulation stats available.")

st.divider()

# -----------------------------------------------------------------------
# Section 3: Param Sweep Heatmap
# -----------------------------------------------------------------------
st.header("Parameter Sweep — Sharpe Heatmap")

if sweep_df is None or sweep_df.empty:
    st.warning("param_sweep.csv not found or empty for this run.")
else:
    # Get unique circuit breaker values for tabs
    cb_col = next((c for c in ["drawdown_circuit_breaker", "circuit_breaker", "cb"] if c in sweep_df.columns), None)

    if cb_col:
        cb_values = sorted(pd.to_numeric(sweep_df[cb_col], errors="coerce").dropna().unique().tolist())
        if cb_values:
            tab_labels = [f"CB: {v * 100:.0f}%" for v in cb_values]
            tabs = st.tabs(tab_labels)
            for tab, cb_val in zip(tabs, cb_values):
                with tab:
                    heatmap_fig = _make_heatmap(sweep_df, cb_val)
                    st.plotly_chart(heatmap_fig, use_container_width=True)

                    # Top 5 combinations
                    sub = sweep_df[
                        pd.to_numeric(sweep_df[cb_col], errors="coerce") == cb_val
                    ]
                    sharpe_col = next((c for c in ["sharpe", "sharpe_ratio"] if c in sub.columns), None)
                    if sharpe_col:
                        top5 = sub.nlargest(5, sharpe_col)
                        st.subheader("Top 5 Parameter Combinations")
                        st.dataframe(top5.reset_index(drop=True), use_container_width=True, hide_index=True)
        else:
            st.info("No circuit breaker values found in sweep data.")
    else:
        # No CB column — single heatmap
        heatmap_fig = _make_heatmap(sweep_df, None)
        st.plotly_chart(heatmap_fig, use_container_width=True)

        sharpe_col = next((c for c in ["sharpe", "sharpe_ratio"] if c in sweep_df.columns), None)
        if sharpe_col:
            top5 = sweep_df.nlargest(5, sharpe_col)
            st.subheader("Top 5 Parameter Combinations")
            st.dataframe(top5.reset_index(drop=True), use_container_width=True, hide_index=True)

st.divider()

# -----------------------------------------------------------------------
# Section 4: Signal Quality Summary
# -----------------------------------------------------------------------
st.header("Signal Quality Summary")

if metrics:
    sq_metrics = metrics.get("signal_quality", {})
    if sq_metrics:
        sq_col1, sq_col2, sq_col3, sq_col4 = st.columns(4)
        with sq_col1:
            st.metric("Accuracy 10d", _fmt_pct(sq_metrics.get("accuracy_10d")))
        with sq_col2:
            st.metric("Accuracy 30d", _fmt_pct(sq_metrics.get("accuracy_30d")))
        with sq_col3:
            st.metric("Avg Alpha 10d", _fmt_pct(sq_metrics.get("avg_alpha_10d")))
        with sq_col4:
            st.metric("Avg Alpha 30d", _fmt_pct(sq_metrics.get("avg_alpha_30d")))

if signal_quality_df is not None and not signal_quality_df.empty:
    st.subheader("Signal Quality Detail")
    st.dataframe(signal_quality_df, use_container_width=True, hide_index=True)

st.divider()

# -----------------------------------------------------------------------
# Section 5: Sub-Score Attribution
# -----------------------------------------------------------------------
st.header("Sub-Score Attribution")

if not attribution:
    st.info("attribution.json not found for this run.")
else:
    attr_fig = make_attribution_chart(attribution)
    st.plotly_chart(attr_fig, use_container_width=True)

st.divider()

# -----------------------------------------------------------------------
# Section 6: Weight Recommendations
# -----------------------------------------------------------------------
st.header("Weight Recommendations")

if metrics:
    recs = metrics.get("weight_recommendations", {})
    current = metrics.get("current_weights", {})
    suggested = metrics.get("suggested_weights", recs)

    if current or suggested:
        from loaders.s3_loader import load_scoring_weights
        live_weights = load_scoring_weights() or {}

        rec_rows = []
        for key in ["technical", "news", "research"]:
            curr_val = live_weights.get(key, current.get(key))
            sugg_val = suggested.get(key) if suggested else None
            try:
                curr_f = float(curr_val) * 100 if curr_val is not None and float(curr_val) <= 1 else float(curr_val) if curr_val is not None else None
                sugg_f = float(sugg_val) * 100 if sugg_val is not None and float(sugg_val) <= 1 else float(sugg_val) if sugg_val is not None else None
                if curr_f is not None and sugg_f is not None:
                    delta = sugg_f - curr_f
                    direction = "⬆" if delta > 0.5 else ("⬇" if delta < -0.5 else "→")
                else:
                    direction = "—"
                rec_rows.append({
                    "Sub-Score": key.capitalize(),
                    "Current Weight": f"{curr_f:.1f}%" if curr_f is not None else "—",
                    "Suggested Weight": f"{sugg_f:.1f}%" if sugg_f is not None else "—",
                    "Direction": direction,
                })
            except Exception:
                rec_rows.append({"Sub-Score": key.capitalize(), "Current Weight": "—", "Suggested Weight": "—", "Direction": "—"})

        if rec_rows:
            rec_df = pd.DataFrame(rec_rows)
            st.dataframe(rec_df, use_container_width=True, hide_index=True)
    else:
        st.info("No weight recommendations in metrics.json.")
else:
    st.info("No metrics data available for weight recommendations.")

st.divider()

# -----------------------------------------------------------------------
# Section 7: Raw Report
# -----------------------------------------------------------------------
st.header("Raw Report")

with st.expander("View Full Backtest Report (report.md)", expanded=False):
    if report_md:
        st.markdown(report_md)
    else:
        st.info("report.md not found for this backtest run.")
