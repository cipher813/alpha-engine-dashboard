"""
Evaluation page — structured visualizations for Phase 2/3/4 metrics.

Reads the weekly backtester report from S3 and displays:
  - Pipeline lift waterfall (Phase 2)
  - Component diagnostics tables (Phase 3)
  - Self-adjustment status (Phase 4)
"""

import json
import os
import sys

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loaders.s3_loader import (
    list_backtest_dates,
    load_backtest_file,
    _fetch_s3_json,
    _research_bucket,
)
from shared.formatters import format_pct

st.set_page_config(page_title="Evaluation — Alpha Engine", layout="wide")

st.title("Pipeline Evaluation")
st.caption("Decision-boundary lift metrics, component diagnostics, and self-adjustment status.")


# ── Date selector ─────────────────────────────────────────────────────────────

backtest_dates = list_backtest_dates()
if not backtest_dates:
    st.warning("No backtest results found. Run the backtester to populate results.")
    st.stop()

selected_date = st.selectbox("Backtest Run Date", options=backtest_dates)

with st.spinner(f"Loading evaluation data for {selected_date}..."):
    metrics = load_backtest_file(selected_date, "metrics.json")
    report_md = load_backtest_file(selected_date, "report.md")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _safe_float(v) -> float | None:
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _fmt_pct(v, decimals=2) -> str:
    if v is None:
        return "—"
    return f"{v * 100:+.{decimals}f}%"


# ── Extract sections from report.md ──────────────────────────────────────────
# The backtester report.md contains structured sections we can parse.


def _extract_section(md: str, heading: str) -> str | None:
    """Extract a markdown section by heading (## level)."""
    if not md:
        return None
    marker = f"## {heading}"
    start = md.find(marker)
    if start == -1:
        return None
    rest = md[start + len(marker):]
    end = rest.find("\n## ")
    if end == -1:
        end = rest.find("\n# ")
    if end == -1:
        end = rest.find("\n---")
    return rest[:end].strip() if end != -1 else rest.strip()


# ═══════════════════════════════════════════════════════════════════════════════
# Section 1: Pipeline Lift Waterfall (Phase 2)
# ═══════════════════════════════════════════════════════════════════════════════

st.header("1. Pipeline Lift — Decision Boundary Analysis")

# Try to extract lift data from metrics.json or report
lift_section = _extract_section(report_md, "End-to-end pipeline lift") if report_md else None

