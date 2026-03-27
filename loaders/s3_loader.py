"""
S3 data loading utilities for the Alpha Engine Dashboard.
All data-fetching functions use @st.cache_data with TTLs from config.yaml.
Credentials come from the EC2 IAM role (no explicit creds needed).
"""

import io
import json
import logging
import os
import re
from datetime import datetime

import boto3
import pandas as pd
import streamlit as st
import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# S3 error tracking
# ---------------------------------------------------------------------------

_recent_s3_errors: list[dict] = []
_MAX_S3_ERRORS = 50


def _record_s3_error(bucket: str, key: str, error_type: str, message: str):
    """Append an error record (capped at _MAX_S3_ERRORS)."""
    _recent_s3_errors.append({
        "timestamp": datetime.utcnow().isoformat(),
        "bucket": bucket,
        "key": key,
        "error_type": error_type,
        "message": str(message)[:200],
    })
    if len(_recent_s3_errors) > _MAX_S3_ERRORS:
        _recent_s3_errors.pop(0)


def get_recent_s3_errors() -> list[dict]:
    """Return the recent S3 error log (up to 50 entries)."""
    return list(_recent_s3_errors)

# ---------------------------------------------------------------------------
# Config loading (module-level, cached forever via lru_cache-style singleton)
# ---------------------------------------------------------------------------

_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml"
)

_config_cache: dict | None = None


def load_config() -> dict:
    """Load and return the parsed config.yaml. Cached in process memory."""
    global _config_cache
    if _config_cache is None:
        with open(_CONFIG_PATH) as f:
            _config_cache = yaml.safe_load(f)
    return _config_cache


# Convenience accessors used by cached functions below
def _ttl(key: str) -> int:
    return load_config()["cache_ttl"].get(key, 900)


def _research_bucket() -> str:
    return load_config()["s3"]["research_bucket"]


def _trades_bucket() -> str:
    return load_config()["s3"]["trades_bucket"]


# ---------------------------------------------------------------------------
# S3 client helper
# ---------------------------------------------------------------------------


def get_s3_client():
    """Return a boto3 S3 client. Uses EC2 IAM role automatically."""
    return boto3.client("s3")


# ---------------------------------------------------------------------------
# Low-level S3 helpers (not cached — called by cached wrappers below)
# ---------------------------------------------------------------------------


def _s3_get_object(bucket: str, key: str):
    """Raw GetObject call. Returns the response body bytes or None on error."""
    try:
        client = get_s3_client()
        response = client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()
    except client.exceptions.NoSuchKey:
        return None
    except client.exceptions.ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error("S3 ClientError for %s/%s: %s", bucket, key, error_code)
        _record_s3_error(bucket, key, "ClientError", str(e))
        return None
    except (ConnectionError, TimeoutError) as e:
        logger.warning("S3 connection error for %s/%s: %s", bucket, key, e)
        _record_s3_error(bucket, key, type(e).__name__, str(e))
        return None
    except Exception as e:
        logger.error("S3 unexpected error for %s/%s", bucket, key, exc_info=True)
        _record_s3_error(bucket, key, type(e).__name__, str(e))
        return None


# ---------------------------------------------------------------------------
# Cached public API
# ---------------------------------------------------------------------------


@st.cache_data(ttl=_ttl("signals"))
def list_s3_prefixes(bucket: str, prefix: str) -> list[str]:
    """
    Return a sorted list of date-like sub-prefixes under *prefix*.
    E.g., for prefix='signals/' returns ['2024-01-15', '2024-01-16', ...].
    """
    try:
        client = get_s3_client()
        paginator = client.get_paginator("list_objects_v2")
        date_pattern = re.compile(r"\d{4}-\d{2}-\d{2}")
        prefixes: set[str] = set()
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter="/"):
            for cp in page.get("CommonPrefixes", []):
                p = cp.get("Prefix", "")
                # Extract the date-like segment
                stripped = p[len(prefix):].strip("/")
                if date_pattern.match(stripped):
                    prefixes.add(stripped)
            # Also handle keys directly (no trailing slash)
            for obj in page.get("Contents", []):
                k = obj.get("Key", "")
                rel = k[len(prefix):]
                seg = rel.split("/")[0]
                if date_pattern.match(seg):
                    prefixes.add(seg)
        return sorted(prefixes)
    except Exception as e:
        logger.error("Failed to list S3 prefixes %s/%s: %s", bucket, prefix, e)
        _record_s3_error(bucket, prefix, type(e).__name__, str(e))
        return []


