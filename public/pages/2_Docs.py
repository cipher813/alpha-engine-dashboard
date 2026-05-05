"""
Nous Ergon — Documentation
Module overviews, quick starts, and deep dives.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st

from components.header import render_header, render_footer
from components.styles import inject_base_css, inject_docs_css

st.set_page_config(
    page_title="Docs — Nous Ergon",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_base_css()
inject_docs_css()
render_header(current_page="Docs")

st.divider()

# ---------------------------------------------------------------------------
# Section registry — maps display names to markdown files
# ---------------------------------------------------------------------------

_DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs")

SECTIONS = {
    "Overview": "overview.md",
    "Research": "research.md",
    "Research — Architecture & Stack": "research_architecture.md",
    "Research — ReAct Agents": "research_agents.md",
    "Research — LangGraph": "research_langgraph.md",
    "Research — RAG & Vector DB": "research_rag.md",
    "Predictor": "predictor.md",
    "Executor": "executor.md",
    "Backtester": "backtester.md",
    "Data": "data.md",
    "Dashboard": "dashboard.md",
    "Evaluation": "evaluation.md",
    "Data Dictionary": "data_dictionary.md",
}

# ---------------------------------------------------------------------------
# Navigation via selectbox + query params for deep linking
# ---------------------------------------------------------------------------

params = st.query_params
default_section = params.get("section", "Overview")
if default_section not in SECTIONS:
    default_section = "Overview"

section = st.selectbox(
    "Select documentation section",
    list(SECTIONS.keys()),
    index=list(SECTIONS.keys()).index(default_section),
    label_visibility="collapsed",
)

st.query_params["section"] = section

# ---------------------------------------------------------------------------
# Render markdown content
# ---------------------------------------------------------------------------

md_path = os.path.join(_DOCS_DIR, SECTIONS[section])
if os.path.exists(md_path):
    with open(md_path) as f:
        st.markdown(f.read(), unsafe_allow_html=True)
else:
    st.warning("Documentation not yet available for this section.")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

render_footer()
