"""Tests for load_optimizer_risk_history in loaders/s3_loader.py.

Sources the daily optimizer shadow log (predictor/optimizer_shadow/{date}.json).
Mirrors the fresh-import + mocked-S3 pattern of tests/test_news_articles_loader.py.
Verifies: flatten optimizer_cfg + diagnostics, skip latest.json + replays/,
tolerate empty/error.
"""

import sysconfig
from unittest.mock import MagicMock, patch

# Warm sysconfig's config-var cache BEFORE any test patches builtins.open — a
# cold import under the patched-open helper below otherwise trips macOS
# _osx_support (re.search on a MagicMock plist read).
sysconfig.get_config_vars()

_MOCK_CONFIG = {
    "s3": {"research_bucket": "test-bucket", "trades_bucket": "test-bucket"},
    "cache_ttl": {"signals": 900, "trades": 900, "research": 3600, "backtest": 3600},
    "paths": {"signals": "signals/{date}/signals.json", "research_db": "research.db"},
}


def _import_s3_loader():
    import sys
    if "loaders.s3_loader" in sys.modules:
        del sys.modules["loaders.s3_loader"]
    with patch("builtins.open", MagicMock()):
        with patch("yaml.safe_load", return_value=_MOCK_CONFIG):
            from loaders import s3_loader
            return s3_loader


def _client_for(keys):
    client = MagicMock()
    client.list_objects_v2.return_value = {"Contents": [{"Key": k} for k in keys]}
    return client


def _shadow_doc(date, risk_aversion=5.0, vol=0.15):
    return {
        "run_date": date,
        "shadow_status": "ok",
        "portfolio_nav": 1_000_000.0,
        "n_tickers": 30,
        "optimizer_cfg": {"risk_aversion": risk_aversion, "tcost_bps": 5.0,
                          "covariance_shrinkage": "ledoit_wolf", "vol_target_annual": None},
        "diagnostics": {"portfolio_vol_ann": vol, "active_share_vs_spy": 0.68,
                        "turnover_one_way": 0.12, "n_active_positions": 10},
    }


class TestLoadOptimizerRiskHistory:
    def test_flattens_cfg_and_diagnostics_in_date_order(self):
        mod = _import_s3_loader()
        keys = [
            "predictor/optimizer_shadow/2026-06-15.json",
            "predictor/optimizer_shadow/2026-06-12.json",
        ]
        docs = {
            "predictor/optimizer_shadow/2026-06-12.json": _shadow_doc("2026-06-12", 5.0, 0.14),
            "predictor/optimizer_shadow/2026-06-15.json": _shadow_doc("2026-06-15", 4.0, 0.18),
        }
        with patch.object(mod, "get_s3_client", return_value=_client_for(keys)):
            with patch.object(mod, "_fetch_s3_json", side_effect=lambda b, k: docs.get(k)):
                out = mod.load_optimizer_risk_history()
        assert [r["run_date"] for r in out] == ["2026-06-12", "2026-06-15"]
        # levers flattened from optimizer_cfg
        assert out[1]["risk_aversion"] == 4.0
        assert out[1]["covariance_shrinkage"] == "ledoit_wolf"
        # metrics flattened from diagnostics
        assert out[1]["portfolio_vol_ann"] == 0.18
        assert out[1]["n_active_positions"] == 10
        # top-level passthrough
        assert out[0]["portfolio_nav"] == 1_000_000.0

    def test_skips_latest_sidecar_and_replays(self):
        mod = _import_s3_loader()
        keys = [
            "predictor/optimizer_shadow/2026-06-15.json",
            "predictor/optimizer_shadow/latest.json",
            "predictor/optimizer_shadow/replays/2026-05-12_replay_x.json",
        ]
        with patch.object(mod, "get_s3_client", return_value=_client_for(keys)):
            with patch.object(mod, "_fetch_s3_json", side_effect=lambda b, k: _shadow_doc("2026-06-15")):
                out = mod.load_optimizer_risk_history()
        assert len(out) == 1
        assert out[0]["run_date"] == "2026-06-15"

    def test_empty_when_no_objects(self):
        mod = _import_s3_loader()
        with patch.object(mod, "get_s3_client", return_value=_client_for([])):
            assert mod.load_optimizer_risk_history() == []

    def test_empty_on_list_error(self):
        mod = _import_s3_loader()
        client = MagicMock()
        client.list_objects_v2.side_effect = RuntimeError("boom")
        with patch.object(mod, "get_s3_client", return_value=client):
            with patch.object(mod, "_record_s3_error", MagicMock()):
                assert mod.load_optimizer_risk_history() == []

    def test_skips_non_dict_payloads(self):
        mod = _import_s3_loader()
        keys = ["predictor/optimizer_shadow/2026-06-15.json"]
        with patch.object(mod, "get_s3_client", return_value=_client_for(keys)):
            with patch.object(mod, "_fetch_s3_json", return_value=None):
                assert mod.load_optimizer_risk_history() == []
