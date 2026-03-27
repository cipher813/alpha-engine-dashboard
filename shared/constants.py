"""
Shared constants for the Alpha Engine Dashboard.

Centralizes signal colors, regime labels, cache defaults, and column schemas
to eliminate duplication across pages and loaders.
"""

import re

# ---------------------------------------------------------------------------
# Signal display
# ---------------------------------------------------------------------------

SIGNAL_COLORS = {
    "ENTER": "#d4edda",
    "EXIT": "#f8d7da",
    "REDUCE": "#fff3cd",
    "HOLD": "#f8f9fa",
}

VETO_COLOR = "#f5c6cb"

REGIME_EMOJI = {
    "bull": "🐂",
    "bear": "🐻",
    "neutral": "➡️",
    "caution": "⚠️",
}
REGIME_EMOJI_DEFAULT = "📊"

# ---------------------------------------------------------------------------
# Return styling (CSS)
# ---------------------------------------------------------------------------

POSITIVE_RETURN_CSS = "color: #155724; background-color: #d4edda"
NEGATIVE_RETURN_CSS = "color: #721c24; background-color: #f8d7da"

# ---------------------------------------------------------------------------
# S3 / cache defaults
# ---------------------------------------------------------------------------

DEFAULT_CACHE_TTL_SECONDS = 900

ISO_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")

# ---------------------------------------------------------------------------
# Positions display columns (ordered for UI tables)
# ---------------------------------------------------------------------------

POSITION_DISPLAY_COLUMNS = [
    "ticker", "sector", "shares", "entry_price", "current_price",
    "unrealized_pnl", "return_pct", "days_held", "score", "signal",
]