@st.cache_data(ttl=_ttl("signals"))
def download_s3_json(bucket: str, key: str) -> dict | list | None:
    """Download and parse a JSON file from S3. Returns None on failure."""
    try:
        client = get_s3_client()
        response = client.get_object(Bucket=bucket, Key=key)
        raw = response["Body"].read()
        return json.loads(raw)
    except client.exceptions.NoSuchKey:
        return None
    except Exception as e:
        logger.error("Failed to download JSON %s/%s: %s", bucket, key, e)
        _record_s3_error(bucket, key, type(e).__name__, str(e))
        return None


@st.cache_data(ttl=_ttl("trades"))
def download_s3_csv(bucket: str, key: str) -> pd.DataFrame | None:
    """Download a CSV from S3 and return a DataFrame. Returns None on failure."""
    try:
        client = get_s3_client()
        response = client.get_object(Bucket=bucket, Key=key)
        raw = response["Body"].read()
    except client.exceptions.NoSuchKey:
        return None
    except Exception as e:
        logger.error("Failed to download CSV %s/%s: %s", bucket, key, e)
        _record_s3_error(bucket, key, type(e).__name__, str(e))
        return None

    try:
        return pd.read_csv(io.BytesIO(raw))
    except Exception as e:
        logger.warning("CSV parse failed for %s/%s: %s", bucket, key, e)
        _record_s3_error(bucket, key, "CSVParseError", str(e))
        return None


@st.cache_data(ttl=_ttl("research"))
def download_s3_text(bucket: str, key: str) -> str | None:
    """Download a text file from S3 and return its content. Returns None on failure."""
    try:
        client = get_s3_client()
        response = client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read().decode("utf-8")
    except client.exceptions.NoSuchKey:
        return None
    except Exception as e:
        logger.error("Failed to download text %s/%s: %s", bucket, key, e)
        _record_s3_error(bucket, key, type(e).__name__, str(e))
        return None


def download_s3_binary(bucket: str, key: str, local_path: str) -> bool:
    """Download a binary file from S3 to *local_path*. Returns True on success."""
    try:
        client = get_s3_client()
        client.download_file(bucket, key, local_path)
        return True
    except Exception as e:
        logger.error("Failed to download binary %s/%s: %s", bucket, key, e)
        _record_s3_error(bucket, key, type(e).__name__, str(e))
        return False


@st.cache_data(ttl=_ttl("signals"))
def get_latest_prefix(bucket: str, prefix: str) -> str | None:
    """
    List all keys under *prefix*, extract YYYY-MM-DD date segments,
    and return the most recent one (sorted descending). Returns None if none found.
    """
    dates = list_s3_prefixes(bucket, prefix)
    if not dates:
        return None
    return sorted(dates, reverse=True)[0]


@st.cache_data(ttl=_ttl("signals"))
def check_key_exists(bucket: str, key: str) -> bool:
    """Return True if the given S3 key exists."""
    try:
        client = get_s3_client()
        client.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Convenience wrappers bound to configured buckets / paths
# ---------------------------------------------------------------------------


def load_signals_json(date_str: str) -> dict | None:
    """Load signals.json for a given date from the research bucket."""
    cfg = load_config()
    key = cfg["paths"]["signals"].format(date=date_str)
    return download_s3_json(_research_bucket(), key)


def load_trades_full() -> pd.DataFrame | None:
    """Load trades_full.csv from the executor bucket."""
    cfg = load_config()
    key = cfg["paths"]["trades_full"]
    return download_s3_csv(_trades_bucket(), key)


def load_eod_pnl() -> pd.DataFrame | None:
    """Load eod_pnl.csv from the executor bucket."""
    cfg = load_config()
    key = cfg["paths"]["eod_pnl"]
    return download_s3_csv(_trades_bucket(), key)


def load_scoring_weights() -> dict | None:
    """Load current scoring_weights.json from the research bucket."""
    cfg = load_config()
    key = cfg["paths"]["scoring_weights"]
    return download_s3_json(_research_bucket(), key)


