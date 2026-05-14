"""Tests for the regime substrate loader functions in s3_loader.py.

Covers:
- ``load_regime_substrate_latest`` resolves via the latest.json sidecar
  and returns the dated artifact payload
- Returns None when no sidecar exists yet (pre-deploy state)
- ``load_regime_substrate_history`` lists YYMMDDHHMM-shaped artifacts,
  sorts chronologically, takes the most recent N
- History skips the latest.json sidecar and non-conforming keys

Uses a lighter-weight test pattern than ``test_s3_loader_data.py`` —
patches loader-module attributes directly rather than mocking
``builtins.open`` + reimporting, which can collide with system module
imports on a fresh test session (cf. _osx_support.py reading a system
plist during platform-detection).
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


sys.path.insert(0, str(Path(__file__).parent.parent))


# Mock streamlit at module-import time so the @st.cache_data decorator
# in s3_loader becomes a no-op. Mirrors conftest's approach.
_mock_st = MagicMock()
_mock_st.cache_data = lambda **kwargs: (lambda f: f)
_mock_st.cache_resource = lambda **kwargs: (lambda f: f)
sys.modules["streamlit"] = _mock_st


@pytest.fixture
def loader():
    """Force-import the real ``loaders.s3_loader`` module.

    Other test files (``test_eval_loader.py``) replace
    ``sys.modules['loaders.s3_loader']`` with a MagicMock at module-import
    time and never restore it — when our tests run AFTER those, a naive
    ``from loaders import s3_loader`` returns the mock. Drop any cached
    MagicMock and reimport to get the real module.
    """
    import importlib
    for mod_name in ("loaders.s3_loader", "loaders"):
        cached = sys.modules.get(mod_name)
        if cached is not None and isinstance(cached, MagicMock):
            del sys.modules[mod_name]
    import loaders.s3_loader as s3_loader
    importlib.reload(s3_loader)
    return s3_loader


_LATEST_SIDECAR = {
    "run_id": "2605170230",
    "artifact_key": "regime/2605170230.json",
    "calendar_date": "2026-05-17",
    "trading_day": "2026-05-15",
    "schema_version": 1,
    "hmm_argmax": "neutral",
    "composite_intensity_z": 0.15,
    "regime_change_signal": False,
    "written_at": "2026-05-17T02:30:00Z",
}

_DATED_ARTIFACT = {
    "calendar_date": "2026-05-17",
    "trading_day": "2026-05-15",
    "run_id": "2605170230",
    "schema_version": 1,
    "hmm": {"argmax": "neutral", "probs": {"bear": 0.18, "neutral": 0.62, "bull": 0.20}},
    "composite": {"intensity_z": 0.15},
    "bocpd": {"change_signal": False},
    "features": {"vix_level": 17.4},
}


class TestLoadRegimeSubstrateLatest:
    def test_resolves_sidecar_to_artifact(self, loader):
        def _fetch(bucket, key):
            if key == "regime/latest.json":
                return _LATEST_SIDECAR
            if key == "regime/2605170230.json":
                return _DATED_ARTIFACT
            return None
        with patch.object(loader, "_fetch_s3_json", side_effect=_fetch):
            result = loader.load_regime_substrate_latest()
        assert result == _DATED_ARTIFACT

    def test_returns_none_when_sidecar_missing(self, loader):
        with patch.object(loader, "_fetch_s3_json", return_value=None):
            result = loader.load_regime_substrate_latest()
        assert result is None

    def test_returns_none_when_sidecar_lacks_artifact_key(self, loader):
        def _fetch(bucket, key):
            if key == "regime/latest.json":
                return {"run_id": "2605170230"}  # missing artifact_key
            return _DATED_ARTIFACT
        with patch.object(loader, "_fetch_s3_json", side_effect=_fetch):
            result = loader.load_regime_substrate_latest()
        assert result is None


class TestLoadRegimeSubstrateHistory:
    def _fake_s3_client_with_keys(self, keys: list[str]):
        client = MagicMock()
        contents = [{"Key": k} for k in keys]
        paginator = MagicMock()
        paginator.paginate.return_value = [{"Contents": contents}]
        client.get_paginator.return_value = paginator
        return client

    def test_lists_canonical_artifacts_chronologically(self, loader):
        keys = [
            "regime/2604120230.json",  # older
            "regime/2605170230.json",  # newer
            "regime/2604260230.json",  # middle
            "regime/latest.json",      # sidecar — must be skipped
        ]
        fake_client = self._fake_s3_client_with_keys(keys)

        def _fetch(bucket, key):
            run_id = key.split("/")[-1].replace(".json", "")
            return {"run_id": run_id}

        with patch.object(loader, "get_s3_client", return_value=fake_client):
            with patch.object(loader, "_fetch_s3_json", side_effect=_fetch):
                result = loader.load_regime_substrate_history(n_weeks=10)

        assert [p["run_id"] for p in result] == [
            "2604120230", "2604260230", "2605170230",
        ], "history must be sorted oldest → newest by run_id"

    def test_takes_only_last_n(self, loader):
        keys = [f"regime/26{m:02d}010230.json" for m in range(1, 11)]  # 10 months
        fake_client = self._fake_s3_client_with_keys(keys)
        with patch.object(loader, "get_s3_client", return_value=fake_client):
            with patch.object(loader, "_fetch_s3_json", side_effect=lambda b, k: {"key": k}):
                result = loader.load_regime_substrate_history(n_weeks=3)
        assert len(result) == 3
        # Should be the three most-recent (months 8, 9, 10)
        assert [r["key"] for r in result] == [
            "regime/2608010230.json",
            "regime/2609010230.json",
            "regime/2610010230.json",
        ]

    def test_skips_nonconforming_keys(self, loader):
        keys = [
            "regime/2605170230.json",
            "regime/retrospective/2605170230.json",  # nested → skip
            "regime/latest.json",                     # sidecar → skip
            "regime/notnumeric.json",                 # non-numeric → skip
            "regime/12345.json",                      # wrong length → skip
            "regime/some.random.parquet",             # wrong ext → skip
        ]
        fake_client = self._fake_s3_client_with_keys(keys)
        with patch.object(loader, "get_s3_client", return_value=fake_client):
            with patch.object(loader, "_fetch_s3_json", side_effect=lambda b, k: {"key": k}):
                result = loader.load_regime_substrate_history(n_weeks=10)
        assert len(result) == 1
        assert result[0]["key"] == "regime/2605170230.json"

    def test_empty_when_no_artifacts(self, loader):
        fake_client = self._fake_s3_client_with_keys([])
        with patch.object(loader, "get_s3_client", return_value=fake_client):
            with patch.object(loader, "_fetch_s3_json", side_effect=lambda b, k: None):
                result = loader.load_regime_substrate_history(n_weeks=26)
        assert result == []

    def test_skips_fetch_failures(self, loader):
        """If one artifact body fails to fetch (S3 hiccup), the others
        should still come back — partial-progress preferred over all-fail."""
        keys = [
            "regime/2604120230.json",
            "regime/2604260230.json",
            "regime/2605170230.json",
        ]
        fake_client = self._fake_s3_client_with_keys(keys)

        def _fetch(bucket, key):
            if "2604260230" in key:
                return None  # simulate fetch failure
            return {"key": key}

        with patch.object(loader, "get_s3_client", return_value=fake_client):
            with patch.object(loader, "_fetch_s3_json", side_effect=_fetch):
                result = loader.load_regime_substrate_history(n_weeks=10)
        assert len(result) == 2
        keys_returned = [r["key"] for r in result]
        assert "regime/2604260230.json" not in keys_returned
