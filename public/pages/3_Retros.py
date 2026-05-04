"""
Nous Ergon — Incidents & Retros

Three production-incident postmortems. Recruiters and interviewers can read
the full set in one scroll; each retro follows the same five-section shape:
symptoms · detection · root cause · fix · systemic improvement.
"""

import os

import streamlit as st

from components.header import render_header, render_footer
from components.styles import inject_base_css, inject_docs_css

st.set_page_config(
    page_title="Retros — Nous Ergon",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_base_css()
inject_docs_css()
render_header(current_page="Retros")

st.divider()

_RETROS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "retros")

# Order matters — each retro lands as its own section, top-to-bottom.
_RETROS = [
    "01_pfe_short_sell.md",
    "02_eod_pipeline_recovery.md",
    "03_predictor_meta_collapse.md",
]


# ---------------------------------------------------------------------------
# Page intro
# ---------------------------------------------------------------------------

st.markdown("# Incidents & Retros")
st.markdown(
    "Production maturity is easier to claim than to demonstrate. These are "
    "real incidents from the system, written tight: what failed, how it was "
    "caught, what caused it, what fixed it, and what changed structurally so "
    "the same class of bug doesn't recur."
)
st.markdown(
    "_This is the public-facing summary. The private interview kit holds "
    "deeper retros with full code paths and naive first attempts._"
)

st.divider()

# ---------------------------------------------------------------------------
# Render each retro inline
# ---------------------------------------------------------------------------

for fn in _RETROS:
    path = os.path.join(_RETROS_DIR, fn)
    if os.path.exists(path):
        with open(path) as f:
            st.markdown(f.read())
        st.divider()
    else:
        st.warning(f"Missing retro file: {fn}")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

render_footer()
