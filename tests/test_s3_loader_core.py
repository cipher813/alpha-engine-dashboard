"""Tests for loaders/s3_loader.py — core S3 I/O, parsing, error tracking."""

import json
import sys
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# All tests import s3_loader inside a config mock context to match
# the pattern in test_s3_loader.py and avoid module-level config errors.

_MOCK_CONFIG = {
    "s3": {"research_bucket": "test-bucket", "trades_bucket": "test-bucket"},
    "cache_ttl": {"signals": 900, "trades": 900, "research": 3600, "backtest": 3600},
    "paths": {
        "signals": "signals/{date}/signals.json",
        "trades_full": "trades/trades_full.csv",
        "eod_pnl": "trades/eod_pnl.csv",
        "scoring_weights": "config/scoring_weights.json",
        "scoring_weights_history_prefix": "scoring_weights_history/",
        "backtest_prefix": "backtest/",
        "research_db": "research.db",
    },
}


def _import_s3_loader():
    """Import s3_loader with config mocked — safe regardless of test order."""
    with patch("builtins.open", MagicMock()):
        with patch("yaml.safe_load", return_value=_MOCK_CONFIG):
            from loaders import s3_loader
            return s3_loader


class TestPathBuilders:
    def test_predictions_key_with_date(self):
        mod = _import_s3_loader()
        assert mod._predictions_key("2026-04-08") == "predictor/predictions/2026-04-08.json"

    def test_predictions_key_latest(self):
        mod = _import_s3_loader()
        assert mod._predictions_key() == "predictor/predictions/latest.json"

    def test_order_book_key(self):
        mod = _import_s3_loader()
        assert mod._order_book_key("2026-04-08") == "order_books/2026-04-08/summary.json"


class TestS3GetObject:
    def test_success(self):
        mod = _import_s3_loader()
        mock_client = MagicMock()
        mock_client.get_object.return_value = {"Body": MagicMock(read=lambda: b"hello")}
        mock_client.exceptions.NoSuchKey = type("NoSuchKey", (Exception,), {})
        mock_client.exceptions.ClientError = type("ClientError", (Exception,), {})
        with patch.object(mod, "get_s3_client", return_value=mock_client):
            assert mod._s3_get_object("bucket", "key") == b"hello"

    def test_no_such_key(self):
        mod = _import_s3_loader()
        mock_client = MagicMock()
        nsk = type("NoSuchKey", (Exception,), {})
        mock_client.exceptions.NoSuchKey = nsk
        mock_client.exceptions.ClientError = type("ClientError", (Exception,), {})
        mock_client.get_object.side_effect = nsk()
        with patch.object(mod, "get_s3_client", return_value=mock_client):
            assert mod._s3_get_object("bucket", "key") is None

    def test_unexpected_error(self):
        mod = _import_s3_loader()
        mock_client = MagicMock()
        mock_client.exceptions.NoSuchKey = type("NoSuchKey", (Exception,), {})
        mock_client.exceptions.ClientError = type("ClientError", (Exception,), {})
        mock_client.get_object.side_effect = RuntimeError("boom")
        with patch.object(mod, "get_s3_client", return_value=mock_client):
            assert mod._s3_get_object("bucket", "key") is None


class TestFetchS3Json:
    def test_valid_json(self):
        mod = _import_s3_loader()
        data = {"key": "value"}
        with patch.object(mod, "_s3_get_object", return_value=json.dumps(data).encode()):
            assert mod._fetch_s3_json("b", "k") == data

    def test_none(self):
        mod = _import_s3_loader()
        with patch.object(mod, "_s3_get_object", return_value=None):
            assert mod._fetch_s3_json("b", "k") is None

    def test_invalid_json(self):
        mod = _import_s3_loader()
        with patch.object(mod, "_s3_get_object", return_value=b"not-json{"):
            assert mod._fetch_s3_json("b", "k") is None

    def test_list(self):
        mod = _import_s3_loader()
        with patch.object(mod, "_s3_get_object", return_value=json.dumps([1, 2]).encode()):
            assert mod._fetch_s3_json("b", "k") == [1, 2]


class TestDownloadS3Csv:
    def test_valid(self):
        mod = _import_s3_loader()
        with patch.object(mod, "_s3_get_object", return_value=b"a,b\n1,2\n3,4\n"):
            df = mod.download_s3_csv("b", "k")
            assert len(df) == 2

    def test_none(self):
        mod = _import_s3_loader()
        with patch.object(mod, "_s3_get_object", return_value=None):
            assert mod.download_s3_csv("b", "k") is None


