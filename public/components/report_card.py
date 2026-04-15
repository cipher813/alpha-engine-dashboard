"""System Report Card — per-module letter grades from the weekly evaluator.

Structural quality data sourced from `backtest/{date}/grading.json`. Complements
the Uptime KPI: uptime answers "is the system running?", the report card
answers "is it running well?"

Most sub-components are N/A today because they need multiple weeks of signal
history to grade. Copy surfaces this honestly — hiding it would look dishonest
as the grid fills in.
"""

from __future__ import annotations

import streamlit as st

# Letter-grade palette. Greens/yellows/oranges tuned to sit on the dark
# background used by styles.py without looking neon.
_GRADE_COLORS = {
    "A": "#7fd17f",  # green — same tone as the at-target uptime bar
    "B": "#e0c050",  # muted yellow
    "C": "#e89050",  # orange
    "D": "#d06060",  # red
    "F": "#d06060",
    "N/A": "#666",
}


def _grade_color(letter: str | None) -> str:
    if not letter:
        return _GRADE_COLORS["N/A"]
    return _GRADE_COLORS.get(letter[0].upper(), _GRADE_COLORS["N/A"])


def _format_numeric(grade: float | int | None) -> str:
    if grade is None:
        return "—"
    return f"{grade:.0f}/100"


def _key_metric_line(module_key: str, module: dict) -> str:
    """Pull one crisp detail line from the module's graded components."""
    components = module.get("components", {}) or {}
    if module_key == "research":
        comp = components.get("composite_scoring", {})
        detail = comp.get("detail") or {}
        acc = detail.get("accuracy_10d")
        if acc:
            return f"10d accuracy: {acc}"
    if module_key == "predictor":
        comp = components.get("gbm_model", {})
        detail = comp.get("detail") or {}
        ic = detail.get("rank_ic")
        if ic:
            return f"Rank IC: {ic}"
    if module_key == "executor":
        comp = components.get("portfolio", {})
        detail = comp.get("detail") or {}
        sharpe = detail.get("sharpe")
        if sharpe:
            return f"Sharpe: {sharpe}"
    return ""


def _render_component_expander(module_key: str, module: dict) -> None:
    components = module.get("components", {}) or {}
    with st.expander("Component detail"):
        any_row = False
        for comp_key, comp in components.items():
            if comp_key == "sector_teams":
                # Array of team dicts — skip for the public view, the per-module
                # grade already rolls them up via sector_teams_avg.
                continue
            if not isinstance(comp, dict):
                continue
            letter = comp.get("letter", "N/A")
            grade = comp.get("grade")
            color = _grade_color(letter)
            label = comp_key.replace("_", " ").title()
            if letter == "N/A":
                reason = comp.get("reason") or "insufficient data"
                st.markdown(
                    f'<div style="color:#888; padding:4px 0;">'
                    f'{label} — <span style="color:{color};">N/A</span> '
                    f'· {reason}</div>',
                    unsafe_allow_html=True,
                )
            else:
                detail = comp.get("detail") or {}
                detail_bits = " · ".join(f"{k}: {v}" for k, v in detail.items())
                numeric = _format_numeric(grade)
                st.markdown(
                    f'<div style="padding:4px 0;">'
                    f'{label} — <span style="color:{color}; font-weight:600;">'
                    f'{letter}</span> ({numeric})'
                    f'{" · " + detail_bits if detail_bits else ""}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            any_row = True
        if not any_row:
            st.caption("No component detail reported for this module.")


def _render_tile(column, module_key: str, display_name: str, module: dict | None) -> None:
    with column:
        if not module:
            st.markdown(f"**{display_name}**")
            st.markdown(
                f'<div style="font-size:38px; color:{_GRADE_COLORS["N/A"]}; '
                f'font-weight:700; line-height:1;">—</div>',
                unsafe_allow_html=True,
            )
            st.caption("No grading data yet.")
            return
        letter = module.get("letter", "N/A")
        color = _grade_color(letter)
        grade = module.get("grade")
        st.markdown(f"**{display_name}**")
        st.markdown(
            f'<div style="font-size:38px; color:{color}; font-weight:700; '
            f'line-height:1;">{letter}</div>',
            unsafe_allow_html=True,
        )
        st.caption(_format_numeric(grade))
        metric_line = _key_metric_line(module_key, module)
        if metric_line:
            st.markdown(
                f'<div style="color:#bbb; font-size:13px; margin-top:4px;">'
                f'{metric_line}</div>',
                unsafe_allow_html=True,
            )
        _render_component_expander(module_key, module)


def render_report_card(grading: dict | None) -> None:
    """Render the full Report Card section."""
    st.markdown("### System Report Card")

    if not grading:
        st.info("No evaluator grading has been published yet.")
        return

    overall = grading.get("overall") or {}
    overall_letter = overall.get("letter", "N/A")
    overall_numeric = _format_numeric(overall.get("grade"))
    overall_color = _grade_color(overall_letter)

    st.markdown(
        f'<div style="color:#ccc; margin-bottom:8px;">'
        f'Overall: <span style="color:{overall_color}; font-weight:700;">'
        f'{overall_letter}</span> ({overall_numeric}). '
        f'Auto-graded by the weekly evaluator. Most sub-components show N/A '
        f'while data accumulates — typically requires 4–8 weeks of signals.'
        f'</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    _render_tile(c1, "research", "Research", grading.get("research"))
    _render_tile(c2, "predictor", "Predictor", grading.get("predictor"))
    _render_tile(c3, "executor", "Executor", grading.get("executor"))

    run_date = grading.get("_run_date")
    if run_date:
        st.caption(f"Last evaluated {run_date}.")
