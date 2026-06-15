"""Tests for the Daily News loaders in loaders/s3_loader.py.

Mirrors tests/test_llm_cost_loader.py — fresh-import helper + mocked S3
client (paginator) + mocked _s3_get_object.
"""

import io
from unittest.mock import MagicMock, patch

import pandas as pd

_MOCK_CONFIG = {
    "s3": {"research_bucket": "test-bucket", "trades_bucket": "test-bucket"},
    "cache_ttl": {"signals": 900, "trades": 900, "research": 3600, "backtest": 3600},
    "paths": {
        "signals": "signals/{date}/signals.json",
        "research_db": "research.db",
    },
}


def _import_s3_loader():
    import sys
    if "loaders.s3_loader" in sys.modules:
        del sys.modules["loaders.s3_loader"]
    with patch("builtins.open", MagicMock()):
        with patch("yaml.safe_load", return_value=_MOCK_CONFIG):
            from loaders import s3_loader
            return s3_loader


def _paginator_for(keys):
    """Return a mock S3 client whose paginator yields one page of `keys`."""
    client = MagicMock()
    paginator = MagicMock()
    paginator.paginate.return_value = [
        {"Contents": [{"Key": k} for k in keys]}
    ]
    client.get_paginator.return_value = paginator
    return client


def _articles_parquet_bytes(rows):
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    return buf.getvalue()


class TestListNewsArticleRuns:
    def test_parses_run_id_to_date_newest_first(self):
        mod = _import_s3_loader()
        keys = [
            "data/news_articles_daily/2606150905_articles.parquet",
            "data/news_articles_daily/2606120905_articles.parquet",
            "data/news_articles_daily/latest.json",  # ignored (no suffix match)
        ]
        with patch.object(mod, "get_s3_client", return_value=_paginator_for(keys)):
            runs = mod.list_news_article_runs()
        assert [r["date"] for r in runs] == ["2026-06-15", "2026-06-12"]
        assert runs[0]["key"] == "data/news_articles_daily/2606150905_articles.parquet"

    def test_dedupes_same_date_keeping_latest_run(self):
        mod = _import_s3_loader()
        keys = [
            "data/news_articles_daily/2606150905_articles.parquet",  # earlier run
            "data/news_articles_daily/2606151430_articles.parquet",  # later run, same day
        ]
        with patch.object(mod, "get_s3_client", return_value=_paginator_for(keys)):
            runs = mod.list_news_article_runs()
        assert len(runs) == 1
        assert runs[0]["run_id"] == "2606151430"

    def test_ignores_non_conforming_keys(self):
        mod = _import_s3_loader()
        keys = [
            "data/news_articles_daily/garbage_articles.parquet",  # non-digit run_id
            "data/news_articles_daily/123_articles.parquet",      # wrong length
            "data/news_articles_daily/2606150905_articles.parquet",
        ]
        with patch.object(mod, "get_s3_client", return_value=_paginator_for(keys)):
            runs = mod.list_news_article_runs()
        assert len(runs) == 1
        assert runs[0]["date"] == "2026-06-15"

    def test_empty_on_no_keys(self):
        mod = _import_s3_loader()
        with patch.object(mod, "get_s3_client", return_value=_paginator_for([])):
            assert mod.list_news_article_runs() == []

    def test_n_recent_caps(self):
        mod = _import_s3_loader()
        keys = [
            f"data/news_articles_daily/26061{d}0905_articles.parquet"
            for d in range(1, 6)
        ]
        with patch.object(mod, "get_s3_client", return_value=_paginator_for(keys)):
            runs = mod.list_news_article_runs(n_recent=2)
        assert len(runs) == 2


class TestLoadNewsArticles:
    def test_loads_parquet(self):
        mod = _import_s3_loader()
        parquet = _articles_parquet_bytes([
            {"title": "Big news", "url": "https://x/1", "lm_sentiment": 0.3},
        ])
        with patch.object(mod, "_s3_get_object", return_value=parquet):
            df = mod.load_news_articles("data/news_articles_daily/2606150905_articles.parquet")
        assert len(df) == 1
        assert df.iloc[0]["title"] == "Big news"

    def test_missing_key_returns_empty(self):
        mod = _import_s3_loader()
        with patch.object(mod, "_s3_get_object", return_value=None):
            df = mod.load_news_articles("missing")
        assert df.empty

    def test_bad_parquet_returns_empty(self):
        mod = _import_s3_loader()
        with patch.object(mod, "_s3_get_object", return_value=b"not parquet"):
            df = mod.load_news_articles("bad")
        assert df.empty
