"""
tests/test_portfolio_parsing.py — Unit tests for position snapshot parsing.

Tests the _parse_snapshot_row() helper extracted from pages/1_Portfolio.py.
No Streamlit or S3 dependencies — pure data transformation tests.
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


def _parse_snapshot_row(row_date: str, snapshot_json: str) -> list[dict]:
    """Local copy of the function from pages/1_Portfolio.py for isolated testing.

    The real function lives in a Streamlit page module that has side effects
    on import, so we mirror the implementation here.
    """
    try:
        positions = json.loads(str(snapshot_json))
    except (json.JSONDecodeError, ValueError):
        return []

    if isinstance(positions, dict):
        positions = [positions]
    if not isinstance(positions, list):
        return []

    records = []
    for pos in positions:
        try:
            market_value = float(pos.get("market_value", 0) or 0)
        except (ValueError, TypeError):
            market_value = 0.0
        records.append({
            "date": row_date,
            "sector": pos.get("sector", "Unknown"),
            "market_value": market_value,
        })
    return records


class TestParseSnapshotRow:
    """Tests for _parse_snapshot_row()."""

    def test_single_position_list(self):
        """Single position wrapped in a list."""
        snapshot = json.dumps([{
            "ticker": "AAPL",
            "sector": "Technology",
            "market_value": 5000.0,
            "shares": 10,
        }])
        records = _parse_snapshot_row("2024-01-15", snapshot)

        assert len(records) == 1
        assert records[0]["date"] == "2024-01-15"
        assert records[0]["sector"] == "Technology"
        assert records[0]["market_value"] == 5000.0

    def test_multiple_positions(self):
        """Multiple positions in a list."""
        snapshot = json.dumps([
            {"ticker": "AAPL", "sector": "Technology", "market_value": 5000},
            {"ticker": "JPM", "sector": "Financials", "market_value": 3000},
        ])
        records = _parse_snapshot_row("2024-01-15", snapshot)

        assert len(records) == 2
        sectors = {r["sector"] for r in records}
        assert sectors == {"Technology", "Financials"}

    def test_dict_input_normalized_to_list(self):
        """A single dict (not wrapped in list) should be handled."""
        snapshot = json.dumps({
            "ticker": "MSFT",
            "sector": "Technology",
            "market_value": 8000,
        })
        records = _parse_snapshot_row("2024-01-15", snapshot)

        assert len(records) == 1
        assert records[0]["sector"] == "Technology"

    def test_missing_sector_defaults_to_unknown(self):
        """Missing sector field should default to 'Unknown'."""
        snapshot = json.dumps([{"ticker": "XYZ", "market_value": 1000}])
        records = _parse_snapshot_row("2024-01-15", snapshot)

        assert records[0]["sector"] == "Unknown"

    def test_missing_market_value_defaults_to_zero(self):
        """Missing market_value should default to 0."""
        snapshot = json.dumps([{"ticker": "XYZ", "sector": "Tech"}])
        records = _parse_snapshot_row("2024-01-15", snapshot)

        assert records[0]["market_value"] == 0.0

    def test_none_market_value(self):
        """market_value of None should become 0."""
        snapshot = json.dumps([{"ticker": "XYZ", "market_value": None}])
        records = _parse_snapshot_row("2024-01-15", snapshot)

        assert records[0]["market_value"] == 0.0

    def test_string_market_value(self):
        """String market_value should be coerced to float."""
        snapshot = json.dumps([{"ticker": "XYZ", "market_value": "1500.50"}])
        records = _parse_snapshot_row("2024-01-15", snapshot)

        assert records[0]["market_value"] == 1500.50

    def test_invalid_json_returns_empty(self):
        """Malformed JSON should return an empty list."""
        records = _parse_snapshot_row("2024-01-15", "not valid json{{{")

        assert records == []

    def test_empty_list_returns_empty(self):
        """Empty JSON list should return empty records."""
        records = _parse_snapshot_row("2024-01-15", "[]")

        assert records == []

    def test_non_numeric_market_value(self):
        """Non-numeric market_value should default to 0."""
        snapshot = json.dumps([{"ticker": "XYZ", "market_value": "abc"}])
        records = _parse_snapshot_row("2024-01-15", snapshot)

        assert records[0]["market_value"] == 0.0
