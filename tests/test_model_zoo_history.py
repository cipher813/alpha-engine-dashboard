"""Tests for load_model_zoo_history — the multi-week promotion-summary
aggregator behind the Model Zoo console page. Mocks streamlit (cache_data
passthrough) before import, then patches the per-cycle loaders.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

# Passthrough cache decorators + no runtime, mirroring tests/test_s3_loader.py.
mock_st = MagicMock()
mock_st.cache_data = lambda **kwargs: (lambda f: f)
mock_st.cache_resource = lambda **kwargs: (lambda f: f)
sys.modules["streamlit"] = mock_st

from loaders import s3_loader  # noqa: E402

LEADERBOARDS = {
    "2026-06-13": {
        "date": "2026-06-13", "mode": "cutover",
        "promotion_baseline_ic": 0.120, "promotion_baseline_source": "champion_arch_fresh",
        "margin": 0.005, "winner_version_id": "spec-resmom-v2",
        "promoted": "spec-resmom-v2", "promoted_kind": "challenger", "reverted_from": None,
        "candidates": [
            {"spec_id": "spec-resmom", "version_id": "spec-resmom-v2", "group": "challenger",
             "cpcv_mean_ic": 0.140, "eligible": True},
            {"spec_id": "champ", "version_id": "champ-arch-v1", "group": "champion_arch",
             "cpcv_mean_ic": 0.120, "eligible": False},
        ],
        "selection_pbo": {"pbo": 0.10, "pbo_pass": True},
        "champion_realized_monitor": {"chasing_noise": False, "realized_rank_ic": 0.06},
    },
    "2026-06-06": {
        "date": "2026-06-06", "mode": "observe",
        "promotion_baseline_ic": 0.115, "winner_version_id": None,
        "promoted": None, "promoted_kind": None,
        "candidates": [
            {"spec_id": "champ", "version_id": "champ-arch-v0", "group": "champion_arch",
             "cpcv_mean_ic": 0.115, "eligible": False},
        ],
        "selection_pbo": {"pbo": 0.30, "pbo_pass": False},
        "champion_realized_monitor": {"chasing_noise": None},
    },
}


def _run(limit=26):
    with patch.object(s3_loader, "list_model_zoo_leaderboard_dates",
                      return_value=list(LEADERBOARDS)), \
         patch.object(s3_loader, "load_model_zoo_leaderboard",
                      side_effect=lambda d=None: LEADERBOARDS.get(d, {})):
        return s3_loader.load_model_zoo_history(limit=limit)


def test_newest_first_and_count():
    rows = _run(limit=10)
    assert [r["date"] for r in rows] == ["2026-06-13", "2026-06-06"]


def test_winner_ic_resolved_from_candidates():
    rows = _run(limit=11)
    promoted_cycle = next(r for r in rows if r["date"] == "2026-06-13")
    assert promoted_cycle["winner_ic"] == 0.140       # looked up by winner_version_id
    assert promoted_cycle["promoted_kind"] == "challenger"
    assert promoted_cycle["n_eligible"] == 1
    assert promoted_cycle["n_candidates"] == 2


def test_no_promotion_cycle_fields():
    rows = _run(limit=12)
    observe = next(r for r in rows if r["date"] == "2026-06-06")
    assert observe["promoted"] is None
    assert observe["winner_ic"] is None                # winner_version_id was None
    assert observe["pbo_pass"] is False
    assert observe["chasing_noise"] is None


def test_empty_when_no_dates():
    with patch.object(s3_loader, "list_model_zoo_leaderboard_dates", return_value=[]):
        assert s3_loader.load_model_zoo_history(limit=13) == []
