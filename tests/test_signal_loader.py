"""Tests for loaders/signal_loader.py — flattening and counting functions.

These test the pure data-transformation functions (no S3/Streamlit dependencies).
"""

import pandas as pd
import pytest

from loaders.signal_loader import (
    _extract_sub_scores,
    get_buy_candidates_df,
    get_sector_ratings_df,
    get_signal_counts,
    signals_to_df,
)


# ---------------------------------------------------------------------------
# _extract_sub_scores
# ---------------------------------------------------------------------------


class TestExtractSubScores:
    def test_nested_sub_scores(self):
        entry = {"sub_scores": {"technical": 80, "news": 60, "research": 70}}
        t, n, r = _extract_sub_scores(entry)
        assert t == 80
        assert n == 60
        assert r == 70

    def test_flat_keys(self):
        entry = {"technical": 75, "news": 65, "research": 55}
        t, n, r = _extract_sub_scores(entry)
        assert t == 75
        assert n == 65
        assert r == 55

    def test_empty_sub_scores_dict(self):
        entry = {"sub_scores": {}, "technical": 90}
        t, n, r = _extract_sub_scores(entry)
        assert t == 90

    def test_missing_all(self):
        entry = {"score": 80}
        t, n, r = _extract_sub_scores(entry)
        assert t is None
        assert n is None
        assert r is None


# ---------------------------------------------------------------------------
# signals_to_df
# ---------------------------------------------------------------------------


class TestSignalsToDf:
    def _make_signals(self, universe):
        return {"date": "2026-04-08", "universe": universe}

    def test_basic(self):
        universe = [
            {"ticker": "AAPL", "score": 82, "signal": "ENTER", "sector": "Technology"},
            {"ticker": "MSFT", "score": 75, "signal": "HOLD", "sector": "Technology"},
        ]
        df = signals_to_df(self._make_signals(universe))
        assert len(df) == 2
        assert "ticker" in df.columns
        assert df.iloc[0]["ticker"] == "AAPL"
        assert df.iloc[0]["score"] == 82

    def test_empty_universe(self):
        df = signals_to_df({"date": "2026-04-08", "universe": []})
        assert df.empty

    def test_none_input(self):
        df = signals_to_df(None)
        assert df.empty

    def test_no_universe_key(self):
        df = signals_to_df({"date": "2026-04-08"})
        assert df.empty

    def test_sub_scores_extracted(self):
        universe = [{"ticker": "GOOG", "sub_scores": {"technical": 85, "news": 70, "research": 75}}]
        df = signals_to_df(self._make_signals(universe))
        assert df.iloc[0]["technical"] == 85
        assert df.iloc[0]["news"] == 70

    def test_numeric_coercion(self):
        universe = [{"ticker": "AAPL", "score": "82.5", "price_target_upside": "0.15"}]
        df = signals_to_df(self._make_signals(universe))
        assert df.iloc[0]["score"] == pytest.approx(82.5)
        assert df.iloc[0]["price_target_upside"] == pytest.approx(0.15)

    def test_stale_default_false(self):
        universe = [{"ticker": "AAPL"}]
        df = signals_to_df(self._make_signals(universe))
        assert df.iloc[0]["stale"] == False


# ---------------------------------------------------------------------------
# get_buy_candidates_df
# ---------------------------------------------------------------------------


class TestGetBuyCandidatesDf:
    def test_basic(self):
        data = {"universe": [{"ticker": "NVDA", "score": 90, "signal": "ENTER"}]}
        df = get_buy_candidates_df(data)
        assert len(df) == 1
        assert df.iloc[0]["ticker"] == "NVDA"

    def test_none(self):
        assert get_buy_candidates_df(None).empty

    def test_empty(self):
        assert get_buy_candidates_df({"universe": []}).empty


# ---------------------------------------------------------------------------
# get_sector_ratings_df
# ---------------------------------------------------------------------------


class TestGetSectorRatingsDf:
    def test_dict_with_nested_values(self):
        data = {
            "sector_ratings": {
                "Technology": {"rating": "overweight", "rationale": "AI tailwinds"},
                "Healthcare": {"rating": "market_weight", "rationale": "Stable"},
            }
        }
        df = get_sector_ratings_df(data)
        assert len(df) == 2
        assert "sector" in df.columns
        assert "rating" in df.columns

    def test_dict_with_string_values(self):
        data = {"sector_ratings": {"Technology": "overweight", "Healthcare": "underweight"}}
        df = get_sector_ratings_df(data)
        assert len(df) == 2
        assert df.iloc[0]["rating"] == "overweight"

    def test_list_format(self):
        data = {"sector_ratings": [{"sector": "Tech", "rating": "OW"}]}
        df = get_sector_ratings_df(data)
        assert len(df) == 1

    def test_none(self):
        assert get_sector_ratings_df(None).empty

    def test_empty_dict(self):
        assert get_sector_ratings_df({"sector_ratings": {}}).empty


# ---------------------------------------------------------------------------
# get_signal_counts
# ---------------------------------------------------------------------------


class TestGetSignalCounts:
    def test_basic(self):
        data = {
            "universe": [
                {"ticker": "A", "signal": "ENTER"},
                {"ticker": "B", "signal": "ENTER"},
                {"ticker": "C", "signal": "HOLD"},
                {"ticker": "D", "signal": "EXIT"},
            ]
        }
        counts = get_signal_counts(data)
        assert counts["ENTER"] == 2
        assert counts["HOLD"] == 1
        assert counts["EXIT"] == 1
        assert counts["REDUCE"] == 0

    def test_none(self):
        counts = get_signal_counts(None)
        assert counts == {"ENTER": 0, "EXIT": 0, "REDUCE": 0, "HOLD": 0}

    def test_no_signals(self):
        counts = get_signal_counts({"universe": [{"ticker": "A"}]})
        assert counts["ENTER"] == 0
