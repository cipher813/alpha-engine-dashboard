"""Tests for public/components/landing_intro narrative content.

Locks the structural shape of the landing-page intro: the four pillars
exist, headlines stay on-message, and the agentic-engineering framing
isn't accidentally swapped back to a returns-first pitch.
"""

from __future__ import annotations

import os
import sys

import pytest

_PUBLIC = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public")
if _PUBLIC not in sys.path:
    sys.path.insert(0, _PUBLIC)

pytest.importorskip("streamlit")

from components import landing_intro  # noqa: E402


def test_four_pillars_present():
    titles = [t for t, _ in landing_intro._PILLARS]
    assert len(titles) == 4
    assert "Multi-agent orchestration" in titles
    assert "Machine-learning overlay" in titles
    assert "Self-improvement loop" in titles
    assert "End-to-end measurement" in titles


def test_self_improvement_pillar_keeps_phase_2_honesty():
    body = dict(landing_intro._PILLARS)["Self-improvement loop"]
    assert "Phase 2" in body, (
        "Self-improvement pillar must explicitly frame full autonomy as the "
        "Phase 2 deliverable, not as a current-state claim"
    )


def test_hero_does_not_lead_with_returns():
    text = (landing_intro._HERO_ONELINER + " " + landing_intro._MISSION).lower()
    forbidden = ["alpha", "outperform", "beating", "returns vs", "profit"]
    leaked = [term for term in forbidden if term in text]
    assert not leaked, (
        f"Landing copy must not lead with returns-flavored language; "
        f"found: {leaked}"
    )
