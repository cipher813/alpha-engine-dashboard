"""Eval Quality page — Are the LLM agents producing good output?

Surfaces the LLM-as-judge eval corpus (PR 2-4 of ROADMAP §1617) so
quality regressions are visible weeks before they show up in alpha.

  • Trend tab       — per-agent line charts × criterion, time-series
                      view of judge scores. Toggle Haiku-vs-Sonnet to
                      spot tier disagreement (§1627 calibration).
  • Versions tab    — prompt-version → quality-score correlation
                      (§1633). Shows whether a rubric or agent prompt
                      bump moved scores up, down, or sideways.

Eval is observability per §1635 — this page names regressions; it
does not gate any deploy.
"""

import os
import sys
from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loaders.eval_loader import load_eval_artifacts


st.set_page_config(page_title="Eval Quality — Alpha Engine", layout="wide")
st.title("Eval Quality")
st.caption(
    "LLM-as-judge rubric scores per agent + criterion. "
    "Eval is observability, not a gate."
)


# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------

with st.sidebar:
    st.subheader("Filters")
    today = date.today()
    default_start = today - timedelta(days=84)  # ~12 weeks
    start_date = st.date_input("Start date", value=default_start)
    end_date = st.date_input("End date", value=today)
    judge_filter = st.selectbox(
        "Judge tier",
        options=["both", "claude-haiku-4-5", "claude-sonnet-4-6"],
        index=0,
    )

df = load_eval_artifacts(start_date=start_date, end_date=end_date)

if df.empty:
    st.info(
        "No eval artifacts under "
        "`s3://alpha-engine-research/decision_artifacts/_eval/` for the "
        "selected window. The eval pipeline (PR 2-3 of the LLM-as-judge "
        "workstream) writes here every Saturday after the Research Lambda."
    )
    st.stop()

if judge_filter != "both":
    df = df[df["judge_model"] == judge_filter]

if df.empty:
    st.warning(f"No eval artifacts for judge model `{judge_filter}` in window.")
    st.stop()


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_trend, tab_versions, tab_data = st.tabs(["Trend", "Versions", "Data"])


# ── Trend tab ─────────────────────────────────────────────────────────────


with tab_trend:
    st.subheader("Score trend per agent")
    st.caption(
        "Each line is one rubric criterion. Per-artifact escalation in "
        "`evals/orchestrator.py` triggers a Sonnet pass when any Haiku "
        "score < 3 — that's the borderline-recheck signal worth watching."
    )

    agents = sorted(df["judged_agent_id"].unique())
    selected_agents = st.multiselect(
        "Agents", options=agents, default=agents,
    )
    sub = df[df["judged_agent_id"].isin(selected_agents)]

    if sub.empty:
        st.warning("No data for the selected agents.")
    else:
        for agent in selected_agents:
            agent_df = sub[sub["judged_agent_id"] == agent]
            if agent_df.empty:
                continue
            fig = px.line(
                agent_df,
                x="eval_date",
                y="score",
                color="criterion",
                line_dash="judge_model" if judge_filter == "both" else None,
                markers=True,
                title=f"{agent}",
                hover_data=["judge_model", "rubric_version", "reasoning"],
            )
            fig.update_yaxes(range=[0.5, 5.5], dtick=1)
            # Visual reference at the 4-week-mean alarm threshold.
            fig.add_hline(
                y=3.0, line_dash="dash", line_color="red",
                annotation_text="alarm threshold",
                annotation_position="bottom right",
            )
            st.plotly_chart(fig, use_container_width=True)


# ── Versions tab ──────────────────────────────────────────────────────────


with tab_versions:
    st.subheader("Prompt-version → quality-score correlation")
    st.caption(
        "Did a rubric or prompt bump move scores? Box plot of scores grouped "
        "by `rubric_version` per (agent, criterion). A version that drops the "
        "median worth investigating against the prompt diff."
    )

    agents_v = sorted(df["judged_agent_id"].unique())
    agent_pick = st.selectbox(
        "Agent", options=agents_v,
        index=0 if agents_v else None,
        key="version_agent_pick",
    )
    agent_df_v = df[df["judged_agent_id"] == agent_pick]
    if agent_df_v.empty:
        st.warning("No data for the selected agent.")
    else:
        # rubric_version uniqueness is the input to the correlation —
        # if there's only one version captured we say so.
        n_versions = agent_df_v["rubric_version"].nunique()
        if n_versions <= 1:
            st.info(
                f"Only one rubric version (`{agent_df_v['rubric_version'].iloc[0]}`) "
                f"observed for {agent_pick}. Bump the rubric to compare versions."
            )
        else:
            fig = px.box(
                agent_df_v,
                x="rubric_version",
                y="score",
                color="criterion",
                points="all",
                title=f"{agent_pick} — score distribution by rubric version",
            )
            fig.update_yaxes(range=[0.5, 5.5], dtick=1)
            st.plotly_chart(fig, use_container_width=True)


# ── Data tab ──────────────────────────────────────────────────────────────


with tab_data:
    st.subheader("Raw eval rows")
    st.caption(
        "One row per (artifact, dimension). Use the search box to filter "
        "by reasoning text — useful when an alarm fires and you want to "
        "find the artifact-level rationale that drove the regression."
    )

    search = st.text_input("Filter reasoning (case-insensitive)", value="")
    table = df.copy()
    if search:
        mask = (
            table["reasoning"].str.contains(search, case=False, na=False)
            | table["overall_reasoning"].str.contains(search, case=False, na=False)
        )
        table = table[mask]

    st.dataframe(
        table[[
            "eval_date", "judged_agent_id", "criterion", "score",
            "judge_model", "rubric_version", "reasoning",
        ]],
        use_container_width=True,
        hide_index=True,
    )
    st.caption(f"{len(table)} rows • {df['run_id'].nunique()} runs in window")
