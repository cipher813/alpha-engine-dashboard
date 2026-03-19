"""
S3 data loading for the Nous Ergon public site.
Minimal subset — only loads eod_pnl.csv (portfolio performance data).
Credentials come from the EC2 IAM role (no explicit creds needed).
"""

import io
import logging
import os

import boto3
import pandas as pd
import streamlit as st
import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml"
)

_config_cache: dict | None = None


def load_config() -> dict:
    global _config_cache
    if _config_cache is None:
        with open(_CONFIG_PATH) as f:
            _config_cache = yaml.safe_load(f)
    return _config_cache


def _ttl(key: str) -> int:
    return load_config()["cache_ttl"].get(key, 900)


def _trades_bucket() -> str:
    return load_config()["s3"]["trades_bucket"]


# ---------------------------------------------------------------------------
# S3 helpers
# ---------------------------------------------------------------------------


def get_s3_client():
    # On Streamlit Cloud, credentials come from st.secrets["aws"]
    # On EC2, boto3 uses the IAM role automatically
    try:
        aws_secrets = st.secrets["aws"]
        return boto3.client(
            "s3",
            aws_access_key_id=aws_secrets["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=aws_secrets["AWS_SECRET_ACCESS_KEY"],
            region_name=aws_secrets.get("AWS_DEFAULT_REGION", "us-east-1"),
        )
    except (KeyError, FileNotFoundError):
        return boto3.client("s3")


@st.cache_data(ttl=_ttl("trades"))
def download_s3_csv(bucket: str, key: str) -> pd.DataFrame | None:
    try:
        client = get_s3_client()
        response = client.get_object(Bucket=bucket, Key=key)
        raw = response["Body"].read()
    except Exception as e:
        logger.error("Failed to download CSV %s/%s: %s", bucket, key, e)
        return None
    try:
        return pd.read_csv(io.BytesIO(raw))
    except Exception as e:
        logger.warning("CSV parse failed for %s/%s: %s", bucket, key, e)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_eod_pnl() -> pd.DataFrame | None:
    """Load eod_pnl.csv from the executor bucket."""
    cfg = load_config()
    key = cfg["paths"]["eod_pnl"]
    return download_s3_csv(_trades_bucket(), key)
