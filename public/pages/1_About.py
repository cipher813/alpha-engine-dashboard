"""
Nous Ergon — About

Brand context page: brand origin (Nous Ergon = νοῦς ἔργον) + project
thesis + who built it + contact.

Per the presentation-layer outline (W2 spec), About owns brand context
only — *not* module descriptions. System architecture + per-pipeline
flows + per-module deep dives live on the Architecture page and the
per-repo GitHub READMEs respectively. Same fact in two places = two
staleness vectors.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st

from components.header import render_header, render_footer
from components.styles import inject_base_css

st.set_page_config(
    page_title="About — Nous Ergon",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_base_css()
render_header(current_page="About")

st.divider()

# ---------------------------------------------------------------------------
# Brand origin
# ---------------------------------------------------------------------------

st.markdown("### Nous Ergon")

st.markdown(
    """
    **Nous Ergon** — Greek for *intelligence at work* (νοῦς ἔργον,
    pronounced *noose air-gone*). *Nous* (νοῦς) is mind, intellect, the
    capacity for reason. *Ergon* (ἔργον) is work, deed, function — the
    same root as English *ergonomics* and *energy*.

    The name frames what the project is: agentic intelligence applied
    to a measurable, continuously verifiable problem. The work — the
    *ergon* — is what's on display. Trading is the substrate; the
    artifact is the orchestration pattern.

    The underlying project name is **Alpha Engine** — repos and S3
    paths use `alpha-engine` since they predate the public brand.
    """
)

st.markdown("---")

# ---------------------------------------------------------------------------
# Thesis
# ---------------------------------------------------------------------------

st.markdown("### Thesis")

st.markdown(
    """
    Build a multi-agent trading system end-to-end, instrument every
    decision it makes, and let it tune itself. The interesting object
    is the orchestration pattern — six modules collaborating through
    S3 contracts, three Step Function pipelines running unattended,
    and an autonomous feedback loop that writes optimized parameters
    back into the system weekly.

    The system is in **Phase 2: Reliability + Measurability buildout**
    — making the substrate trustworthy enough that Phase 3 can refine
    alpha on data, not vibes. Long-term alpha vs SPY is the metric
    Phase 3 is engineered to inflect; alpha is tracked, but not
    optimized, until the substrate is ready.

    See [Home](/) for live phase progress and per-phase key objectives,
    [Architecture](/Architecture) for the visual system walkthrough,
    and [Retros](/Retros) for production case studies.
    """
)

st.markdown("---")

# ---------------------------------------------------------------------------
# Built by
# ---------------------------------------------------------------------------

st.markdown("### Built by")

st.markdown(
    """
    Brian McMahon. Single-author project — every line of code, every
    architectural decision, every retro. The repos are public so the
    design choices and the trade-offs accepted are inspectable.

    The project began as a vehicle for engineering an agentic system
    end-to-end — multi-agent orchestration, autonomous self-improvement,
    end-to-end measurement substrate — at a scale where outcomes are
    unambiguous and continuously verifiable.
    """
)

st.markdown("---")

# ---------------------------------------------------------------------------
# Contact / Learn more
# ---------------------------------------------------------------------------

st.markdown("### Contact")

st.markdown(
    """
    - [GitHub](https://github.com/cipher813) — seven public repos
      covering every module
    - [Blog](https://nousergon.ai/blog) — long-form writing on what
      surfaced while building this
    """
)

st.markdown("---")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

render_footer()
