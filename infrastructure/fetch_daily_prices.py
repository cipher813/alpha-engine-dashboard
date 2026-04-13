#!/usr/bin/env python3
"""
Centralized daily price fetcher — runs on the micro instance after market close.

Calls Polygon grouped-daily (1 API call → all ~12,000 US stocks), then writes
both S3 formats that downstream modules expect:

  prices/{date}/prices.json            ← backtester price_loader.py
  predictor/daily_closes/{date}.parquet ← predictor load_price_data_from_cache()

Schedule: 35 20 * * 1-5 (4:35 PM ET weekdays, 35 min after market close)

Usage:
    python infrastructure/fetch_daily_prices.py                  # today
    python infrastructure/fetch_daily_prices.py --date 2026-03-28  # specific date
    python infrastructure/fetch_daily_prices.py --dry-run          # log only
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import sys
from datetime import date, datetime, timezone

import boto3
import pandas as pd

# polygon_client.py and ssm_secrets.py live in the repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from polygon_client import PolygonClient
from ssm_secrets import load_secrets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

S3_BUCKET = "alpha-engine-research"




def _write_health(s3, status: str, date_str: str, n_tickers: int = 0, note: str = ""):
    """Write health status JSON to S3."""
    health = {
        "module": "price_fetcher",
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "date": date_str,
        "tickers": n_tickers,
    }
    if note:
        health["note"] = note
    s3.put_object(
        Bucket=S3_BUCKET,
        Key="health/price_fetcher.json",
        Body=json.dumps(health),
        ContentType="application/json",
    )


def main():
    parser = argparse.ArgumentParser(description="Fetch daily prices from Polygon → S3")
    parser.add_argument("--date", default=str(date.today()), help="Target date YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="Log only, don't write to S3")
    args = parser.parse_args()

    date_str = args.date
    dry_run = args.dry_run

    load_secrets()

    log.info("Fetching prices for %s (dry_run=%s)", date_str, dry_run)

    # ── Fetch from Polygon ────────────────────────────────────────────────
    client = PolygonClient()
    grouped = client.get_grouped_daily(date_str)

    if not grouped:
        log.info("No results for %s (non-trading day or API issue)", date_str)
        if not dry_run:
            s3 = boto3.client("s3")
            _write_health(s3, "ok", date_str, note="non-trading day (0 results)")
        return

    n_tickers = len(grouped)
    log.info("Polygon returned %d tickers for %s", n_tickers, date_str)

    # ── Build backtester format (prices.json) ─────────────────────────────
    prices_json = {
        "date": date_str,
        "prices": {
            ticker: {
                "open": round(data["open"], 2),
                "close": round(data["close"], 2),
                "high": round(data["high"], 2),
                "low": round(data["low"], 2),
            }
            for ticker, data in grouped.items()
        },
    }

    # ── Build predictor format (daily_closes parquet) ─────────────────────
    records = []
    for ticker, data in grouped.items():
        records.append({
            "ticker": ticker,
            "date": date_str,
            "open": round(data["open"], 4),
            "high": round(data["high"], 4),
            "low": round(data["low"], 4),
            "close": round(data["close"], 4),
            "adj_close": round(data["close"], 4),  # split-adjusted; matches predictor convention
            "volume": int(data["volume"]),
        })
    closes_df = pd.DataFrame(records).set_index("ticker")

    if dry_run:
        log.info("[dry-run] Would write prices/%s/prices.json (%d tickers)", date_str, n_tickers)
        log.info("[dry-run] Would write predictor/daily_closes/%s.parquet (%d tickers)", date_str, n_tickers)
        return

    # ── Write to S3 ───────────────────────────────────────────────────────
    s3 = boto3.client("s3")

    # prices.json
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=f"prices/{date_str}/prices.json",
        Body=json.dumps(prices_json),
        ContentType="application/json",
    )
    log.info("Written s3://%s/prices/%s/prices.json (%d tickers)", S3_BUCKET, date_str, n_tickers)

    # daily_closes parquet
    buf = io.BytesIO()
    closes_df.to_parquet(buf, engine="pyarrow", compression="snappy", index=True)
    buf.seek(0)
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=f"predictor/daily_closes/{date_str}.parquet",
        Body=buf.getvalue(),
    )
    log.info("Written s3://%s/predictor/daily_closes/%s.parquet (%d tickers)", S3_BUCKET, date_str, n_tickers)

    # ── Health status ─────────────────────────────────────────────────────
    _write_health(s3, "ok", date_str, n_tickers)
    log.info("Price fetch complete: %d tickers for %s", n_tickers, date_str)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.error("Price fetch failed: %s", e, exc_info=True)
        try:
            s3 = boto3.client("s3")
            _write_health(s3, "failed", str(date.today()), note=str(e))
        except Exception:
            pass
        sys.exit(1)
