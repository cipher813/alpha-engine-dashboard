## Data Module

The Data module is the centralized data collection layer for the Alpha Engine system.
It eliminates redundant API calls by running a single upstream job that writes to S3,
so all downstream modules operate on identical data snapshots.

*GitHub: [alpha-engine-data](https://github.com/cipher813/alpha-engine-data) · Last updated: 2026-04-08*

---

### Overview

With six modules consuming overlapping market data (~900 tickers fetched 2-3x,
redundant FRED/macro calls), centralizing collection reduces API costs, eliminates
rate-limiting issues, and ensures data consistency.

**Alpha contribution:** Data quality directly affects every downstream decision.
Stale prices produce stale features → wrong predictions → bad trades. The data
module's quality gates catch anomalies before they propagate.

---

### Key Concepts

- **ArcticDB:** Unified, versioned time-series store backed by S3. Replaced 909
  individual Parquet files with a single library supporting efficient range queries,
  deduplication, and schema evolution. Two libraries: `universe` (10y, training)
  and `universe_slim` (2y, inference).

- **Two-phase pipeline:** Phase 1 (before Research) collects prices, macro, and
  constituents for the full S&P 900 universe. Phase 2 (after Research) collects
  expensive alternative data only for the ~30 promoted tickers.

- **Feature store:** Pre-computes 54 features across 903 tickers for the predictor.
  Runs in both weekly and daily pipelines so inference reads pre-computed features
  instead of computing inline.

- **Data quality gates:** Six automated checks run after every price refresh —
  OHLC ordering, zero prices, extreme returns (>50% daily), zero volume, volume
  spikes, and trading day gaps. Anomalies are surfaced in completion emails.

- **Universe returns:** Full-population forward returns (5d, 10d) for all ~900
  tickers, enabling backtester evaluation of every decision boundary
  (scanner, teams, CIO, predictor, executor).

---

### How It Works

```
WEEKLY (Saturday, Step Function)
  Phase 1 (EC2 SSM, 15-25 min)
    Constituents → S&P 500+400 tickers + GICS sectors (Wikipedia)
    Prices → 10y OHLCV → ArcticDB universe library
    Slim Cache → 2y slices → ArcticDB universe_slim library
    Macro → FRED (fed funds, yields, VIX) + commodities + breadth
    Universe Returns → polygon.io grouped-daily → research.db
    Features → 54 features for 903 tickers (~20s)
    Quality Gates → 6 validation checks, anomalies in email

  Phase 2 (Lambda, after Research selects ~30 promoted tickers)
    Alternative Data → analyst consensus, EPS revisions,
      options chains, insider filings, 13F, news sentiment

DAILY (Mon-Fri, Step Function)
  DailyData (EC2 SSM)
    daily_closes/{date}.parquet → OHLCV for all tickers
    Macro refresh → yields, VIX, commodities
  FeatureStoreCompute (EC2 SSM)
    Pre-compute 54 features for inference
```

---

### Data Sources

| Source | API Key | Data | Frequency |
|--------|---------|------|-----------|
| yfinance | No | 10y OHLCV, options chains | Weekly + Daily |
| Polygon.io | POLYGON_API_KEY | Universe returns (grouped-daily) | Weekly |
| FRED | FRED_API_KEY | Fed funds, treasury yields, VIX | Weekly + Daily |
| FMP | FMP_API_KEY | Analyst consensus, EPS revisions | Weekly (Phase 2) |
| SEC EDGAR | EDGAR_IDENTITY | Insider filings, institutional 13F | Weekly (Phase 2) |
| Wikipedia | No | S&P 500+400 constituent lists | Weekly |

---

### S3 Output

| Path | Content | Consumers |
|------|---------|-----------|
| `arcticdb/universe/` | 10y OHLCV for 909 tickers | Predictor training, Backtester |
| `arcticdb/universe_slim/` | 2y OHLCV slices | Predictor inference, Executor |
| `predictor/daily_closes/{date}.parquet` | Daily OHLCV archive | Predictor inference |
| `predictor/feature_store/{date}/` | 54 features x 903 tickers | Predictor inference |
| `market_data/weekly/{date}/` | Constituents, macro, alternative | Research, Predictor |
| `research.db` (universe_returns table) | Forward returns for all tickers | Backtester |
