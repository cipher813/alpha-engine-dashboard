## System Evaluation Framework

The evaluation framework grades every component in the Alpha Engine pipeline on a
weekly basis. It produces a unified scorecard with letter grades, precision/recall/F1
metrics at every decision boundary, and tracks component health over time.

*GitHub: [alpha-engine-backtester](https://github.com/cipher813/alpha-engine-backtester) (analysis/grading.py) · Last updated: 2026-04-08*

---

### Overview

Every Saturday, the backtester computes a System Report Card that answers: "Which
components are working well, and which are degrading?" Each component is graded
on a 0-100 scale mapped to letter grades (A through F), using a weighted combination
of precision, recall, lift, and domain-specific metrics.

**Alpha contribution:** Without evaluation, the system runs blind. Signal quality
could degrade for weeks before anyone notices. The scorecard surfaces problems
early and drives the autonomous optimization loop.

---

### Grade Bands

| Score Range | Letter | Interpretation |
|-------------|--------|---------------|
| 90-100 | A | Excellent — component consistently adds alpha |
| 80-89 | A- | Strong — minor improvements possible |
| 73-79 | B+ | Good — performing above baseline |
| 65-72 | B | Solid — meeting expectations |
| 58-64 | B- | Adequate — room for improvement |
| 50-57 | C+ | Below average — attention needed |
| 42-49 | C | Weak — consider intervention |
| 35-41 | C- | Poor — active remediation needed |
| <35 | D/F | Failing — component may be subtracting value |

---

### What Gets Graded

**Research Module:**
- **Scanner** — Does the quant filter select stocks that beat SPY? (precision + recall + leakage)
- **6 Sector Teams** — Does each team pick winners within its sector? (precision + recall vs sector ETF)
- **Macro Agent** — Does the macro shift improve or hurt accuracy? (A/B lift)
- **CIO** — Does the CIO select better stocks than mechanical ranking? (precision + recall + ranking lift)
- **Composite Scoring** — Does a higher score predict higher alpha? (monotonicity + bucket accuracy)

**Predictor Module:**
- **GBM Model** — Is the model's directional signal informative? (IC + stability + sizing lift)
- **Veto Gate** — Are vetoes correct? (precision + recall + net dollar value)

**Executor Module:**
- **Entry Triggers** — Do triggers get better fills than market-open? (slippage + win rate + alpha)
- **Risk Guard** — Are blocked entries actually bad? (precision + recall + guard lift)
- **Exit Rules** — Are exits well-timed? (capture ratio + MFE/MAE + diagnosis)
- **Position Sizing** — Does sizing add value over equal-weight? (Sharpe diff + alpha diff)
- **Portfolio** — Overall portfolio performance (accuracy + alpha + Sharpe + drawdown)

---

### Classification Metrics

At every decision boundary, the system computes standard classification metrics:

| Stage | Positive Class | Precision = | Recall = |
|-------|---------------|-------------|----------|
| Scanner | Stock beats SPY | % of passed stocks that won | % of all winners that passed |
| Sector Team | Stock beats sector ETF | % of team picks that won | % of sector winners that were picked |
| CIO | Stock beats SPY | % of ADVANCE picks that won | % of all winners that were advanced |
| Predictor (UP) | Stock goes up | % of UP predictions correct | % of actual up-moves predicted |
| Veto Gate | Stock goes down | % of vetoes correct | % of actual down-moves vetoed |
| Risk Guard | Stock would lose | % of blocks that were losers | % of all losers blocked |

**F1 score** is the harmonic mean of precision and recall — it penalizes components
that sacrifice one for the other.

---

### Predictor Confusion Matrix

A 3x3 matrix comparing predicted direction (UP/FLAT/DOWN) against actual direction
(derived from 5-day forward returns using ±0.5% thresholds). Per-direction precision,
recall, and F1 reveal whether the model confuses flat with directional or reverses
direction entirely.

---

### Grade History

Weekly grades are appended to a rolling 52-week history on S3. The dashboard
displays grade trend lines per component, enabling early detection of degradation
before it impacts portfolio performance.

---

### How Grades Drive Optimization

The evaluation framework is tightly coupled with the backtester's 6 autonomous optimizers:

| Evaluator | Optimizer | Action |
|-----------|-----------|--------|
| Signal accuracy (by sector, bucket) | Weight optimizer | Adjust quant/qual scoring weights |
| Veto precision/recall | Veto analyzer | Tune confidence threshold |
| Trigger scorecard | Trigger optimizer | Disable underperforming triggers |
| Team grades | Pipeline optimizer | Adjust team slot allocation |
| CIO grade | Pipeline optimizer | Fall back to deterministic ranking if CIO degrades |
| Sizing A/B | Sizing optimizer | Simplify to equal-weight if sizing doesn't help |

When a component's grade drops, the corresponding optimizer adjusts parameters
automatically. This closes the loop: evaluate → diagnose → optimize → re-evaluate.
