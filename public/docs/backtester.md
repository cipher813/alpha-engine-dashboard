## Backtester Module

The Backtester is the system's learning and evaluation mechanism. It grades every
component (A-F scorecard), measures signal quality with precision/recall/F1 at
every decision boundary, optimizes parameters across all modules, and auto-applies
updated configurations — closing the feedback loop without manual intervention.

*GitHub: [alpha-engine-backtester](https://github.com/cipher813/alpha-engine-backtester) · Last updated: 2026-04-08*

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

- **System report card:** Weekly A-F grades for every component (scanner, 6 sector
  teams, CIO, macro, predictor, veto, entry triggers, risk guard, exits, sizing, portfolio)
- **Classification metrics:** Precision/recall/F1 at every pipeline decision boundary
  (scanner, teams, CIO, predictor, executor, risk guard)
- **Per-sector accuracy:** Signal quality and veto precision broken down by sector
- **Predictor confusion matrix:** 3x3 UP/FLAT/DOWN with per-direction P/R/F1
- **Signal quality analysis:** Measures what percentage of BUY signals beat SPY
  over 5/10/30-day windows, broken down by score range, market regime, and sector
- **Attribution analysis:** Correlates sub-scores (quant, qual) with outperformance
  using Benjamini-Hochberg FDR correction
- **Parameter sweep:** 60-trial random search over executor risk parameters, ranked
  by Sharpe ratio and validated on holdout
- **6 autonomous optimizers:** Scoring weights, executor params, veto threshold,
  trigger enables, team slots, CIO mode
- **Grade history:** 52-week rolling grades appended to S3 for trend tracking
- **Portfolio simulation:** VectorBT replays historical orders to compute Sharpe,
  max drawdown, Calmar ratio, and cumulative alpha

---

### How It Works

```
Read signal history + trade data from S3
  → System report card: grade every component (A-F)
  → Classification metrics: P/R/F1 at each decision boundary
  → Per-sector accuracy: signals and veto by sector
  → Predictor confusion matrix: 3x3 UP/FLAT/DOWN
  → Signal quality: accuracy by score bucket, regime, sector
  → Attribution: correlate sub-scores with outperformance
  → Weight optimization: recommend scoring weight adjustments
  → Parameter sweep: 60-trial random search over risk params
  → Veto analysis: auto-tune predictor confidence threshold
  → Portfolio simulation: replay historical trades via VectorBT
  → Write optimized configs to S3 + structured analysis JSON:
      config/scoring_weights.json    → Research
      config/executor_params.json    → Executor
      config/predictor_params.json   → Predictor
      backtest/{date}/grading.json   → Dashboard (report card)
      backtest/{date}/*.json         → Dashboard (7 analysis files)
      backtest/grade_history.json    → Dashboard (52-week trends)
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
