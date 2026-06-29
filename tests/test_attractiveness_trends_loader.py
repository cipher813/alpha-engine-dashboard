"""Cross-repo consumer-contract test for the Attractiveness Trends page.

Pins the dashboard's contract with crucible-research
``scoring/attractiveness_trajectory.py`` (``scanner/universe/trajectory/latest.json``,
``schema_version=1``) + the attractiveness-history parquet. A producer/consumer
field drift here would silently blank the leaderboards or the per-stock chart.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from loaders.attractiveness_trends import (  # noqa: E402
    TRAJECTORY_COLS,
    flatten_trajectory,
    pre_repricing_table,
    rising_table,
    ticker_series,
    trajectory_meta,
)


def _artifact() -> dict:
    """A schema_version=1 trajectory as the producer emits it."""
    return {
        "schema_version": 1,
        "as_of": "2026-06-26",
        "window_weeks": 8,
        "method": "theilsen_slope_orthogonalized_residual",
        "orthogonalization_beta": 0.31,
        "n_universe": 3,
        "n_rising": 2,
        "n_pre_repricing": 1,
        "provisional_ic": None,
        "stocks": [
            {"ticker": "KNF", "sector": "Industrials", "attr_slope": 0.214, "attr_slope_z": 3.04,
             "n_points": 7, "slope_significant": True, "price_ret": 0.01,
             "sector_rel_price_ret": -0.04, "price_mom_z": -1.2, "pre_repricing_score": 3.04,
             "rising": True, "pre_repricing": True, "rising_rank": 1, "pre_repricing_rank": 1},
            {"ticker": "MSFT", "sector": "Information Technology", "attr_slope": 0.05,
             "attr_slope_z": 0.8, "n_points": 7, "slope_significant": True, "price_ret": 0.12,
             "sector_rel_price_ret": 0.06, "price_mom_z": 1.5, "pre_repricing_score": -0.2,
             "rising": True, "pre_repricing": False, "rising_rank": 2, "pre_repricing_rank": 2},
            {"ticker": "XOM", "sector": "Energy", "attr_slope": -0.10, "attr_slope_z": -1.4,
             "n_points": 7, "slope_significant": True, "price_ret": -0.02,
             "sector_rel_price_ret": 0.0, "price_mom_z": 0.1, "pre_repricing_score": -1.4,
             "rising": False, "pre_repricing": False, "rising_rank": None, "pre_repricing_rank": 3},
        ],
    }


def _history() -> pd.DataFrame:
    rows = []
    for d, raw, score in [("2026-06-12", -0.5, 20.0), ("2026-06-19", 0.1, 55.0),
                          ("2026-06-26", 0.6, 92.0)]:
        rows.append({"as_of": d, "ticker": "KNF", "attractiveness_raw": raw,
                     "attractiveness_score": score, "sector": "Industrials"})
    return pd.DataFrame(rows)


def test_meta_surfaces_method_and_counts():
    m = trajectory_meta(_artifact())
    assert m["method"] == "theilsen_slope_orthogonalized_residual"
    assert m["window_weeks"] == 8 and m["n_pre_repricing"] == 1
    assert m["orthogonalization_beta"] == 0.31


def test_flatten_consumes_producer_fields():
    df = flatten_trajectory(_artifact())
    assert list(df.columns) == TRAJECTORY_COLS
    knf = df.set_index("ticker").loc["KNF"]
    assert knf["pre_repricing_score"] == 3.04 and knf["pre_repricing"] == True  # noqa: E712
    assert knf["sector_rel_price_ret"] == -0.04


def test_leaderboards_filter_and_order():
    df = flatten_trajectory(_artifact())
    pre = pre_repricing_table(df)
    assert list(pre["ticker"]) == ["KNF"]              # only the pre-repricing pick
    rising = rising_table(df)
    assert list(rising["ticker"]) == ["KNF", "MSFT"]   # by rising_rank, XOM excluded


def test_ticker_series_for_chart():
    s = ticker_series(_history(), "KNF")
    assert list(s.columns) == ["attractiveness_score", "attractiveness_raw"]
    assert len(s) == 3 and s.index.is_monotonic_increasing
    assert s["attractiveness_score"].iloc[-1] == 92.0
    # absent ticker → empty
    assert ticker_series(_history(), "NOPE").empty


def test_empty_artifact_safe():
    assert flatten_trajectory({"stocks": []}).empty
    assert flatten_trajectory(None).empty
    assert ticker_series(pd.DataFrame(), "KNF").empty


def test_loader_reads_pinned_keys():
    src = (REPO_ROOT / "loaders" / "s3_loader.py").read_text()
    assert "scanner/universe/trajectory/latest.json" in src
    assert "scanner/universe/trajectory/{date_str}/trajectory.json" in src
    assert "scanner/universe/history/attractiveness_history.parquet" in src