class TestDownloadS3Text:
    def test_valid(self):
        mod = _import_s3_loader()
        with patch.object(mod, "_s3_get_object", return_value=b"# Report"):
            assert mod.download_s3_text("b", "k") == "# Report"

    def test_none(self):
        mod = _import_s3_loader()
        with patch.object(mod, "_s3_get_object", return_value=None):
            assert mod.download_s3_text("b", "k") is None


class TestLoadBacktestFile:
    def test_json(self):
        mod = _import_s3_loader()
        with patch.object(mod, "load_config", return_value=_MOCK_CONFIG), patch.object(mod, "download_s3_json", return_value={"g": 85}):
            assert mod.load_backtest_file("2026-04-08", "grading.json") == {"g": 85}

    def test_csv(self):
        mod = _import_s3_loader()
        df = pd.DataFrame({"a": [1]})
        with patch.object(mod, "load_config", return_value=_MOCK_CONFIG), patch.object(mod, "download_s3_csv", return_value=df):
            result = mod.load_backtest_file("2026-04-08", "sq.csv")
            assert isinstance(result, pd.DataFrame)

    def test_md(self):
        mod = _import_s3_loader()
        with patch.object(mod, "load_config", return_value=_MOCK_CONFIG), patch.object(mod, "download_s3_text", return_value="# R"):
            assert mod.load_backtest_file("2026-04-08", "report.md") == "# R"


class TestConvenienceWrappers:
    def test_load_signals_json(self):
        mod = _import_s3_loader()
        with patch.object(mod, "load_config", return_value=_MOCK_CONFIG), patch.object(mod, "download_s3_json", return_value={"signals": {}}):
            result = mod.load_signals_json("2026-04-08")
            assert result == {"signals": {}}

    def test_load_trades_full(self):
        mod = _import_s3_loader()
        df = pd.DataFrame({"ticker": ["AAPL"]})
        with patch.object(mod, "load_config", return_value=_MOCK_CONFIG), patch.object(mod, "download_s3_csv", return_value=df):
            result = mod.load_trades_full()
            assert len(result) == 1

    def test_load_eod_pnl(self):
        mod = _import_s3_loader()
        df = pd.DataFrame({"nav": [100000]})
        with patch.object(mod, "load_config", return_value=_MOCK_CONFIG), patch.object(mod, "download_s3_csv", return_value=df):
            result = mod.load_eod_pnl()
            assert len(result) == 1

    def test_load_scoring_weights(self):
        mod = _import_s3_loader()
        with patch.object(mod, "load_config", return_value=_MOCK_CONFIG), patch.object(mod, "download_s3_json", return_value={"quant": 0.5}):
            result = mod.load_scoring_weights()
            assert result["quant"] == 0.5

    def test_list_backtest_dates(self):
        mod = _import_s3_loader()
        with patch.object(mod, "load_config", return_value=_MOCK_CONFIG), patch.object(mod, "list_s3_prefixes", return_value=["2026-04-01", "2026-04-08"]):
            result = mod.list_backtest_dates()
            assert result == ["2026-04-08", "2026-04-01"]

    def test_check_key_exists_true(self):
        mod = _import_s3_loader()
        mock_client = MagicMock()
        with patch.object(mod, "get_s3_client", return_value=mock_client):
            assert mod.check_key_exists("b", "k") is True

    def test_check_key_exists_false(self):
        mod = _import_s3_loader()
        mock_client = MagicMock()
        mock_client.head_object.side_effect = Exception("404")
        with patch.object(mod, "get_s3_client", return_value=mock_client):
            assert mod.check_key_exists("b", "k") is False

    def test_get_latest_prefix(self):
        mod = _import_s3_loader()
        with patch.object(mod, "list_s3_prefixes", return_value=["2026-04-01", "2026-04-08"]):
            assert mod.get_latest_prefix("b", "p/") == "2026-04-08"

    def test_get_latest_prefix_empty(self):
        mod = _import_s3_loader()
        with patch.object(mod, "list_s3_prefixes", return_value=[]):
            assert mod.get_latest_prefix("b", "p/") is None


class TestErrorTracking:
    def test_record_and_retrieve(self):
        mod = _import_s3_loader()
        mod._record_s3_error("tb", "tk", "Err", "d")
        errors = mod.get_recent_s3_errors()
        assert len(errors) > 0
        assert errors[-1]["error_type"] == "Err"


class TestWithS3ErrorTracking:
    def test_success(self):
        mod = _import_s3_loader()

        @mod.with_s3_error_tracking(fallback="default")
        def good():
            return "ok"
        assert good() == "ok"

    def test_failure(self):
        mod = _import_s3_loader()

        @mod.with_s3_error_tracking(fallback="fallback")
        def bad():
            raise RuntimeError("boom")
        assert bad() == "fallback"
