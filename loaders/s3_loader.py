"""
S3 data loading utilities for the Alpha Engine Dashboard.
All data-fetching functions use @st.cache_data with TTLs from config.yaml.
Credentials come from the EC2 IAM role (no explicit creds needed).
"""

import io
import json
import os
import re

import boto3
import pandas as pd
import streamlit as st
import yaml

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
    except Exception:
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
    except Exception:
        return []


@st.cache_data(ttl=_ttl("signals"))
def download_s3_json(bucket: str, key: str) -> dict | list | None:
    """Download and parse a JSON file from S3. Returns None on failure."""
    try:
        client = get_s3_client()
        response = client.get_object(Bucket=bucket, Key=key)
        raw = response["Body"].read()
        return json.loads(raw)
    except Exception:
        return None


@st.cache_data(ttl=_ttl("trades"))
def download_s3_csv(bucket: str, key: str) -> pd.DataFrame | None:
    """Download a CSV from S3 and return a DataFrame. Returns None on failure."""
    try:
        client = get_s3_client()
        response = client.get_object(Bucket=bucket, Key=key)
        raw = response["Body"].read()
        return pd.read_csv(io.BytesIO(raw))
    except Exception:
        return None


@st.cache_data(ttl=_ttl("research"))
def download_s3_text(bucket: str, key: str) -> str | None:
    """Download a text file from S3 and return its content. Returns None on failure."""
    try:
        client = get_s3_client()
        response = client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read().decode("utf-8")
    except Exception:
        return None


def download_s3_binary(bucket: str, key: str, local_path: str) -> bool:
    """Download a binary file from S3 to *local_path*. Returns True on success."""
    try:
        client = get_s3_client()
        client.download_file(bucket, key, local_path)
        return True
    except Exception:
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
    except Exception:
        return {}


def load_predictor_metrics() -> dict:
    """Load predictor metrics from S3. Returns {} on any failure."""
    try:
        client = get_s3_client()
        response = client.get_object(Bucket=_research_bucket(), Key="predictor/metrics/latest.json")
        return json.loads(response["Body"].read())
    except Exception:
        return {}
