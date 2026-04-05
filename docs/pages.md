# Pages Reference

Per-page field and chart documentation.

---

## Home (`app.py`)

Entry point. Answers: _is everything healthy right now?_

### System Health

Five status indicators (🟢/🟡/🔴):

| Indicator | Green | Yellow | Red |
|-----------|-------|--------|-----|
| Research Lambda | signals.json found today | Found yesterday | Not found in 2+ days |
| IB Gateway | eod_pnl row today | Row yesterday | No row in 3+ days |
| Backtester | Ran within 7 days | Ran within 30 days | Older than 30 days |
| Signal Quality | <10% stale signals | 10–30% stale | >30% stale |
| Predictor | metrics/latest.json today, hit_rate_30d > 0.52 | Today but hit rate 0.48–0.52 | Not found today or hit rate < 0.48 |

### Today's Snapshot

| Card | Source |
|------|--------|
| Portfolio NAV | `eod_pnl.portfolio_nav` (most recent row) |
| Daily Return | `eod_pnl.daily_return_pct` |
| vs SPY (Alpha) | `eod_pnl.daily_alpha_pct` |
| Signal Count | ENTER/EXIT/HOLD counts from today's signals.json |

### Today's Signals

Buy candidates from signals.json sorted by score descending. Color coded by signal type:

- ENTER — green (`#d4edda`)
- EXIT — red (`#f8d7da`)
- REDUCE — orange (`#fff3cd`)
- HOLD — gray (`#f8f9fa`)

### Market Context

Regime, VIX, 10yr yield from `macro_snapshots` for today's date.

---

## Page 1: Portfolio (`pages/1_Portfolio.py`)

Answers: _how is the paper portfolio performing vs. SPY?_

### Charts

**NAV vs SPY** (`charts/nav_chart.py`)
- Cumulative return % from first eod_pnl row
- Green shading where portfolio > SPY; red where below
- Hover shows date, portfolio %, SPY %, alpha %

**Daily Alpha** (`charts/alpha_chart.py`)
- Bar chart: green bars for positive alpha days, red for negative
- Secondary axis: cumulative alpha line overlay

**Drawdown**
- Area chart of `(NAV - peak_NAV) / peak_NAV`
- Red fill; dashed horizontal line at circuit breaker threshold (`-8%` from config)

### Current Positions

Parsed from `eod_pnl.positions_snapshot` (JSON string). Joined with today's signals for current score.

| Column | Source |
|--------|--------|
| Ticker | positions_snapshot key |
| Shares | positions_snapshot |
| Market Value | positions_snapshot |
| % NAV | positions_snapshot |
| Score (latest) | today's signals.json |
| Return Since Entry | `(current price - entry_price) / entry_price` |

### Summary Stats

Computed from full eod_pnl history:

| Stat | Formula |
|------|---------|
| Total return | `(NAV_last / NAV_first) - 1` |
| Sharpe (annualized) | `mean(daily_return) / std(daily_return) * √252` (requires ≥30 rows) |
| Max drawdown | `min((NAV - peak_NAV) / peak_NAV)` |
| Best / worst day | Max/min of `daily_return_pct` |
| Days positive/negative | Count of positive/negative `daily_alpha_pct` |
| Avg daily alpha | `mean(daily_alpha_pct)` |

---

## Page 2: Signals & Research (`pages/2_Signals_and_Research.py`)

Answers: _what are all the signals today and why, and what does the research say about a specific ticker?_

Merges the former Signals and Research pages. Signal table and sector ratings at the top; a ticker drilldown section below surfaces the former Research page content (full score history with sub-scores and signal markers, conviction history, performance outcomes, thesis timeline).

### Date Picker

Dropdown of all available `signals/{date}/` S3 prefixes, defaulting to most recent.

### Signal Table

Full universe from signals.json. Filterable by:
- Sector (multiselect)
- Signal type (multiselect)
- Minimum score (slider)

