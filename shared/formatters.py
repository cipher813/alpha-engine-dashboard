"""
Shared formatting utilities for the Alpha Engine Dashboard.

Provides consistent number formatting across all pages and the home app.
"""

from shared.constants import POSITIVE_RETURN_CSS, NEGATIVE_RETURN_CSS, REGIME_EMOJI, REGIME_EMOJI_DEFAULT


def format_pct(val, decimals: int = 2, sign: bool = True) -> str:
    """Format a value as a percentage string.

    Auto-detects scale: values with abs > 2 are treated as already in
    percent form (e.g. 5.2 → 5.20%), otherwise as decimal (e.g. 0.052 → 5.20%).
    """
    try:
        v = float(val)
        if abs(v) > 2:
            v = v / 100
        pct = v * 100
        return f"{pct:+.{decimals}f}%" if sign else f"{pct:.{decimals}f}%"
    except (ValueError, TypeError):
        return "—"


def format_dollar(val) -> str:
    """Format a numeric value as a dollar amount (e.g. $1,234.56)."""
    try:
        return f"${float(val):,.2f}"
    except (ValueError, TypeError):
        return "—"


def color_return(val) -> str:
    """Return a CSS style string for positive/negative return values.

    Suitable for use with pandas Styler.map().
    """
    try:
        v = float(val)
        if v > 0:
            return POSITIVE_RETURN_CSS
        elif v < 0:
            return NEGATIVE_RETURN_CSS
    except (ValueError, TypeError):
        pass
    return ""


def regime_label(regime: str) -> str:
    """Return an emoji-prefixed regime label (e.g. '🐂 Bull')."""
    emoji = REGIME_EMOJI.get(str(regime).lower(), REGIME_EMOJI_DEFAULT)
    return f"{emoji} {str(regime).title()}"
