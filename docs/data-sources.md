# Data Sources Reference

All data is read-only. The dashboard downloads from two S3 buckets using the EC2 IAM role — no credentials are stored in the codebase.

---

## S3 Buckets

| Bucket | Contents |
|--------|----------|
| `alpha-engine-research` | Signals, research.db, backtest output, scoring weights |
| `alpha-engine-executor` | Trade log CSVs, EOD P&L |

---

## Live / Daily Sources

### signals.json

**Path:** `s3://alpha-engine-research/signals/{date}/signals.json`
**Cache:** 15 min
**Loader:** `loaders/signal_loader.py`

Top-level fields:

| Field | Type | Description |
|-------|------|-------------|
| `date` | string | YYYY-MM-DD |
| `market_regime` | string | bull / neutral / bear / caution |
| `sector_ratings` | dict | sector → `{rating, modifier, rationale}` |
| `universe` | list | All scored tickers |
| `buy_candidates` | list | Subset with BUY/ENTER signal |

Per-ticker fields (in `universe[]` and `buy_candidates[]`):

| Field | Type | Description |
|-------|------|-------------|
| `ticker` | string | |
| `sector` | string | |
| `signal` | string | ENTER / EXIT / REDUCE / HOLD |
| `rating` | string | BUY / HOLD / SELL |
| `score` | float | 0–100 composite score |
| `conviction` | string | rising / stable / declining |
| `sub_scores.technical` | float | Technical sub-score |
| `sub_scores.news` | float | News sub-score |
| `sub_scores.research` | float | Research sub-score |
| `price_target_upside` | float | Decimal (e.g. 0.18 = 18%) |
| `thesis_summary` | string | One-paragraph research summary |
| `stale` | bool | True if research is older than threshold |

---

### eod_pnl.csv

**Path:** `s3://alpha-engine-executor/trades/eod_pnl.csv`
**Cache:** 15 min
**Loader:** `loaders/s3_loader.load_eod_pnl()`

| Column | Type | Description |
|--------|------|-------------|
| `date` | date | Trading date |
| `portfolio_nav` | float | End-of-day NAV in dollars |
| `daily_return_pct` | float | Portfolio return (decimal or %) |
| `spy_return_pct` | float | SPY return same day |
| `daily_alpha_pct` | float | `daily_return_pct - spy_return_pct` |
| `positions_snapshot` | JSON string | Dict of open positions at EOD |

`positions_snapshot` schema (per ticker):
```json
{
  "PLTR": {
    "shares": 142,
    "market_value": 11954.0,
    "pct_nav": 0.0117,
    "entry_price": 82.50
  }
}
```

---

### trades_full.csv

**Path:** `s3://alpha-engine-executor/trades/trades_full.csv`
**Cache:** 15 min
**Loader:** `loaders/s3_loader.load_trades_full()`

| Column | Type | Description |
|--------|------|-------------|
| `trade_id` | string | UUID |
| `date` | date | Trade date |
| `ticker` | string | |
| `action` | string | ENTER / EXIT / REDUCE |
| `shares` | int | |
| `price_at_order` | float | |
| `fill_price` | float | Actual fill |
| `portfolio_nav_at_order` | float | NAV at time of order |
| `position_pct` | float | % of NAV allocated |
| `research_score` | float | |
| `research_conviction` | string | |
| `research_rating` | string | |
| `sector_rating` | string | |
| `market_regime` | string | |
| `price_target_upside` | float | |
| `thesis_summary` | string | |
| `ib_order_id` | string | IBKR order ID |

---

## Research Database (research.db)

**Path:** `s3://alpha-engine-research/research.db`
**Cache:** 1 hr (downloaded to `/tmp/research.db`)
**Loader:** `loaders/db_loader.py`

### score_performance

One row per (symbol, score_date). Outcome fields populate progressively — `beat_spy_10d` appears ~10 trading days after `score_date`, `beat_spy_30d` after ~30.

| Column | Type | Description |
|--------|------|-------------|
| `symbol` | string | |
| `score_date` | date | Date signal was scored |
| `score` | float | Composite score at time of signal |
| `return_10d` | float | Ticker return over next 10 days |
| `return_30d` | float | Ticker return over next 30 days |
| `spy_10d_return` | float | SPY return over same 10-day window |
| `spy_30d_return` | float | SPY return over same 30-day window |
| `beat_spy_10d` | bool/int | 1 if return_10d > spy_10d_return |
| `beat_spy_30d` | bool/int | 1 if return_30d > spy_30d_return |

### investment_thesis

One row per (symbol, date) run. Powers the Research History page.

| Column | Type | Description |
|--------|------|-------------|
| `symbol` | string | |
| `date` | date | Date of this thesis snapshot |
| `rating` | string | BUY / HOLD / SELL |
| `score` | float | Composite score |
| `technical_score` | float | |
| `news_score` | float | |
| `research_score` | float | |
| `conviction` | string | rising / stable / declining |
| `signal` | string | ENTER / EXIT / REDUCE / HOLD |
| `price_target_upside` | float | |
| `thesis_summary` | string | |

### macro_snapshots

One row per Lambda run date.

| Column | Type | Description |
|--------|------|-------------|
| `date` | date | |
| `market_regime` | string | bull / neutral / bear / caution |
| `vix` | float | |
| `sp500_30d_return` | float | |
| `yield_curve_slope` | float | |
| `treasury_10yr` | float | |

---

## Backtest Output

**Path:** `s3://alpha-engine-research/backtest/{date}/`
**Cache:** 1 hr
**Loader:** `loaders/s3_loader.load_backtest_file(date, filename)`

| File | Format | Description |
|------|--------|-------------|
| `metrics.json` | JSON | Overall accuracy and alpha stats |
| `signal_quality.csv` | CSV | Accuracy by score threshold |
| `param_sweep.csv` | CSV | Portfolio simulation param grid results |
| `attribution.json` | JSON | Sub-score correlation with outcomes |
| `report.md` | Markdown | Full backtester narrative report |

### metrics.json schema

```json
{
  "run_date": "2026-03-09",
  "status": "ok",
  "accuracy_10d": 0.61,
  "accuracy_30d": 0.58,
  "avg_alpha_10d": 0.012,
  "avg_alpha_30d": 0.018,
  "n_10d": 98,
  "n_30d": 72
}
```

### attribution.json schema

```json
{
  "status": "ok",
  "rows_analyzed": 250,
  "correlations": {
    "technical": {"beat_spy_10d": 0.24, "beat_spy_30d": 0.19},
    "news":      {"beat_spy_10d": 0.11, "beat_spy_30d": 0.14},
    "research":  {"beat_spy_10d": 0.18, "beat_spy_30d": 0.22}
  },
  "ranking_10d": ["technical", "research", "news"],
  "ranking_30d": ["research", "technical", "news"]
}
```

---

## Scoring Weights

**Current:** `s3://alpha-engine-research/config/scoring_weights.json`
**History:** `s3://alpha-engine-research/config/scoring_weights_history/{date}.json`
**Cache:** 1 hr

```json
{
  "technical": 0.44,
  "news": 0.28,
  "research": 0.28,
  "updated_at": "2026-03-09",
  "n_samples": 85,
  "confidence": "medium"
}
```
