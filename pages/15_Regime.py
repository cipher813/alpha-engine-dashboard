"""
Regime — Alpha Engine (private console)

Observability for the quantitative regime substrate (v3) produced
weekly by the Saturday SF ``RegimeSubstrate`` Lambda
(``alpha-engine-predictor-regime-substrate``). The substrate informs
the macro economist agent as a strong prior (Stage C, pending); the
macro agent remains the final regime authority.

Stage A is observe-only. This page is the primary surface for the
4-week observation window — operators verify HMM stability, calibration
sanity, and quant-vs-LLM disagreement before any downstream consumer
is wired to the substrate.

Surfaces shipped here:

- Current-week summary card (HMM argmax + intensity + change signal)
- HMM-vs-macro-agent disagreement check (substrate ``hmm.argmax`` vs
  ``signals.json`` ``market_regime``, mapped to the 3-state taxonomy)
- HMM probability trend (P(bear) / P(neutral) / P(bull) over time)
- Composite intensity_z trend (positive = risk-on)
- BOCPD change-signal markers + run-length confidence
- Per-feature z-scores (current week) + raw feature values
- Guardrail flag panel (mirrors macro agent's _validate_regime severity)
- Fit-window metadata + HMM feature columns
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.header import render_footer, render_header
from components.styles import inject_base_css, inject_docs_css
from loaders.s3_loader import (
    load_regime_substrate_history,
    load_regime_substrate_latest,
)
from loaders.signal_loader import get_available_signal_dates, load_signals


st.set_page_config(
    page_title="Regime — Alpha Engine",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_base_css()
inject_docs_css()
render_header(current_page="Regime")

st.divider()

st.markdown("### Regime Substrate (v3) — Observation Console")
st.caption(
    "Quantitative regime substrate produced weekly by the Saturday SF "
    "``RegimeSubstrate`` Lambda. Substrate informs the macro economist "
    "agent as a strong prior; the macro agent remains the final regime "
    "authority. Stage A is observe-only — use this page to verify HMM "
    "stability + calibration + quant-vs-LLM agreement before wiring "
    "downstream consumers (Stage C onward)."
)

# ---------------------------------------------------------------------------
# Data load
# ---------------------------------------------------------------------------

latest = load_regime_substrate_latest()
history = load_regime_substrate_history(n_weeks=26)

if latest is None:
    st.warning(
        "No regime substrate artifact found at ``s3://alpha-engine-research/"
        "regime/latest.json``. This is expected before the first Saturday "
        "SF ``RegimeSubstrate`` state executes successfully. Verify the "
        "Lambda exists (``alpha-engine-predictor-regime-substrate``) and "
        "the SF state insertion has been deployed."
    )
    render_footer()
    st.stop()

# ---------------------------------------------------------------------------
# Current-week summary card
# ---------------------------------------------------------------------------

st.markdown("### Current week")

hmm = latest.get("hmm", {})
composite = latest.get("composite", {})
bocpd = latest.get("bocpd", {})

c1, c2, c3, c4 = st.columns(4)
c1.metric(
    "HMM regime",
    str(hmm.get("argmax", "—")).upper(),
    delta=f"{hmm.get('weeks_in_current_state', 0)}w in state",
    delta_color="off",
)
c2.metric(
    "Intensity (risk-on → +)",
    f"{composite.get('intensity_z', 0.0):+.2f}",
    delta=composite.get("implied_severity", "—"),
    delta_color="off",
)
change_signal = bool(bocpd.get("change_signal", False))
c3.metric(
    "Change signal",
    "⚠ FIRED" if change_signal else "STABLE",
    delta=f"max run-length P={bocpd.get('max_runlength_prob', 0.0):.2f}",
    delta_color="off",
)
c4.metric(
    "Calendar / trading day",
    latest.get("calendar_date", "—"),
    delta=f"td: {latest.get('trading_day', '—')}",
    delta_color="off",
)

# Surface the HMM probability triplet inline
probs = hmm.get("probs", {})
st.caption(
    f"P(bear) = **{probs.get('bear', 0):.2f}**  ·  "
    f"P(neutral) = **{probs.get('neutral', 0):.2f}**  ·  "
    f"P(bull) = **{probs.get('bull', 0):.2f}**  ·  "
    f"argmax = **{hmm.get('argmax', '—')}**  ·  "
    f"run_id = `{latest.get('run_id', '—')}`"
)

st.divider()

# ---------------------------------------------------------------------------
# HMM vs macro-agent disagreement (Stage A's headline diagnostic)
# ---------------------------------------------------------------------------

st.markdown("### HMM vs macro economist — disagreement check")
st.caption(
    "Substrate's HMM argmax compared to the macro agent's regime call "
    "from the most recent ``signals.json``. Both are calculated "
    "independently — the macro agent does not yet read the substrate "
    "(Stage C will wire it in). This panel is the observation-period "
    "instrument for measuring whether the LLM regime authority would "
    "agree, disagree by one severity, or disagree harder."
)

dates = get_available_signal_dates()
agent_regime: str | None = None
agent_date: str | None = None
if dates:
    agent_date = dates[0]
    signals = load_signals(agent_date)
    if signals:
        agent_regime = signals.get("market_regime")

if agent_regime is None:
    st.info("Macro agent regime call not yet available — `signals.json` for the latest date is missing or empty.")
else:
    # Map 4-class taxonomy (bull/neutral/caution/bear) to 3-state for
    # apples-to-apples comparison with the HMM. "caution" maps to "bear"
    # on the substrate side (HMM has no caution state; caution-tilted
    # severity is encoded in intensity_z rather than label).
    def _normalize(label: str) -> str:
        if label in ("bear", "caution"):
            return "bear"
        if label == "neutral":
            return "neutral"
        if label == "bull":
            return "bull"
        return label

    hmm_norm = _normalize(hmm.get("argmax", ""))
    agent_norm = _normalize(agent_regime)

    if hmm_norm == agent_norm:
        st.success(
            f"**Agreement.** HMM argmax = `{hmm.get('argmax')}` · "
            f"macro agent = `{agent_regime}` (signals.json from {agent_date})."
        )
    else:
        st.warning(
            f"**Disagreement.** HMM argmax = `{hmm.get('argmax')}` ≠ "
            f"macro agent = `{agent_regime}` (signals.json from {agent_date}). "
            f"This is informational during Stage A; not actionable yet. "
            f"Capture both calls + the realized market behavior over the "
            f"following 8 weeks for the T1 retrospective ground-truth "
            f"comparison (regime-v3-260514.md §5.3.3)."
        )

st.divider()

# ---------------------------------------------------------------------------
# HMM probability trend (stacked area)
# ---------------------------------------------------------------------------

if history:
    st.markdown("### HMM probability trend")
    st.caption(
        "Rolling weekly P(bear), P(neutral), P(bull) from the filter-only "
        "(Hamilton-Kim) posterior. Look for: (a) state stability — no "
        "label-switching across refits, (b) duration realism — bear/bull "
        "states lasting weeks-to-months not single weeks, (c) clean "
        "transitions during known regime shifts."
    )

    rows = []
    for entry in history:
        run_id = entry.get("run_id", "")
        ts = pd.to_datetime(entry.get("trading_day"), errors="coerce")
        p = entry.get("hmm", {}).get("probs", {})
        rows.append({
            "trading_day": ts,
            "P(bear)": p.get("bear", 0.0),
            "P(neutral)": p.get("neutral", 0.0),
            "P(bull)": p.get("bull", 0.0),
            "run_id": run_id,
        })
    hist_df = pd.DataFrame(rows).dropna(subset=["trading_day"]).sort_values("trading_day")

    if not hist_df.empty:
        fig = go.Figure()
        for col, color in [("P(bear)", "#d62728"), ("P(neutral)", "#7f7f7f"), ("P(bull)", "#2ca02c")]:
            fig.add_trace(go.Scatter(
                x=hist_df["trading_day"], y=hist_df[col],
                mode="lines", stackgroup="one", name=col,
                line=dict(width=0.5, color=color),
            ))
        fig.update_layout(
            height=320, margin=dict(l=0, r=0, t=10, b=0),
            yaxis=dict(range=[0, 1], tickformat=".0%", title="Posterior"),
            xaxis_title="Trading day",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, use_container_width=True)

    # Composite intensity trend
    st.markdown("### Composite intensity trend")
    st.caption(
        "AQR-style risk-on/risk-off macro z-score composite. Positive = "
        "risk-on; negative = risk-off. Pure rule-based (no estimation "
        "risk) — the always-available fallback when HMM is unfit. "
        "Threshold-band tints reflect ``implied_severity`` carving."
    )
    int_rows = []
    for entry in history:
        ts = pd.to_datetime(entry.get("trading_day"), errors="coerce")
        cz = entry.get("composite", {}).get("intensity_z")
        if ts is not None and cz is not None:
            int_rows.append({"trading_day": ts, "intensity_z": cz})
    int_df = pd.DataFrame(int_rows).dropna().sort_values("trading_day")
    if not int_df.empty:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=int_df["trading_day"], y=int_df["intensity_z"],
            mode="lines+markers", name="intensity_z",
            line=dict(color="#1f77b4", width=2),
        ))
        fig2.add_hline(y=1.0, line_dash="dot", line_color="#2ca02c", annotation_text="risk-on", annotation_position="right")
        fig2.add_hline(y=-1.0, line_dash="dot", line_color="#d62728", annotation_text="risk-off", annotation_position="right")
        fig2.add_hline(y=0.0, line_dash="solid", line_color="#cccccc")
        fig2.update_layout(
            height=300, margin=dict(l=0, r=0, t=10, b=0),
            yaxis_title="intensity_z (z-units)",
            xaxis_title="Trading day",
        )
        st.plotly_chart(fig2, use_container_width=True)

    # Change-signal markers
    change_rows = [
        (pd.to_datetime(e.get("trading_day"), errors="coerce"), bool(e.get("bocpd", {}).get("change_signal", False)))
        for e in history
    ]
    n_changes = sum(1 for _, c in change_rows if c)
    if n_changes:
        change_dates = [d.date() for d, c in change_rows if c and d is not pd.NaT]
        st.info(f"**BOCPD change-signal fired {n_changes}× in window** — dates: {', '.join(str(d) for d in change_dates)}")
    else:
        st.caption(f"BOCPD change-signal: no fires in the {len(history)}-week window.")

    st.divider()

# ---------------------------------------------------------------------------
# Current-week feature panel
# ---------------------------------------------------------------------------

st.markdown("### Current week features")
features = latest.get("features", {})
per_feature_z = composite.get("per_feature_z", {})

feature_rows = []
for feat in [
    "spy_20d_return", "vix_level", "vix_term_slope",
    "hy_oas_bps", "yield_curve_slope", "market_breadth",
]:
    raw = features.get(feat)
    z = per_feature_z.get(feat)
    feature_rows.append({
        "feature": feat,
        "raw_value": "—" if raw is None else f"{raw:.3f}",
        "z_score": "—" if z is None else f"{z:+.2f}",
    })
st.dataframe(pd.DataFrame(feature_rows), hide_index=True, use_container_width=True)

# ---------------------------------------------------------------------------
# Guardrail flags
# ---------------------------------------------------------------------------

st.markdown("### Guardrail flags")
st.caption(
    "Mirrors the macro agent's ``_validate_regime`` severity-escalator "
    "rules. Active flags indicate quantitative conditions that would "
    "force a minimum severity if the macro agent were already consuming "
    "the substrate. ``active_severity_floor`` is the resulting minimum."
)
guardrails = latest.get("guardrails", {})
g_cols = st.columns(3)
flag_labels = [
    ("vix_caution_breached", "VIX caution"),
    ("vix_bear_breached", "VIX bear"),
    ("spy_30d_caution_breached", "SPY 30d caution"),
    ("spy_30d_bear_breached", "SPY 30d bear"),
    ("hy_oas_caution_breached", "HY OAS caution"),
]
for i, (k, label) in enumerate(flag_labels):
    fired = bool(guardrails.get(k))
    g_cols[i % 3].metric(label, "⚠ FIRED" if fired else "—", delta_color="off")
floor = guardrails.get("active_severity_floor")
if floor:
    st.warning(f"**Active severity floor:** `{floor}` — macro agent would be forced to at least this severity.")

# ---------------------------------------------------------------------------
# Model metadata
# ---------------------------------------------------------------------------

st.divider()
st.markdown("### Model metadata")
md = latest.get("model_metadata", {})
md_cols = st.columns(3)
md_cols[0].caption(f"**HMM features:** `{', '.join(md.get('hmm_feature_columns') or [])}`")
md_cols[1].caption(f"**Fit window:** {md.get('fit_window_start', '—')} → {md.get('fit_window_end', '—')}")
md_cols[2].caption(f"**Written at:** {md.get('written_at', '—')}")
st.caption(f"Schema version: `{latest.get('schema_version', '—')}` · Composite weights: `{md.get('composite_weights_version', '—')}`")

render_footer()