def load_scoring_weights_history() -> list[dict]:
    """
    Load all scoring weight history files and return as a list of dicts,
    each containing the date and weight values, sorted ascending by date.
    """
    cfg = load_config()
    prefix = cfg["paths"]["scoring_weights_history_prefix"]
    dates = list_s3_prefixes(_research_bucket(), prefix)
    history = []
    for date_str in sorted(dates):
        key = f"{prefix}{date_str}.json"
        data = download_s3_json(_research_bucket(), key)
        if data and isinstance(data, dict):
            data["updated_at"] = date_str
            history.append(data)
    return history


def list_backtest_dates() -> list[str]:
    """Return sorted list of available backtest dates (descending)."""
    cfg = load_config()
    prefix = cfg["paths"]["backtest_prefix"]
    dates = list_s3_prefixes(_research_bucket(), prefix)
    return sorted(dates, reverse=True)


def load_backtest_file(date_str: str, filename: str):
    """
    Load a file from backtest/{date}/{filename} in the research bucket.
    Supports .json, .csv, .md extensions.
    """
    cfg = load_config()
    prefix = cfg["paths"]["backtest_prefix"]
    key = f"{prefix}{date_str}/{filename}"
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".json":
        return download_s3_json(_research_bucket(), key)
    elif ext == ".csv":
        return download_s3_csv(_research_bucket(), key)
    elif ext in (".md", ".txt"):
        return download_s3_text(_research_bucket(), key)
    else:
        return download_s3_text(_research_bucket(), key)


def load_predictions_json(date_str: str | None = None) -> dict:
    """Load predictor predictions from S3. Returns {} on any failure."""
    if date_str:
        key = f"predictor/predictions/{date_str}.json"
    else:
        key = "predictor/predictions/latest.json"
    try:
        client = get_s3_client()
        response = client.get_object(Bucket=_research_bucket(), Key=key)
        data = json.loads(response["Body"].read())
        pred_list = data.get("predictions", [])
        return {p["ticker"]: p for p in pred_list if "ticker" in p}
    except client.exceptions.NoSuchKey:
        return {}
    except Exception as e:
        logger.error("Failed to load predictions %s: %s", key, e)
        _record_s3_error(_research_bucket(), key, type(e).__name__, str(e))
        return {}


def load_predictor_metrics() -> dict:
    """Load predictor metrics from S3. Returns {} on any failure."""
    key = "predictor/metrics/latest.json"
    try:
        client = get_s3_client()
        response = client.get_object(Bucket=_research_bucket(), Key=key)
        return json.loads(response["Body"].read())
    except client.exceptions.NoSuchKey:
        return {}
    except Exception as e:
        logger.error("Failed to load predictor metrics: %s", e)
        _record_s3_error(_research_bucket(), key, type(e).__name__, str(e))
        return {}


def load_mode_history() -> list[dict]:
    """Load predictor mode selection history from S3. Returns [] on failure."""
    key = "predictor/metrics/mode_history.json"
    try:
        client = get_s3_client()
        response = client.get_object(Bucket=_research_bucket(), Key=key)
        data = json.loads(response["Body"].read())
        return data if isinstance(data, list) else []
    except client.exceptions.NoSuchKey:
        return []
    except Exception as e:
        logger.error("Failed to load mode history: %s", e)
        _record_s3_error(_research_bucket(), key, type(e).__name__, str(e))
        return []


def load_predictor_params() -> dict:
    """Load predictor_params.json from S3 config. Returns {} on any failure."""
    key = "config/predictor_params.json"
    try:
        client = get_s3_client()
        response = client.get_object(Bucket=_research_bucket(), Key=key)
        return json.loads(response["Body"].read())
    except client.exceptions.NoSuchKey:
        return {}
    except Exception as e:
        logger.error("Failed to load predictor params: %s", e)
        _record_s3_error(_research_bucket(), key, type(e).__name__, str(e))
        return {}


@st.cache_data(ttl=_ttl("research"))
def load_population_json() -> dict | None:
    """Load population/latest.json from the research bucket.

    Returns the full dict with 'population', 'date', 'market_regime', etc.
    Returns None if the file does not exist.
    """
    return download_s3_json(_research_bucket(), "population/latest.json")


@st.cache_data(ttl=_ttl("signals"))
def load_order_book_summary(date_str: str) -> dict | None:
    """Load order_book_summary.json for a given date from the research bucket.

    Returns None if the file does not exist (backward compatible).
    """
    key = f"signals/{date_str}/order_book_summary.json"
    return download_s3_json(_research_bucket(), key)