Stale signals shown with ⚠ badge. Predictor direction shown as UP ↑ / FLAT → / DOWN ↓ in a `Prediction` column (blank if no prediction available); `Confidence` column shown only when ≥ 0.65.

### Ticker Drilldown

Select a ticker below the signal table to surface:
- Thesis summary paragraph
- Sub-score horizontal bar chart (technical / news / research) — current snapshot
- Predictor probability bar: `p_up` (green) / `p_flat` (gray) / `p_down` (red) stacked horizontal; badge showing modifier applied or skipped with reason
- **Score history** (full): composite line (bold) + faint sub-score lines (technical/news/research) + signal markers (ENTER ▲ / EXIT ▼ / REDUCE ◆)
- **Conviction history** line chart
- **Performance outcomes** table from `score_performance` (score_date, composite_score, return_10d/30d vs SPY, beat_spy_10d/30d as ✅/❌/⏳)
- **Thesis timeline** — expandable list of `thesis_summary` entries from `investment_thesis`, newest first

### Sector Ratings

| Column | Source |
|--------|--------|
| Sector | signals.json sector_ratings keys |
| Rating | OW / MW / UW |
| Modifier | +/- modifier |
| Rationale | Snippet from signals.json |

Color: OW = green, UW = red, MW = neutral.

---

## Page 3: Signal Quality (`pages/3_Signal_Quality.py`)

Answers: _are the signals getting better or worse?_

**Note:** Meaningful after ~Week 4 (~200 rows with `beat_spy_10d` populated). Shows a data loading banner until then.

### Charts (`charts/accuracy_chart.py`)

**Accuracy Trend**
- Rolling 4-week accuracy (% of BUY signals beating SPY)
- Two lines: accuracy_10d and accuracy_30d
- Dashed 50% reference line; shaded band at 55%+

**Accuracy by Score Bucket**
- Grouped bars: 60–70, 70–80, 80–90, 90+
- Two bars per bucket: 10d and 30d accuracy

**Accuracy by Regime**
- Grouped bars: bull, neutral, bear, caution
- Joins `score_performance` to `macro_snapshots` on date
- Uses `market_regime` column (falls back to `regime` if present)

**Alpha Distribution**
- Histogram of `return_10d - spy_10d_return`
- Mean and median lines; two panels: score ≥ 70 and all signals

### Scoring Weights

Current weight metric cards from `scoring_weights.json`.

Weight history line chart (`charts/attribution_chart.make_weight_history_chart`) from all `config/scoring_weights_history/{date}.json` files.

### Predictor Accuracy (collapsible)

Only renders when `predictor_outcomes` has ≥ 20 rows with `correct_5d` populated. Shows data loading banner until then.

**Rolling Hit Rate** — 20-day rolling hit rate from `predictor_outcomes`; three lines (UP / DOWN / all); dashed 50% baseline; shaded band at 55%+ (production-ready zone).

**Hit Rate by Confidence Bucket** — grouped bars: 0.65–0.75, 0.75–0.85, 0.85–1.0. Validates that confidence is monotonically predictive. Non-monotonic result = calibration issue.

**Predictor Impact on Outcomes** — two bars: signals where predictor modifier was applied vs. not. Metric: `beat_spy_10d` rate per group. Source: join `predictor_outcomes` to `score_performance`.

**IC Over Time** — rolling 20-day Pearson IC of `p_up - p_down` vs `actual_5d_return`. Dashed 0.05 reference line (minimum viable threshold).

---

## Page 5: Backtester (`pages/5_Backtester.py`)

Shows the latest backtester run output.

### Sections

**Latest Run Banner**
- Date, status, n_samples from `metrics.json`

**Portfolio Simulation Stats**
- Total return, Sharpe, max drawdown, Calmar ratio, win rate, total trades
- Source: `metrics.json`

**Param Sweep Heatmap**
- X: `min_score` values; Y: `max_position_pct` values; Color: Sharpe ratio
- One tab per `drawdown_circuit_breaker` value
- Source: `param_sweep.csv`
- Top 5 combinations table below heatmap