if lift_section:
    # Parse lift values from report text for waterfall chart
    lift_steps = []
    step_names = [
        ("Scanner filter lift", "Scanner"),
        ("Team selection lift", "Teams"),
        ("CIO selection lift", "CIO"),
        ("Predictor lift", "Predictor"),
        ("Executor lift", "Executor"),
        ("Full pipeline lift", "Full Pipeline"),
    ]

    for search_term, label in step_names:
        for line in lift_section.split("\n"):
            if search_term.lower() in line.lower() and ":" in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    val_str = parts[-1].strip().split()[0].replace("%", "").replace("+", "")
                    val = _safe_float(val_str)
                    if val is not None:
                        if abs(val) < 1:
                            lift_steps.append({"step": label, "lift": val})
                        else:
                            lift_steps.append({"step": label, "lift": val / 100})
                break

    if lift_steps:
        fig = go.Figure(go.Waterfall(
            name="Lift",
            orientation="v",
            x=[s["step"] for s in lift_steps],
            y=[s["lift"] * 100 for s in lift_steps],
            textposition="outside",
            text=[f"{s['lift']*100:+.2f}%" for s in lift_steps],
            connector={"line": {"color": "rgb(63, 63, 63)"}},
            increasing={"marker": {"color": "#2ca02c"}},
            decreasing={"marker": {"color": "#d62728"}},
        ))
        fig.update_layout(
            title="Pipeline Lift at Each Decision Boundary",
            yaxis_title="Lift (percentage points)",
            plot_bgcolor="white",
            paper_bgcolor="white",
            height=400,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Lift waterfall chart will populate once lift metrics have data.")

    with st.expander("Raw Lift Report"):
        st.markdown(lift_section)
else:
    st.info("Pipeline lift data not available for this backtest run.")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# Section 2: Component Diagnostics (Phase 3)
# ═══════════════════════════════════════════════════════════════════════════════

st.header("2. Component Diagnostics")

tab_triggers, tab_exits, tab_veto, tab_alpha, tab_shadow, tab_macro = st.tabs([
    "Entry Triggers", "Exit Timing", "Veto Value", "Alpha Distribution",
    "Shadow Book", "Macro A/B",
])

# ── Entry Triggers (3a) ──
with tab_triggers:
    trigger_section = _extract_section(report_md, "Entry trigger scorecard") if report_md else None
    if trigger_section:
        st.markdown(trigger_section)
    else:
        st.info("Entry trigger scorecard not available. Requires trades with trigger_type logged.")

# ── Exit Timing (3c) ──
with tab_exits:
    exit_section = _extract_section(report_md, "Exit timing analysis") if report_md else None
    if exit_section:
        st.markdown(exit_section)
    else:
        st.info("Exit timing analysis not available. Requires completed roundtrip trades.")

# ── Veto Value (3e) ──
with tab_veto:
    veto_section = _extract_section(report_md, "Net veto value") if report_md else None
    if veto_section:
        st.markdown(veto_section)
    else:
        st.info("Net veto value not available. Requires predictor vetoes with resolved returns.")

# ── Alpha Distribution (3g) ──
with tab_alpha:
    alpha_section = _extract_section(report_md, "Alpha magnitude distribution") if report_md else None
    cal_section = _extract_section(report_md, "Score calibration") if report_md else None
    if alpha_section:
        st.markdown(alpha_section)
    if cal_section:
        st.markdown(cal_section)
    if not alpha_section and not cal_section:
        st.info("Alpha distribution not available. Requires score_performance with resolved returns.")

# ── Shadow Book (3b) ──
with tab_shadow:
    shadow_section = _extract_section(report_md, "Risk guard shadow book") if report_md else None
    if shadow_section:
        st.markdown(shadow_section)
    else:
        st.info("Shadow book analysis not available. Requires executor_shadow_book entries.")

# ── Macro A/B (3f) ──
with tab_macro:
    macro_section = _extract_section(report_md, "Macro multiplier evaluation") if report_md else None
    if macro_section:
        st.markdown(macro_section)
    else:
        st.info("Macro A/B evaluation not available. Requires cio_evaluations with macro shift data.")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# Section 3: Self-Adjustment Status (Phase 4)
# ═══════════════════════════════════════════════════════════════════════════════

st.header("3. Self-Adjustment Mechanisms")

# Load current S3 configs to show active state
executor_params = _fetch_s3_json(_research_bucket(), "config/executor_params.json")
scanner_params = _fetch_s3_json(_research_bucket(), "config/scanner_params.json")
team_slots = _fetch_s3_json(_research_bucket(), "config/team_slots.json")
research_params = _fetch_s3_json(_research_bucket(), "config/research_params.json")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Executor Adjustments")

    # Disabled triggers (4e)
    disabled = executor_params.get("disabled_triggers", []) if executor_params else []
    if disabled:
        st.warning(f"Disabled triggers: {', '.join(disabled)}")
        updated = executor_params.get("disabled_triggers_updated_at", "—") if executor_params else "—"
        st.caption(f"Last updated: {updated}")
    else:
        st.success("All triggers active")

    # p_up sizing (4d)
    p_up_enabled = executor_params.get("use_p_up_sizing", False) if executor_params else False
    if p_up_enabled:
        ic = executor_params.get("p_up_sizing_ic", "—") if executor_params else "—"
        st.success(f"p_up sizing enabled (IC={ic})")
    else:
        st.info("p_up sizing disabled — awaiting positive IC")

    # Sizing A/B (4f) — from report
    sizing_section = _extract_section(report_md, "Position sizing A/B test") if report_md else None
    if sizing_section:
        with st.expander("Sizing A/B Results"):
            st.markdown(sizing_section)

with col2:
    st.subheader("Research Adjustments")

    # Scanner params (4a)
    if scanner_params:
        st.success("Scanner params active from S3")
        updated = scanner_params.get("updated_at", "—")
        st.caption(f"Last updated: {updated}")
        with st.expander("Scanner Params"):
            display_keys = [k for k in scanner_params if k not in ("updated_at", "leakage_rate", "n_weeks")]
            if display_keys:
                st.json({k: scanner_params[k] for k in display_keys})
    else:
        st.info("Scanner params: using defaults (no S3 override)")

    # Team slots (4b)
    if team_slots:
        st.success("Team slot allocation active")
        updated = team_slots.get("updated_at", "—")
        st.caption(f"Last updated: {updated}")
        slot_display = {k: v for k, v in team_slots.items() if k != "updated_at"}
        if slot_display:
            slot_df = pd.DataFrame(
                [{"Team": k, "Slots": v} for k, v in slot_display.items()]
            )
            st.dataframe(slot_df, use_container_width=True, hide_index=True)
    else:
        st.info("Team slots: using defaults (3 per team)")

    # CIO mode (4c)
    cio_mode = research_params.get("cio_mode", "llm") if research_params else "llm"
    if cio_mode == "deterministic":
        reason = research_params.get("cio_mode_reason", "") if research_params else ""
        st.warning(f"CIO mode: deterministic")
        if reason:
            st.caption(reason)
    else:
        st.success("CIO mode: LLM (default)")

# ── Phase 4 sections from report ──
phase4_section = _extract_section(report_md, "Phase 4: Self-Adjustment Mechanisms") if report_md else None
if not phase4_section and report_md:
    # Try alternate heading formats
    for heading in ["Trigger optimizer", "Predictor p_up sizing", "Scanner filter optimizer"]:
        section = _extract_section(report_md, heading)
        if section:
            phase4_section = section
            break

if phase4_section:
    with st.expander("Full Phase 4 Report", expanded=False):
        st.markdown(phase4_section)
