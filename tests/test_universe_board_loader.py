"""Cross-repo consumer-contract test for the Universe Board page.

Pins the dashboard's contract with crucible-research ``scoring/universe_board.py``
(artifact ``scanner/universe/latest.json``, ``schema_version=1``): the page's
flatten transform MUST correctly consume the producer's exact field names
(``attractiveness_score``, ``pillars.<pillar>``, ``metrics.<metric>``,
``gate.quant_filter_pass``, ``country``). A producer/consumer drift here would
silently blank columns on the board.

The fixture below mirrors a record EXACTLY as the producer emits it (see
crucible-research ``tests/test_universe_board.py``). ``loaders/universe_board.py``
is pure pandas (no Streamlit) so this runs without mocking the UI.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from loaders.universe_board import PILLARS, flatten_board  # noqa: E402


def _producer_board() -> dict:
    """A schema_version=1 board as crucible-research scoring/universe_board.py emits it."""
    return {
        "schema_version": 1,
        "as_of": "2026-06-28",
        "universe_count": 2,
        "attractiveness_method": "equal_weight_available_pillars",
        "pillars": list(PILLARS),
        "stocks": [
            {
                "ticker": "AAPL",
                "sector": "Information Technology",
                "country": "United States",
                "industry": "Consumer Electronics",
                "attractiveness_score": 69.17,
                "pillars": {"quality": 90.0, "value": 30.0, "momentum": 85.0,
                            "growth": 80.0, "stewardship": 70.0, "defensiveness": 60.0},
                "pillar_coverage": {"quality": 4, "momentum": 5},
                "focus_score": 80.0, "focus_stance": "momentum", "tech_score": 72.0,
                "gate": {"quant_filter_pass": 1, "filter_fail_reason": None},
                "metrics": {
                    "current_price": 195.0, "market_cap": 3.0e12, "pe": 30.0, "pb": 40.0,
                    "fcf_yield": 0.04, "dividend_yield": 0.005, "debt_to_equity": 1.5,
                    "current_ratio": 1.2, "payout_ratio": 0.15, "roe": 1.5, "gross_margin": 0.44,
                    "revenue_growth_3y": 0.08, "eps_growth_3y": 0.10, "rsi_14": 58.0,
                    "momentum_20d": 0.03, "return_60d": 0.08, "return_120d": 0.12,
                    "realized_vol_20d": 0.22, "atr_pct": 0.015, "dist_from_52w_high": -0.04,
                    "price_vs_ma200": 0.10, "beta": 1.2, "avg_volume": 55_000_000.0,
                },
            },
            {
                # Rejected, Ireland-domiciled, partial pillar coverage, sparse metrics.
                "ticker": "LIN",
                "sector": "Materials",
                "country": "Ireland",
                "industry": "Specialty Chemicals",
                "attractiveness_score": 45.0,
                "pillars": {"quality": 50.0, "value": 40.0, "momentum": 30.0,
                            "growth": None, "stewardship": None, "defensiveness": 60.0},
                "pillar_coverage": {"quality": 4},
                "focus_score": 55.0, "focus_stance": "quality", "tech_score": 40.0,
                "gate": {"quant_filter_pass": 0, "filter_fail_reason": "liquidity"},
                "metrics": {"current_price": 460.0, "pe": 36.0},
            },
        ],
    }


def test_flatten_consumes_producer_fields():
    df = flatten_board(_producer_board())
    assert len(df) == 2
    aapl = df.set_index("ticker").loc["AAPL"]
    # Attractiveness + a pillar + a denormalized metric + gate all land.
    assert aapl["attractiveness"] == 69.17
    assert aapl["quality"] == 90.0
    assert aapl["pe"] == 30.0
    assert aapl["country"] == "United States"
    assert aapl["gate"] == "PASS"
    assert aapl["mkt_cap"] == 3.0e12


def test_partial_coverage_and_missing_metrics_degrade_to_nan():
    df = flatten_board(_producer_board()).set_index("ticker")
    lin = df.loc["LIN"]
    assert lin["gate"] == "FAIL"
    assert lin["fail_reason"] == "liquidity"
    assert lin["country"] == "Ireland"
    # Null pillar + absent metric → NaN (a coverage gap, never fabricated).
    assert lin["growth"] != lin["growth"]   # NaN
    assert lin["roe"] != lin["roe"]         # NaN (metric absent from LIN)


def test_every_pillar_column_present():
    df = flatten_board(_producer_board())
    for p in PILLARS:
        assert p in df.columns


def test_empty_board_yields_empty_frame():
    assert flatten_board({"stocks": []}).empty
    assert flatten_board(None).empty


def test_loader_reads_pinned_latest_key():
    """The loader must read the producer's exact artifact key. A drift here
    silently shows an empty board."""
    src = (REPO_ROOT / "loaders" / "s3_loader.py").read_text()
    assert "scanner/universe/latest.json" in src
    assert "scanner/universe/{date_str}/universe.json" in src


def test_page_registered_in_nav():
    app_src = (REPO_ROOT / "app.py").read_text()
    assert "39_Universe_Board.py" in app_src
    assert (REPO_ROOT / "views" / "39_Universe_Board.py").exists()