**Signal Quality Summary**
- Accuracy 10d/30d with n= counts
- Avg alpha 10d/30d
- By-threshold table from `signal_quality.csv`

**Sub-Score Attribution**
- Horizontal bar chart: correlation of each sub-score with beat_spy_10d/30d
- Source: `attribution.json`

**Weight Recommendation**
- Table: current vs suggested weights with change direction
- Status badge: Applied / Not applied (insufficient data)

**Raw Report**
- Collapsible expander rendering `report.md` as markdown

---

## Page 6: Trade Log (`pages/6_Trade_Log.py`)

Full audit trail of every order placed.

### Filters

| Filter | Type |
|--------|------|
| Date range | Date input (start/end) |
| Action | Multiselect: ENTER / EXIT / REDUCE |
| Ticker | Text input |
| Market regime | Multiselect |
| Min score | Slider (0–100) |

### Trade Table

Paginated at 25 rows/page. Columns from `trades_full.csv`:

`Date · Ticker · Action · Shares · Price · Fill Price · NAV at Order · Position % · Score · Conviction · Rating · Sector Rating · Regime · Upside · IB Order ID`

Download button exports filtered view as CSV.

### Trade Summary Stats

Aggregated from filtered rows:
- Total ENTER / EXIT / REDUCE counts
- Avg score at ENTER
- Most common regime at ENTER
- Most active sectors (top 3)
- Avg position size % NAV

### Outcome Join

For ENTER trades with a matching `score_performance` row (symbol + date):
- Shows `beat_spy_10d` and `beat_spy_30d` inline
- ✅ beat SPY / ❌ did not / ⏳ outcome pending

---

## Page 7: Predictor (`pages/7_Predictor.py`)

Answers: _is the model healthy, and what is it predicting today?_

### Model Health Banner

Model version, last trained date, training sample count from `predictor/metrics/latest.json`. Status badge: 🟢 Healthy / 🟡 Degraded / 🔴 Stale. Four metric cards:

| Card | Source |
|------|--------|
| Hit Rate (30d rolling) | `hit_rate_30d_rolling` |
| IC (30d) | `ic_30d` |
| IC IR (30d) | `ic_ir_30d` |
| High-confidence predictions today | `n_high_confidence` |

### Today's Predictions Table

Full universe from `predictions/latest.json`, sorted by `p_up - p_down` descending. Default filter: high-confidence only (≥ 0.65); toggle to show all.

| Column | Source |
|--------|--------|
| Ticker | |
| Direction | UP ↑ / FLAT → / DOWN ↓ with row color |
| Confidence | `prediction_confidence` |
| P(UP) / P(FLAT) / P(DOWN) | Raw softmax probabilities |
| Score modifier | Points applied to technical score (`±` value or `—` if gate not met) |
| Current rating | From today's signals.json |

### Prediction History — Ticker Drilldown

Selectbox: any ticker in `predictor_outcomes`. Charts:
- Line: `p_up - p_down` over time (net directional signal, range −1 to +1)
- Outcome markers on resolution date: ✅ correct / ❌ wrong
- Running accuracy: `X correct of Y predictions (Z%)`

### Confidence Calibration Chart

Scatter: x = `prediction_confidence` decile, y = actual hit rate within that decile. A well-calibrated model produces a near-diagonal line. Meaningful after ~100 resolved predictions; shows calibration banner until then.

### Prediction vs. Signal Disagreements

Table of tickers where predictor direction conflicts with composite score signal — e.g., ENTER signal but DOWN prediction, or EXIT signal but UP prediction. These are the highest-tension cases for manual review.

| Column | Source |
|--------|--------|
| Ticker | |
| Signal | ENTER / EXIT / HOLD |
| Score | Composite score |
| Predicted Direction | UP / DOWN / FLAT |
| Confidence | |
| Outcome | ✅/❌/⏳ if resolved in `score_performance` |
