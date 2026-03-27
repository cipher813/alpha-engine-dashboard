"""
tests/test_formatters.py — Unit tests for shared/formatters.py.

Tests format_pct, format_dollar, color_return, and regime_label
with various input types and edge cases.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.formatters import format_pct, format_dollar, color_return, regime_label
from shared.constants import POSITIVE_RETURN_CSS, NEGATIVE_RETURN_CSS


class TestFormatPct:
    """Tests for format_pct()."""

    def test_decimal_input(self):
        assert format_pct(0.052) == "+5.20%"

    def test_percent_input_auto_detects(self):
        """Values > 2 are treated as already in percent form."""
        assert format_pct(5.2) == "+5.20%"

    def test_negative_value(self):
        assert format_pct(-0.03) == "-3.00%"

    def test_negative_percent_form(self):
        assert format_pct(-3.0) == "-3.00%"

    def test_zero(self):
        assert format_pct(0) == "+0.00%"

    def test_custom_decimals(self):
        assert format_pct(0.052, decimals=1) == "+5.2%"

    def test_no_sign(self):
        assert format_pct(0.052, sign=False) == "5.20%"

    def test_negative_no_sign(self):
        result = format_pct(-0.03, sign=False)
        assert result == "-3.00%" or result == "−3.00%"

    def test_none_returns_dash(self):
        assert format_pct(None) == "—"

    def test_string_returns_dash(self):
        assert format_pct("not a number") == "—"

    def test_string_number(self):
        assert format_pct("0.05") == "+5.00%"

    def test_boundary_value_two(self):
        """Value of exactly 2.0 is treated as decimal (not percent)."""
        assert format_pct(2.0) == "+200.00%"

    def test_small_percent_value(self):
        """Value of 2.1 is treated as percent form (abs > 2)."""
        assert format_pct(2.1) == "+2.10%"

    def test_large_percent_value(self):
        assert format_pct(50) == "+50.00%"


class TestFormatDollar:
    """Tests for format_dollar()."""

    def test_positive(self):
        assert format_dollar(1234.5) == "$1,234.50"

    def test_negative(self):
        assert format_dollar(-500) == "$-500.00"

    def test_zero(self):
        assert format_dollar(0) == "$0.00"

    def test_large_value(self):
        assert format_dollar(1000000) == "$1,000,000.00"

    def test_small_value(self):
        assert format_dollar(0.5) == "$0.50"

    def test_none_returns_dash(self):
        assert format_dollar(None) == "—"

    def test_string_returns_dash(self):
        assert format_dollar("abc") == "—"

    def test_string_number(self):
        assert format_dollar("1234.56") == "$1,234.56"


class TestColorReturn:
    """Tests for color_return()."""

    def test_positive_return(self):
        result = color_return(0.05)
        assert result == POSITIVE_RETURN_CSS

    def test_negative_return(self):
        result = color_return(-0.03)
        assert result == NEGATIVE_RETURN_CSS

    def test_zero_returns_empty(self):
        assert color_return(0) == ""

    def test_none_returns_empty(self):
        assert color_return(None) == ""

    def test_string_returns_empty(self):
        assert color_return("abc") == ""

    def test_string_positive(self):
        assert color_return("0.05") == POSITIVE_RETURN_CSS

    def test_very_small_positive(self):
        assert color_return(0.0001) == POSITIVE_RETURN_CSS


class TestRegimeLabel:
    """Tests for regime_label()."""

    def test_bull(self):
        result = regime_label("bull")
        assert "🐂" in result
        assert "Bull" in result

    def test_bear(self):
        result = regime_label("bear")
        assert "🐻" in result
        assert "Bear" in result

    def test_neutral(self):
        result = regime_label("neutral")
        assert "Neutral" in result

    def test_caution(self):
        result = regime_label("caution")
        assert "⚠️" in result

    def test_case_insensitive(self):
        result = regime_label("BULL")
        assert "🐂" in result
        assert "Bull" in result

    def test_unknown_regime(self):
        result = regime_label("unknown")
        assert "📊" in result
        assert "Unknown" in result

    def test_empty_string(self):
        result = regime_label("")
        assert "📊" in result
