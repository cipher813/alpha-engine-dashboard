#!/bin/bash
# Register the daily price fetcher cron job.
# Safe to run multiple times — replaces existing entry.
#
# Fetches all US stock prices from Polygon (1 API call) and writes to S3
# in both backtester (prices.json) and predictor (daily_closes.parquet) formats.
#
# Schedule: 4:35 PM ET weekdays (35 min after market close for Polygon to update)
#
# Usage:
#   bash infrastructure/add-price-cron.sh

set -euo pipefail

CRON_LINE="35 20 * * 1-5  cd /home/ec2-user/alpha-engine-dashboard && .venv/bin/python infrastructure/fetch_daily_prices.py >> /var/log/price_fetcher.log 2>&1"

# Remove existing price fetcher entry, then add new one
EXISTING=$(crontab -l 2>/dev/null || true)
FILTERED=$(echo "$EXISTING" | grep -v "fetch_daily_prices" || true)

{
    echo "$FILTERED"
    echo "$CRON_LINE"
} | crontab -

echo "Price fetcher cron registered: weekdays 20:35 UTC (4:35 PM ET)"
echo ""
echo "Current crontab:"
crontab -l
