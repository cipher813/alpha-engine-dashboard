"""Tests for shared/constants.py."""

from unittest.mock import patch

from shared.constants import DEFAULT_THRESHOLDS, get_thresholds


class TestGetThresholds:
    def test_returns_defaults(self):
        result = get_thresholds()
        for key in DEFAULT_THRESHOLDS:
            assert key in result

    def test_merges_overrides(self):
        mock_config = {"thresholds": {"veto_confidence": 0.70}}
        with patch("loaders.s3_loader.load_config", return_value=mock_config):
            result = get_thresholds()
            assert result["veto_confidence"] == 0.70

    def test_ignores_unknown_keys(self):
        mock_config = {"thresholds": {"unknown_key": 999}}
        with patch("loaders.s3_loader.load_config", return_value=mock_config):
            result = get_thresholds()
            assert "unknown_key" not in result

    def test_handles_none_config(self):
        with patch("loaders.s3_loader.load_config", return_value=None):
            result = get_thresholds()
            assert result == DEFAULT_THRESHOLDS
