"""Tests for shared/position_pnl.py."""

import json

import pandas as pd
import pytest

from shared.position_pnl import enrich_positions, parse_positions_snapshot


class TestParsePositionsSnapshot:
    def test_valid_list_snapshot(self):
        positions = [
            {"ticker": "AAPL", "shares": 10, "market_value": 1500},
            {"ticker": "MSFT", "shares": 5, "market_value": 2000},
        ]
        eod_df = pd.DataFrame({
            "date": ["2026-04-08"],
            "positions_snapshot": [json.dumps(positions)],
        })
        result = parse_positions_snapshot(eod_df)
        assert result is not None
        assert len(result) == 2
        assert result.iloc[0]["ticker"] == "AAPL"

    def test_valid_dict_snapshot(self):
        position = {"ticker": "GOOG", "shares": 3, "market_value": 900}
        eod_df = pd.DataFrame({
            "date": ["2026-04-08"],
            "positions_snapshot": [json.dumps(position)],
        })
        result = parse_positions_snapshot(eod_df)
        assert result is not None
        assert len(result) == 1

    def test_none_eod(self):
        assert parse_positions_snapshot(None) is None

    def test_empty_eod(self):
        assert parse_positions_snapshot(pd.DataFrame()) is None

    def test_no_snapshot_column(self):
        eod_df = pd.DataFrame({"date": ["2026-04-08"], "nav": [100000]})
        assert parse_positions_snapshot(eod_df) is None

    def test_null_snapshot(self):
        eod_df = pd.DataFrame({
            "date": ["2026-04-08"],
            "positions_snapshot": [None],
        })
        assert parse_positions_snapshot(eod_df) is None

    def test_invalid_json(self):
        eod_df = pd.DataFrame({
            "date": ["2026-04-08"],
            "positions_snapshot": ["not-json"],
        })
        assert parse_positions_snapshot(eod_df) is None


class TestEnrichPositions:
    def _make_positions(self):
        return pd.DataFrame({
            "ticker": ["AAPL", "MSFT"],
            "shares": [10, 5],
            "market_value": [1500.0, 2000.0],
        })

    def test_no_enrichment(self):
        pos = self._make_positions()
        result = enrich_positions(pos)
        assert len(result) == 2
        assert "current_price" in result.columns
        assert result.iloc[0]["current_price"] == pytest.approx(150.0)

    def test_signal_merge(self):
        pos = self._make_positions()
        signals = pd.DataFrame({
            "ticker": ["AAPL", "MSFT"],
            "score": [82.0, 75.0],
            "signal": ["ENTER", "HOLD"],
            "conviction": ["rising", "stable"],
        })
        result = enrich_positions(pos, signals_df=signals)
        assert result.iloc[0]["score"] == 82.0
        assert result.iloc[1]["signal"] == "HOLD"

    def test_trade_merge(self):
        pos = self._make_positions()
        trades = pd.DataFrame({
            "ticker": ["AAPL", "AAPL", "MSFT"],
            "action": ["ENTER", "ENTER", "ENTER"],
            "date": ["2026-03-01", "2026-04-01", "2026-04-05"],
            "fill_price": [140.0, 145.0, 390.0],
        })
        result = enrich_positions(pos, trades_df=trades)
        assert "entry_price" in result.columns
        # Should pick the latest ENTER for AAPL (145.0)
        aapl = result[result["ticker"] == "AAPL"].iloc[0]
        assert aapl["entry_price"] == pytest.approx(145.0)

    def test_pnl_computation(self):
        pos = self._make_positions()
        trades = pd.DataFrame({
            "ticker": ["AAPL", "MSFT"],
            "action": ["ENTER", "ENTER"],
            "date": ["2026-04-01", "2026-04-01"],
            "fill_price": [140.0, 380.0],
        })
        result = enrich_positions(pos, trades_df=trades)
        aapl = result[result["ticker"] == "AAPL"].iloc[0]
        # current_price = 1500/10 = 150, entry = 140, unrealized = (150-140)*10 = 100
        assert aapl["unrealized_pnl"] == pytest.approx(100.0)
        assert aapl["return_pct"] == pytest.approx(150.0 / 140.0 - 1)

    def test_empty_signals(self):
        pos = self._make_positions()
        result = enrich_positions(pos, signals_df=pd.DataFrame())
        assert len(result) == 2

    def test_empty_trades(self):
        pos = self._make_positions()
        result = enrich_positions(pos, trades_df=pd.DataFrame())
        assert len(result) == 2
        assert "entry_price" not in result.columns
