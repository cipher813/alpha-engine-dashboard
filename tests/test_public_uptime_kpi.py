"""Tests for public/components/uptime_kpi aggregation."""

from __future__ import annotations

import os
import sys

import pytest

_PUBLIC = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public")
if _PUBLIC not in sys.path:
    sys.path.insert(0, _PUBLIC)

# Skip the whole module if streamlit isn't installed in the test env.
pytest.importorskip("streamlit")

from components.uptime_kpi import _aggregate, _progress_bar_html  # noqa: E402


def test_aggregate_sums_across_records():
    records = [
        {"connected_minutes": 390, "market_minutes": 390, "crashes": 0},
        {"connected_minutes": 200, "market_minutes": 390, "crashes": 2},
        {"connected_minutes": 390, "market_minutes": 390, "crashes": 0},
    ]
    agg = _aggregate(records)
    assert agg["connected_minutes"] == 980
    assert agg["market_minutes"] == 1170
    assert agg["crashes"] == 2
    assert agg["sessions"] == 3
    assert round(agg["uptime_pct"], 2) == round(980 / 1170 * 100, 2)


def test_aggregate_handles_empty_records():
    agg = _aggregate([])
    assert agg["connected_minutes"] == 0
    assert agg["market_minutes"] == 0
    assert agg["uptime_pct"] == 0.0
    assert agg["sessions"] == 0


def test_aggregate_handles_missing_fields():
    # Partial records should not raise
    agg = _aggregate([{"date": "2026-04-13"}])
    assert agg["uptime_pct"] == 0.0
    assert agg["sessions"] == 1


def test_progress_bar_clamps_and_renders_target():
    html = _progress_bar_html(150.0)
    # Clamped to 100 in the fill bar, but the label still shows 150.0
    assert "100.0%" in html
    assert "99% target" in html


def test_progress_bar_below_target_uses_blue():
    html = _progress_bar_html(80.0)
    assert "#5fa8f0" in html


def test_progress_bar_at_or_above_target_uses_green():
    html = _progress_bar_html(99.5)
    assert "#7fd17f" in html
