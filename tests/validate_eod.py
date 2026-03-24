"""
Validate eod_pnl.csv data integrity.

Checks for gaps, unreasonable values, and cross-references SPY prices.
Run after EOD reconcile or as a periodic health check.

Usage:
    python tests/validate_eod.py              # fetch from S3
    python tests/validate_eod.py --local FILE # validate a local CSV
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta

import pandas as pd


def validate(df: pd.DataFrame) -> list[str]:
    """Validate eod_pnl DataFrame. Returns list of error strings."""
    errors = []

    if df.empty:
        return ["eod_pnl is empty"]

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # 1. Check for missing required columns
    required = ["date", "portfolio_nav", "daily_return_pct", "spy_return_pct", "daily_alpha_pct"]
    for col in required:
        if col not in df.columns:
            errors.append(f"Missing column: {col}")
    if errors:
        return errors

    # 2. Check for weekday gaps (skip weekends)
    dates = df["date"].dt.date.tolist()
    for i in range(1, len(dates)):
        prev, curr = dates[i - 1], dates[i]
        expected = prev + timedelta(days=1)
        # Skip weekends
        while expected.weekday() >= 5:
            expected += timedelta(days=1)
        if curr != expected:
            errors.append(f"Date gap: {prev} → {curr} (expected {expected})")

    # 3. NAV reasonableness
    for _, row in df.iterrows():
        nav = row["portfolio_nav"]
        if pd.isna(nav) or nav <= 0:
            errors.append(f"{row['date'].date()}: NAV is {nav} (invalid)")
        elif nav < 500_000 or nav > 2_000_000:
            errors.append(f"{row['date'].date()}: NAV={nav:.0f} outside expected range [500K, 2M]")

    # 4. Daily return reasonableness (>10% in a day is suspicious)
    for _, row in df.iterrows():
        ret = row["daily_return_pct"]
        if pd.notna(ret) and abs(ret) > 10:
            errors.append(f"{row['date'].date()}: daily_return={ret:.2f}% exceeds ±10% threshold")

    # 5. Alpha = port - spy (verify consistency)
    for _, row in df.iterrows():
        port = row["daily_return_pct"] or 0
        spy = row["spy_return_pct"] or 0
        alpha = row["daily_alpha_pct"] or 0
        expected_alpha = port - spy
        if abs(alpha - expected_alpha) > 0.01:  # allow small float rounding
            errors.append(
                f"{row['date'].date()}: alpha={alpha:.4f} != port({port:.4f}) - spy({spy:.4f}) = {expected_alpha:.4f}"
            )

    # 6. SPY close should be populated
    if "spy_close" in df.columns:
        missing_spy = df["spy_close"].isna().sum()
        if missing_spy > 0:
            errors.append(f"{missing_spy} rows with missing spy_close")

    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate eod_pnl.csv data integrity")
    parser.add_argument("--local", metavar="FILE", help="Path to local CSV file")
    args = parser.parse_args()

    if args.local:
        df = pd.read_csv(args.local)
    else:
        import os
        os.environ.setdefault("PATH", "/opt/homebrew/bin:" + os.environ.get("PATH", ""))
        import boto3
        import io
        s3 = boto3.client("s3")
        obj = s3.get_object(Bucket="alpha-engine-executor", Key="trades/eod_pnl.csv")
        df = pd.read_csv(io.BytesIO(obj["Body"].read()))

    print(f"Rows: {len(df)}")
    print(f"Date range: {df['date'].min()} → {df['date'].max()}")

    errors = validate(df)
    if errors:
        print(f"\nFAILED — {len(errors)} issue(s):")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
    else:
        print("\nPASSED — eod_pnl data is consistent")
        sys.exit(0)


if __name__ == "__main__":
    main()
