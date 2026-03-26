## Predictor Module

The Predictor is the system's quantitative ML layer. It trains a gradient-boosted
model (LightGBM) to predict 5-day sector-relative returns for each tracked stock,
producing directional predictions (UP/FLAT/DOWN) with confidence scores.

---

### Overview

Research asks "is this a good stock?" — the Predictor asks "is now the right time?"
The model is trained on sector-neutral labels (stock return minus sector ETF return)
to isolate stock-specific alpha from broad sector moves.

**Alpha contribution:** High-confidence DOWN predictions trigger a veto gate that
overrides BUY signals, preventing entry into declining positions. The model adds a
quantitative timing layer on top of the qualitative research signals.

---

### Key Concepts

- **Sector-neutral labels:** Training target is `stock_5d_return - sector_etf_5d_return`,
  so the model learns stock-specific behavior independent of sector trends
- **Walk-forward validation:** Model is validated on rolling out-of-sample windows
  to prevent overfitting to historical patterns
- **Information Coefficient (IC):** Primary metric — correlation between predicted
  and actual returns. Model weights are only promoted if IC exceeds a gate threshold
- **Veto gate:** When the model predicts DOWN with confidence above a tunable
  threshold, the Executor holds off on entering that position
- **Price caching:** Layered S3 cache (full 10y weekly + 2y slim + daily delta)
  minimizes API calls to yfinance

---

### How It Works

**Weekly (Monday 07:00 UTC):**
```
Download price cache from S3
  → Refresh stale parquets (yfinance)
  → Compute features (21 technical indicators)
  → Walk-forward validation
  → Train LightGBM
  → IC gate check → promote weights if passed
  → Write slim cache for daily inference
```

**Daily (6:15 AM PT):**
```
Load GBM weights from S3
  → Fetch prices (slim cache + daily delta, yfinance fallback)
  → Compute features with batch cross-sectional rank normalization
  → Run inference per ticker
  → Write predictions/{date}.json to S3
  → Send combined morning briefing email
```

---

### Feature Engineering

The model uses 41 features across six groups:

- **Price & momentum** — Trend indicators, moving average relationships, and
  multi-horizon return signals
- **Volume** — Volume dynamics relative to historical norms and price action
- **Volatility** — Realized and implied volatility measures at multiple timeframes
- **Macro regime** — Market-wide indicators (rates, commodities, volatility index)
- **Regime interactions** — Cross-sectional features that combine macro state with
  ticker-specific signals, enabling the model to learn context-dependent behavior
- **Alternative data** — Earnings, analyst revisions, and options flow signals

All features are normalized to cross-sectional ranks within each date's universe
for comparability across stocks and time periods.

---

### Quick Start

```bash
git clone https://github.com/cipher813/alpha-engine-predictor.git
cd alpha-engine-predictor
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Dry run (loads data, computes features, skips S3 writes)
python -m inference.daily_predict --dry-run
```

**Required environment variables:** `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`

---

### Key Files

| File | Purpose |
|------|---------|
| `inference/daily_predict.py` | Full daily prediction pipeline + email |
| `training/train_handler.py` | Weekly retrain + price refresh + slim cache |
| `data/feature_engineer.py` | Feature computation (41 features) |
| `model/gbm_scorer.py` | LightGBM wrapper (train/predict/serialize) |
| `data/dataset.py` | Array builder for train/validation sets |
