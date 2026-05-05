"""Tests for public/components/landing_intro narrative content.

Locks the structural shape of the landing-page intro: the four pillars
exist, headlines stay on-message, and the agentic-engineering framing
isn't accidentally swapped back to a returns-first pitch.
"""

from __future__ import annotations

import os
import sys

import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

pytest.importorskip("streamlit")

from components import landing_intro  # noqa: E402


def test_four_pillars_present():
    titles = [t for t, _ in landing_intro._PILLARS]
    assert len(titles) == 4
    assert "Multi-agent orchestration" in titles
    assert "Machine-learning overlay" in titles
    assert "Self-improvement loop" in titles
    assert "End-to-end measurement" in titles


def test_self_improvement_pillar_describes_mechanism_not_returns():
    body = dict(landing_intro._PILLARS)["Self-improvement loop"]
    # Autonomy is now a Phase 1 receipt (the backtester→S3-config feedback
    # loop is shipped); the pillar describes the mechanism rather than
    # framing autonomy as future work. Still must not lead with returns.
    forbidden = ["alpha", "outperform", "beating", "profit", "returns vs"]
    leaked = [t for t in forbidden if t in body.lower()]
    assert not leaked, (
        f"Self-improvement pillar must not lean on returns-flavored "
        f"framing; found: {leaked}"
    )
    # Honesty floor: the pillar should describe mechanism (configs / params /
    # parameter updates etc.), not claim outcomes (alpha generation).
    mechanism_words = ["config", "parameter", "tune", "evaluation", "loop"]
    assert any(w in body.lower() for w in mechanism_words), (
        "Self-improvement pillar must describe the mechanism (configs, "
        "parameter updates, evaluation loop), not just claim self-improvement."
    )


def test_hero_does_not_lead_with_returns():
    text = (landing_intro._HERO_ONELINER + " " + landing_intro._MISSION).lower()
    forbidden = ["alpha", "outperform", "beating", "returns vs", "profit"]
    leaked = [term for term in forbidden if term in text]
    assert not leaked, (
        f"Landing copy must not lead with returns-flavored language; "
        f"found: {leaked}"
    )
