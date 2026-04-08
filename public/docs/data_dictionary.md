## Data Dictionary

Schema reference for all databases, CSV exports, and JSON data contracts
across the Alpha Engine system. Modules communicate exclusively through S3 —

*GitHub: [alpha-engine-docs](https://github.com/cipher813/alpha-engine-docs) · Last updated: 2026-04-08*
these schemas define the contracts between them.

---

### Overview

| Store | Module | Technology | Purpose |
|-------|--------|-----------|---------|
| `research.db` | Research | SQLite | Signal history, theses, macro, score performance |
| `trades.db` | Executor | SQLite | Trade records, daily P&L |
| RAG database | Research | PostgreSQL + pgvector | SEC filings, thesis embeddings |
| `signals.json` | Research → Predictor, Executor | JSON (S3) | Daily scored universe |
| `predictions.json` | Predictor → Executor | JSON (S3) | Daily ML predictions |
| `eod_pnl.csv` | Executor → Dashboard | CSV (S3) | Daily NAV and alpha |
| `trades_full.csv` | Executor → Dashboard | CSV (S3) | Complete trade audit log |

---

### research.db (SQLite)

Maintained by the Research module. Backed up to S3 at `research.db` and
`backups/research_{YYYYMMDD}.db`.

#### investment_thesis

Latest investment rating and composite score per stock per run.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-increment primary key |
| `symbol` | TEXT | Stock ticker |
| `date` | TEXT | Analysis date (YYYY-MM-DD) |
| `run_time` | TEXT | Run timestamp within the day |
| `rating` | TEXT | BUY, HOLD, or SELL |
| `score` | REAL | Composite score (0-100) |
| `technical_score` | REAL | Technical analysis subscore |
| `news_score` | REAL | News sentiment subscore |
| `research_score` | REAL | Fundamental analysis subscore |
| `macro_modifier` | REAL | Sector macro adjustment factor |
| `thesis_summary` | TEXT | Investment thesis (markdown) |
| `prev_rating` | TEXT | Prior rating (for change detection) |
| `prev_score` | REAL | Prior score |
| `last_material_change_date` | TEXT | Date of most recent material update |
| `stale_days` | INTEGER | Trading days since last material change |
| `conviction` | TEXT | rising, stable, or declining |
| `signal` | TEXT | ENTER, EXIT, REDUCE, or HOLD |
| `score_velocity_5d` | REAL | 5-day score momentum |
| `price_target_upside` | REAL | Expected upside as decimal |
| `predicted_direction` | TEXT | Predictor output: UP, DOWN, or FLAT |
| `prediction_confidence` | REAL | Predictor confidence (0.0-1.0) |

Unique constraint: `(symbol, date, run_time)`

#### score_performance

Ground truth for signal accuracy — used by the backtester to evaluate signal quality.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `symbol` | TEXT | Stock ticker |
| `score_date` | TEXT | Date score was generated |
| `score` | REAL | Composite score at that date |
| `price_on_date` | REAL | Stock price on score_date |
| `price_10d` | REAL | Price 10 trading days later |
| `price_30d` | REAL | Price 30 trading days later |
| `spy_10d_return` | REAL | SPY 10-day return (%) |
| `spy_30d_return` | REAL | SPY 30-day return (%) |
| `return_10d` | REAL | Stock 10-day return (%) |
| `return_30d` | REAL | Stock 30-day return (%) |
| `beat_spy_10d` | INTEGER | 1 if stock beat SPY at 10 days |
| `beat_spy_30d` | INTEGER | 1 if stock beat SPY at 30 days |

Unique constraint: `(symbol, score_date)`

#### macro_snapshots

Daily market regime and macro indicators.

| Column | Type | Description |
|--------|------|-------------|
| `date` | TEXT | Date (YYYY-MM-DD, unique) |
| `fed_funds_rate` | REAL | Fed Funds Rate (%) |
| `treasury_2yr` | REAL | 2-year Treasury yield (%) |
| `treasury_10yr` | REAL | 10-year Treasury yield (%) |
| `yield_curve_slope` | REAL | 10y - 2y spread (%) |
| `vix` | REAL | VIX volatility index |
| `sp500_close` | REAL | S&P 500 closing price |
| `sp500_30d_return` | REAL | 30-day S&P 500 return (%) |
| `market_regime` | TEXT | bull, neutral, bear, or caution |
| `sector_modifiers` | TEXT | JSON of per-sector adjustment factors |
| `sector_ratings` | TEXT | JSON of 11-sector ratings |

#### predictor_outcomes

Tracks predictor accuracy — filled by the backtester after outcomes are known.

| Column | Type | Description |
|--------|------|-------------|
| `symbol` | TEXT | Stock ticker |
| `prediction_date` | TEXT | Date of prediction |
| `predicted_direction` | TEXT | UP, DOWN, or FLAT |
| `prediction_confidence` | REAL | Confidence (0.0-1.0) |
| `p_up` | REAL | Probability UP |
| `p_flat` | REAL | Probability FLAT |
| `p_down` | REAL | Probability DOWN |
| `actual_5d_return` | REAL | Actual 5-day return (filled later) |
| `correct_5d` | INTEGER | 1 if direction was correct |

Unique constraint: `(symbol, prediction_date)`

#### thesis_history

Versioned investment thesis archive for RAG ingestion and audit trail.

| Column | Type | Description |
|--------|------|-------------|
| `ticker` | TEXT | Stock symbol |
| `run_date` | TEXT | Analysis date |
| `author` | TEXT | Agent identifier (e.g., "sector:technology") |
| `bull_case` | TEXT | Bull thesis (markdown) |
| `bear_case` | TEXT | Bear thesis (markdown) |
| `catalysts` | TEXT | Key catalysts |
| `risks` | TEXT | Key risks |
| `conviction` | INTEGER | Conviction level (1-5) |
| `score` | REAL | Recommendation score |

#### active_candidates

Current tracked universe roster (25 slots).

| Column | Type | Description |
|--------|------|-------------|
| `slot` | INTEGER | Portfolio slot number (0-24, primary key) |
| `symbol` | TEXT | Stock ticker |
| `entry_date` | TEXT | Date added to universe |
| `score` | REAL | Current composite score |
| `consecutive_low_runs` | INTEGER | Consecutive weeks with low score |

#### technical_scores

Daily technical indicator cache.

| Column | Type | Description |
|--------|------|-------------|
| `symbol` | TEXT | Stock ticker |
| `date` | TEXT | Date (YYYY-MM-DD) |
| `rsi_14` | REAL | Relative Strength Index (14-day) |
| `macd_signal` | REAL | MACD vs signal line |
| `price_vs_ma50` | REAL | Price relative to 50-day MA (%) |
| `price_vs_ma200` | REAL | Price relative to 200-day MA (%) |
| `momentum_20d` | REAL | 20-day price momentum |
| `technical_score` | REAL | Composite technical score (0-100) |

Unique constraint: `(symbol, date)`

---

### trades.db (SQLite)

Maintained by the Executor module. Exported to S3 as CSV at end of each trading day.

#### trades

Order execution records.

| Column | Type | Description |
|--------|------|-------------|
| `trade_id` | TEXT | UUID primary key |
| `date` | TEXT | Trade date (YYYY-MM-DD) |
| `ticker` | TEXT | Stock symbol |
| `action` | TEXT | ENTER, EXIT, or REDUCE |
| `shares` | INTEGER | Number of shares traded |
| `price_at_order` | REAL | Stock price when order was placed |
| `portfolio_nav_at_order` | REAL | Portfolio NAV at order time |
| `position_pct` | REAL | Position size as % of NAV |
| `research_score` | REAL | Research signal score (0-100) |
| `research_conviction` | TEXT | rising, stable, or declining |
| `research_rating` | TEXT | BUY, HOLD, or SELL |
| `sector_rating` | TEXT | overweight, market_weight, or underweight |
| `market_regime` | TEXT | bull, neutral, bear, or caution |
| `price_target_upside` | REAL | Expected upside as decimal |
| `thesis_summary` | TEXT | Investment thesis summary |
| `fill_price` | REAL | Actual fill price from broker |
| `fill_time` | TEXT | Execution timestamp (ISO 8601) |
| `ib_order_id` | INTEGER | Interactive Brokers order ID |
| `predicted_direction` | TEXT | UP, DOWN, or FLAT |
| `prediction_confidence` | REAL | Confidence (0.0-1.0) |
| `status` | TEXT | Trade status |
| `exit_reason` | TEXT | Reason for exit (time_decay, stop_hit, etc.) |
| `filled_shares` | INTEGER | Actual filled share count |
| `source` | TEXT | Signal source identifier |
| `created_at` | TEXT | ISO 8601 timestamp (UTC) |

#### eod_pnl

End-of-day portfolio reconciliation.

| Column | Type | Description |
|--------|------|-------------|
| `date` | TEXT | Trade date (primary key) |
| `portfolio_nav` | REAL | Portfolio net asset value |
| `daily_return_pct` | REAL | Daily portfolio return (%) |
| `spy_return_pct` | REAL | Daily SPY return (%) |
| `daily_alpha_pct` | REAL | Portfolio return minus SPY return (%) |
| `positions_snapshot` | TEXT | JSON of current positions |
| `spy_close` | REAL | SPY closing price |
| `created_at` | TEXT | ISO 8601 timestamp (UTC) |

---

### RAG Database (PostgreSQL + pgvector)

Hosted on Neon PostgreSQL. Used by Research qualitative agents for semantic
search over SEC filings and thesis history.

#### rag.documents

Ingested financial documents with metadata.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `ticker` | VARCHAR(10) | Stock symbol |
| `sector` | VARCHAR(50) | Sector classification |
| `doc_type` | VARCHAR(50) | 10-K, 10-Q, earnings_transcript, or thesis |
| `source` | VARCHAR(50) | sec_edgar, fmp, or alpha_engine |
| `filed_date` | DATE | Document filing date |
| `ingested_at` | TIMESTAMPTZ | Ingestion timestamp |
| `title` | TEXT | Document title |
| `url` | TEXT | Source URL |

Unique constraint: `(ticker, doc_type, filed_date, source)`

#### rag.chunks

Chunked document sections with vector embeddings for similarity search.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `document_id` | UUID | Foreign key to rag.documents |
| `chunk_index` | INTEGER | Chunk sequence within document |
| `content` | TEXT | Raw chunk text (~400 tokens) |
| `section_label` | VARCHAR(100) | Section type (Risk Factors, MD&A, etc.) |
| `embedding` | vector(512) | Voyage voyage-3-lite embedding |
| `created_at` | TIMESTAMPTZ | Chunk creation timestamp |

Index: HNSW on `embedding` column for cosine similarity search.

---

### S3 JSON Contracts

#### signals.json

**Path:** `signals/{YYYY-MM-DD}/signals.json`
**Producer:** Research | **Consumers:** Predictor, Executor

Top-level envelope:

| Field | Type | Description |
|-------|------|-------------|
| `date` | string | Run date (YYYY-MM-DD) |
| `run_time` | string | ISO 8601 timestamp |
| `market_regime` | string | bull, neutral, bear, or caution |
| `sector_ratings` | object | Per-sector rating, modifier, and rationale |
| `universe` | array | All analyzed stocks (see below) |
| `buy_candidates` | array | ENTER-signal subset |

Per-stock entry (in `universe` and `buy_candidates`):

| Field | Type | Description |
|-------|------|-------------|
| `ticker` | string | Stock symbol |
| `signal` | string | ENTER, EXIT, REDUCE, or HOLD |
| `score` | number | Composite score (0-100) |
| `conviction` | string | rising, stable, or declining |
| `research_rating` | string | BUY, HOLD, or SELL |
| `sector_rating` | string | overweight, market_weight, or underweight |
| `price_target_upside` | number | Expected upside as decimal |
| `thesis_summary` | string | Investment thesis summary |
| `news_score` | number | News sentiment subscore (0-100) |
| `research_score` | number | Fundamental research subscore (0-100) |
| `predicted_direction` | string | UP, DOWN, or FLAT (from GBM) |
| `prediction_confidence` | number | Confidence (0.0-1.0) |

#### predictions.json

**Path:** `predictor/predictions/{YYYY-MM-DD}.json`
**Producer:** Predictor | **Consumer:** Executor

Envelope:

| Field | Type | Description |
|-------|------|-------------|
| `date` | string | Prediction date |
| `model_version` | string | Model identifier |
| `n_predictions` | integer | Total predictions made |
| `predictions` | array | Per-ticker predictions (see below) |

Per-ticker entry:

| Field | Type | Description |
|-------|------|-------------|
| `ticker` | string | Stock symbol |
| `predicted_direction` | string | UP, DOWN, or FLAT |
| `prediction_confidence` | number | Confidence (0.0-1.0) |
| `p_up` | number | Probability UP |
| `p_flat` | number | Probability FLAT |
| `p_down` | number | Probability DOWN |
| `predicted_alpha` | number | Expected alpha vs SPY (%) |
| `combined_rank` | integer | Overall rank (lower = better) |

---

### S3 CSV Exports

#### trades_full.csv

**Path:** `trades/trades_full.csv`
**Producer:** Executor (EOD) | **Consumer:** Dashboard, Backtester

All columns from the `trades` SQLite table, exported as CSV. One row per
trade order (entry or exit).

#### eod_pnl.csv

**Path:** `trades/eod_pnl.csv`
**Producer:** Executor (EOD) | **Consumer:** Dashboard

All columns from the `eod_pnl` SQLite table, exported as CSV. One row per
trading day.

---

### Enum Reference

| Field | Valid Values | Used By |
|-------|-------------|---------|
| `signal` | ENTER, EXIT, REDUCE, HOLD | Research, Executor |
| `rating` / `research_rating` | BUY, HOLD, SELL | Research, Executor |
| `conviction` | rising, stable, declining | Research, Executor |
| `market_regime` | bull, neutral, bear, caution | Research, Executor, Dashboard |
| `predicted_direction` | UP, DOWN, FLAT | Predictor, Research, Executor |
| `sector_rating` | overweight, market_weight, underweight | Research, Executor |
| `action` | ENTER, EXIT, REDUCE | Executor |
| `doc_type` | 10-K, 10-Q, earnings_transcript, thesis | RAG |
