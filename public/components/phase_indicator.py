"""Phase indicator — shows the system's current engineering phase.

Alpha Engine moves through four phases. Each has a distinct primary KPI;
the homepage surfaces the current phase so visitors understand what's
being optimized now and why alpha is or isn't the headline metric.
"""

import streamlit as st

PHASES = [
    {"name": "Completeness", "status": "complete", "kpi": "Coverage"},
    {"name": "Reliability + Evaluation", "status": "current", "kpi": "Uptime"},
    {"name": "Performance (paper)", "status": "upcoming", "kpi": "Alpha vs SPY"},
    {"name": "Performance (live)", "status": "upcoming", "kpi": "NAV"},
]

_COLORS = {
    "complete": {"bg": "#1e3a1e", "border": "#2d5a2d", "fg": "#7fd17f"},
    "current": {"bg": "#1a3a5a", "border": "#1a73e8", "fg": "#5fa8f0"},
    "upcoming": {"bg": "#2a2a2a", "border": "#444", "fg": "#888"},
}

_ICONS = {"complete": "&#x2713;", "current": "&#x25B6;", "upcoming": "&#x2022;"}


def render_phase_indicator(current_phase: str = "Reliability + Evaluation") -> None:
    """Render the four-phase pill row with the given phase highlighted."""
    pills = []
    for i, phase in enumerate(PHASES):
        # Override phases by position relative to the current one
        if phase["name"] == current_phase:
            status = "current"
        elif any(p["name"] == current_phase for p in PHASES[i + 1:]):
            status = "complete"
        else:
            status = "upcoming"

        c = _COLORS[status]
        icon = _ICONS[status]
        pill = (
            f'<div style="flex:1; min-width:140px; background:{c["bg"]}; '
            f'border:1px solid {c["border"]}; border-radius:6px; padding:10px 12px; '
            f'text-align:center;">'
            f'<div style="color:{c["fg"]}; font-size:11px; letter-spacing:1px; '
            f'text-transform:uppercase;">Phase {i + 1} {icon}</div>'
            f'<div style="color:#eee; font-weight:600; font-size:14px; margin-top:4px;">'
            f'{phase["name"]}</div>'
            f'<div style="color:#888; font-size:11px; margin-top:2px;">'
            f'KPI: {phase["kpi"]}</div>'
            f'</div>'
        )
        pills.append(pill)

    st.markdown(
        f"""
        <div style="display:flex; gap:8px; margin:12px 0 8px 0; flex-wrap:wrap;">
          {''.join(pills)}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_phase_caption(current_phase: str = "Reliability + Evaluation") -> None:
    """One-line explainer under the phase indicator."""
    captions = {
        "Completeness": "All six modules wired end-to-end — research, prediction, execution, evaluation, data, and dashboard.",
        "Reliability + Evaluation": (
            "Reliability, transparency, and self-evaluation. "
            "Every signal, prediction, and fill instrumented. "
            "Alpha is tracked but not optimized until uptime reaches 99%."
        ),
        "Performance (paper)": "Tuning signals, risk, and execution for sustained alpha vs SPY on paper.",
        "Performance (live)": "Graduating from paper to live capital with progressive sizing.",
    }
    text = captions.get(current_phase, "")
    if text:
        st.markdown(
            f'<div style="color:#aaa; font-size:13px; margin:4px 0 12px 0; '
            f'text-align:center; font-style:italic;">{text}</div>',
            unsafe_allow_html=True,
        )
