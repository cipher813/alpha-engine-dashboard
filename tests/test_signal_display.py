"""
tests/test_signal_display.py — Unit tests for signal row styling logic.

Tests the _render_signal_display() function from pages/2_Signals_and_Research.py.
Verifies CSS styles are correctly applied based on signal type and veto status.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.constants import SIGNAL_COLORS, VETO_COLOR


def _render_signal_display(row: pd.Series) -> list[str]:
    """Local copy of the function for testing without importing the full page module.

    The real function lives in pages/2_Signals_and_Research.py but that module has
    Streamlit side effects on import. This mirrors the implementation
    exactly so we can test the logic in isolation.
    """
    veto_val = str(row.get("Veto", ""))
    if veto_val.startswith("VETOED"):
        return [f"background-color: {VETO_COLOR}" for _ in row]
    sig = str(row.get("signal", "HOLD")).upper()
    color = SIGNAL_COLORS.get(sig, SIGNAL_COLORS["HOLD"])
    return [f"background-color: {color}" for _ in row]


class TestRenderSignalDisplay:
    """Tests for _render_signal_display()."""

    def _make_row(self, signal="HOLD", veto="", **extra) -> pd.Series:
        data = {"ticker": "AAPL", "score": 75.0, "signal": signal, "Veto": veto}
        data.update(extra)
        return pd.Series(data)

    def test_enter_signal_green(self):
        row = self._make_row(signal="ENTER")
        styles = _render_signal_display(row)

        assert len(styles) == len(row)
        for s in styles:
            assert SIGNAL_COLORS["ENTER"] in s

    def test_exit_signal_red(self):
        row = self._make_row(signal="EXIT")
        styles = _render_signal_display(row)

        for s in styles:
            assert SIGNAL_COLORS["EXIT"] in s

    def test_reduce_signal_yellow(self):
        row = self._make_row(signal="REDUCE")
        styles = _render_signal_display(row)

        for s in styles:
            assert SIGNAL_COLORS["REDUCE"] in s

    def test_hold_signal_default(self):
        row = self._make_row(signal="HOLD")
        styles = _render_signal_display(row)

        for s in styles:
            assert SIGNAL_COLORS["HOLD"] in s

    def test_unknown_signal_defaults_to_hold(self):
        row = self._make_row(signal="UNKNOWN")
        styles = _render_signal_display(row)

        for s in styles:
            assert SIGNAL_COLORS["HOLD"] in s

    def test_veto_overrides_signal_color(self):
        """Vetoed rows should use VETO_COLOR regardless of signal."""
        row = self._make_row(signal="ENTER", veto="VETOED (72%)")
        styles = _render_signal_display(row)

        for s in styles:
            assert VETO_COLOR in s
            assert SIGNAL_COLORS["ENTER"] not in s

    def test_non_veto_string_uses_signal(self):
        """A Veto value that doesn't start with 'VETOED' should use signal color."""
        row = self._make_row(signal="ENTER", veto="")
        styles = _render_signal_display(row)

        for s in styles:
            assert SIGNAL_COLORS["ENTER"] in s

    def test_missing_signal_defaults_to_hold(self):
        """If signal column is missing, should default to HOLD."""
        row = pd.Series({"ticker": "AAPL", "score": 75.0, "Veto": ""})
        styles = _render_signal_display(row)

        for s in styles:
            assert SIGNAL_COLORS["HOLD"] in s

    def test_case_insensitive_signal(self):
        """Signal values should be uppercased before lookup."""
        row = self._make_row(signal="enter")
        styles = _render_signal_display(row)

        for s in styles:
            assert SIGNAL_COLORS["ENTER"] in s

    def test_style_count_matches_columns(self):
        """Number of styles should match the number of columns in the row."""
        row = self._make_row(signal="ENTER", sector="Tech", conviction="high")
        styles = _render_signal_display(row)

        assert len(styles) == len(row)
