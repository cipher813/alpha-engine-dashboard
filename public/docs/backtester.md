## Backtester Module

The Backtester is the system's learning mechanism. It measures signal quality,
optimizes parameters across all modules, and auto-applies updated configurations —
closing the feedback loop without manual intervention.

---

### Overview

Every Monday after Research and Predictor Training complete, the Backtester analyzes
historical signal accuracy, runs parameter sweeps, and writes optimized configs back
to S3. Downstream modules pick up these configs on their next cold start.

**Alpha contribution:** Validates that signals actually correlate with outperformance,
identifies which scoring factors are most predictive, and continuously tunes the
system toward higher risk-adjusted returns.

---

### Key Concepts

- **Signal quality analysis:** Measures what percentage of BUY signals actually beat
  SPY over 10-day and 30-day windows, broken down by score range and market regime
- **Attribution analysis:** Correlates individual sub-scores (news, research, macro,
  signal boosts) with actual outperformance to identify the most predictive factors
- **Parameter sweep:** 60-trial random search over executor risk parameters (ATR
  multiplier, time decay, position sizing factors), ranked by Sharpe ratio and
  validated on a holdout period
- **Auto-apply:** Optimized parameters are written directly to S3 config files that
  all downstream modules read — no manual intervention required
- **Portfolio simulation:** VectorBT replays historical orders to compute Sharpe,
  max drawdown, Calmar ratio, and cumulative alpha

---

### How It Works

```
Read signal history from S3 (score_performance table)
  → Signal quality: accuracy by score bucket, regime, time period
  → Attribution: correlate sub-scores with outperformance
  → Weight optimization: recommend scoring weight adjustments
  → Parameter sweep: 60-trial random search over risk params
  → Veto analysis: auto-tune predictor confidence threshold
  → Portfolio simulation: replay historical trades via VectorBT
  → Write optimized configs to S3:
      config/scoring_weights.json   → Research
      config/executor_params.json   → Executor
      config/predictor_params.json  → Predictor
      config/research_params.json   → Research (deferred until 200+ samples)
```

---

### What Gets Optimized

| Config File | Target Module | Parameters |
|-------------|---------------|------------|
| `scoring_weights.json` | Research | News/research sub-score balance |
| `executor_params.json` | Executor | ATR multiplier, time decay, position sizing, drawdown tiers |
| `predictor_params.json` | Predictor | Veto confidence threshold |
| `research_params.json` | Research | Signal boost parameters (deferred) |

The backtester uses guardrails to prevent extreme parameter swings — changes are
bounded and only applied when backed by sufficient sample size.

---

### Quick Start

```bash
git clone https://github.com/cipher813/alpha-engine-backtester.git
cd alpha-engine-backtester
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run full analysis (reads from S3, writes report locally)
python backtest.py --report-only
```

**Required environment variables:** `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`

---

### Key Files

| File | Purpose |
|------|---------|
| `backtest.py` | CLI entry point |
| `analysis/signal_quality.py` | Accuracy metrics by score/regime |
| `analysis/attribution.py` | Sub-score correlation analysis |
| `analysis/param_sweep.py` | 60-trial random search over risk params |
| `optimizer/weight_optimizer.py` | Scoring weight auto-apply |
| `optimizer/executor_optimizer.py` | Executor param auto-apply |
| `analysis/veto_analysis.py` | Predictor veto threshold tuning |
| `synthetic/predictor_backtest.py` | 10-year synthetic signal pipeline |
| `vectorbt_bridge.py` | Portfolio simulation + alpha computation |
