"""Tests for shared/position_pnl.py."""

import json

import pandas as pd
import pytest

from shared.position_pnl import (
    compute_position_lifecycles,
    enrich_positions,
    parse_positions_snapshot,
)


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


# ── compute_position_lifecycles (ROADMAP L137) ────────────────────────────


class TestPositionLifecycles:
    def _make_trades(self, rows: list[dict]) -> pd.DataFrame:
        cols = [
            "trade_id", "date", "ticker", "action", "shares", "fill_price",
            "sector", "entry_trade_id", "realized_pnl",
            "realized_return_pct", "realized_alpha_pct",
        ]
        norm = []
        for r in rows:
            row = {c: r.get(c) for c in cols}
            norm.append(row)
        return pd.DataFrame(norm)

    def test_empty_trades_returns_empty(self):
        result = compute_position_lifecycles(None)
        assert result.empty
        result = compute_position_lifecycles(pd.DataFrame())
        assert result.empty

    def test_entry_without_exits_status_open(self):
        trades = self._make_trades([
            {"trade_id": "T1", "date": "2026-04-15", "ticker": "AAPL",
             "action": "ENTER", "shares": 100, "fill_price": 150.0,
             "sector": "Tech"},
        ])
        result = compute_position_lifecycles(trades)
        assert len(result) == 1
        row = result.iloc[0]
        assert row["status"] == "open"
        assert row["ticker"] == "AAPL"
        assert row["sector"] == "Tech"
        assert row["entry_price"] == 150.0
        assert row["shares_entered"] == 100
        assert row["n_exits"] == 0
        assert row["total_realized_pnl"] == 0.0
        assert pd.isna(row["exit_date"])

    def test_closed_position_collapses_single_exit(self):
        trades = self._make_trades([
            {"trade_id": "T1", "date": "2026-04-15", "ticker": "AAPL",
             "action": "ENTER", "shares": 100, "fill_price": 150.0,
             "sector": "Tech"},
            {"trade_id": "T2", "date": "2026-05-08", "ticker": "AAPL",
             "action": "EXIT", "shares": 100, "fill_price": 165.0,
             "entry_trade_id": "T1", "realized_pnl": 1500.0,
             "realized_return_pct": 0.10, "realized_alpha_pct": 0.06},
        ])
        result = compute_position_lifecycles(trades)
        assert len(result) == 1
        row = result.iloc[0]
        assert row["status"] == "closed"
        assert row["n_exits"] == 1
        assert row["total_realized_pnl"] == 1500.0
        assert row["holding_days"] == 23  # 4/15 → 5/08
        assert row["total_realized_return_pct"] == pytest.approx(0.10)
        assert row["total_realized_alpha_pct"] == pytest.approx(0.06)

    def test_partial_exit_marks_open_partial(self):
        trades = self._make_trades([
            {"trade_id": "T1", "date": "2026-04-15", "ticker": "MSFT",
             "action": "ENTER", "shares": 100, "fill_price": 300.0},
            {"trade_id": "T2", "date": "2026-04-30", "ticker": "MSFT",
             "action": "REDUCE", "shares": 50, "fill_price": 320.0,
             "entry_trade_id": "T1", "realized_pnl": 1000.0,
             "realized_return_pct": 0.067, "realized_alpha_pct": 0.04},
        ])
        result = compute_position_lifecycles(trades)
        assert len(result) == 1
        row = result.iloc[0]
        assert row["status"] == "open_partial"
        assert row["n_exits"] == 1
        assert row["total_realized_pnl"] == 1000.0
        # exit_date / holding_days only populated on `closed`
        assert pd.isna(row["exit_date"])
        assert row["holding_days"] is None

    def test_multiple_exits_aggregate_pnl_and_weight_pct(self):
        trades = self._make_trades([
            {"trade_id": "T1", "date": "2026-04-15", "ticker": "GOOG",
             "action": "ENTER", "shares": 100, "fill_price": 100.0},
            # Two partial exits: 40 sh at +10%, 60 sh at +20%
            {"trade_id": "T2", "date": "2026-04-25", "ticker": "GOOG",
             "action": "REDUCE", "shares": 40, "fill_price": 110.0,
             "entry_trade_id": "T1", "realized_pnl": 400.0,
             "realized_return_pct": 0.10, "realized_alpha_pct": 0.05},
            {"trade_id": "T3", "date": "2026-05-05", "ticker": "GOOG",
             "action": "EXIT", "shares": 60, "fill_price": 120.0,
             "entry_trade_id": "T1", "realized_pnl": 1200.0,
             "realized_return_pct": 0.20, "realized_alpha_pct": 0.12},
        ])
        result = compute_position_lifecycles(trades)
        assert len(result) == 1
        row = result.iloc[0]
        assert row["status"] == "closed"
        assert row["n_exits"] == 2
        assert row["total_realized_pnl"] == pytest.approx(1600.0)
        # Weighted by shares: (0.10 × 40 + 0.20 × 60) / 100 = 0.16
        assert row["total_realized_return_pct"] == pytest.approx(0.16)
        # Weighted alpha: (0.05 × 40 + 0.12 × 60) / 100 = 0.092
        assert row["total_realized_alpha_pct"] == pytest.approx(0.092)
        assert row["holding_days"] == 20  # 4/15 → 5/05

    def test_unrelated_exit_does_not_match_other_entry(self):
        """An EXIT pointing to a DIFFERENT entry_trade_id must not leak
        into another entry's lifecycle.
        """
        trades = self._make_trades([
            {"trade_id": "T1", "date": "2026-04-15", "ticker": "AAPL",
             "action": "ENTER", "shares": 50, "fill_price": 150.0},
            {"trade_id": "T2", "date": "2026-04-15", "ticker": "MSFT",
             "action": "ENTER", "shares": 50, "fill_price": 300.0},
            {"trade_id": "T3", "date": "2026-05-01", "ticker": "MSFT",
             "action": "EXIT", "shares": 50, "fill_price": 310.0,
             "entry_trade_id": "T2", "realized_pnl": 500.0},
        ])
        result = compute_position_lifecycles(trades)
        # AAPL still open with zero P&L; MSFT closed at 500.
        aapl = result[result["ticker"] == "AAPL"].iloc[0]
        msft = result[result["ticker"] == "MSFT"].iloc[0]
        assert aapl["status"] == "open"
        assert aapl["total_realized_pnl"] == 0.0
        assert msft["status"] == "closed"
        assert msft["total_realized_pnl"] == 500.0

    def test_lifecycles_sorted_by_entry_date_descending(self):
        trades = self._make_trades([
            {"trade_id": "T1", "date": "2026-03-15", "ticker": "OLD",
             "action": "ENTER", "shares": 10, "fill_price": 100.0},
            {"trade_id": "T2", "date": "2026-05-15", "ticker": "NEW",
             "action": "ENTER", "shares": 10, "fill_price": 200.0},
        ])
        result = compute_position_lifecycles(trades)
        # Most recent entry first
        assert result.iloc[0]["ticker"] == "NEW"
        assert result.iloc[1]["ticker"] == "OLD"

    def test_missing_entry_trade_id_column_treats_entries_as_open(self):
        """If `entry_trade_id` column is absent (e.g. very-old trades.db
        before the 2026-03-27 migration), every ENTER reads as `open`."""
        trades = pd.DataFrame([
            {"trade_id": "T1", "date": "2026-04-15", "ticker": "AAPL",
             "action": "ENTER", "shares": 100, "fill_price": 150.0,
             "sector": "Tech"},
            {"trade_id": "T2", "date": "2026-05-08", "ticker": "AAPL",
             "action": "EXIT", "shares": 100, "fill_price": 165.0,
             # NOTE: no entry_trade_id column present in the DataFrame
             "sector": "Tech"},
        ])
        result = compute_position_lifecycles(trades)
        # Only one entry record; status open because no linkage column.
        entries = result[result["status"] == "open"]
        assert len(entries) == 1
