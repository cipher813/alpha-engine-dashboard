## Documentation

Nous Ergon is built from six independent modules that communicate through S3. Each module
handles one stage of the trading pipeline — data collection, research, prediction, execution,
learning via backtest, and dashboard monitoring. This documentation covers how each module works.

---

### System Pipeline

<div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08);
            border-radius: 8px; padding: 20px; text-align: center; margin: 16px 0;">
    <p style="font-size: 15px; font-family: monospace; color: #aaa; margin: 0;">
        Data &rarr; Research &rarr; Predictor &rarr; Executor &rarr; Backtester &rarr;
        <span style="color: #1a73e8;">(feedback loop)</span>
    </p>
</div>

**Weekly cycle (Saturdays):** Data collects prices into ArcticDB, Research scans the market,
the predictor retrains its stacked meta-ensemble (Layer-1 LightGBM momentum + LightGBM
volatility + research-score calibrator feeding a Layer-2 Ridge meta-learner), and the
backtester evaluates system performance (component grades, P/R/F1) and optimizes parameters.

**Daily cycle (weekdays):** Data refreshes daily closes and features, the predictor
infers 5-day alpha predictions, and the executor sizes positions, manages risk,
and places trades. EOD reconciliation runs via Step Function.

---

### Modules

<table style="width: 100%; border-collapse: collapse;">
<tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
<td style="padding: 12px 16px; vertical-align: top; width: 130px;"><a href="/Docs?section=Research" target="_blank" style="color: #1a73e8; font-weight: 600;">Research</a></td>
<td style="padding: 12px 16px; color: #ccc;">AI agents scan ~900 stocks weekly, filtering down to a scored universe of 20-25 tracked positions. Uses LLM-driven analysis with LangGraph orchestration, ReAct agents, and RAG over SEC filings.</td>
</tr>
<tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
<td style="padding: 12px 16px; vertical-align: top;"><a href="/Docs?section=Predictor" target="_blank" style="color: #1a73e8; font-weight: 600;">Predictor</a></td>
<td style="padding: 12px 16px; color: #ccc;">LightGBM model predicting 5-day sector-relative returns. Retrains weekly on years of price history, infers daily with fresh market data. Provides a veto gate that blocks entries when the model predicts underperformance.</td>
</tr>
<tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
<td style="padding: 12px 16px; vertical-align: top;"><a href="/Docs?section=Executor" target="_blank" style="color: #1a73e8; font-weight: 600;">Executor</a></td>
<td style="padding: 12px 16px; color: #ccc;">Rule-based position sizing, risk management, and trade execution on Interactive Brokers. Enforces position limits, sector caps, and graduated drawdown response. Intraday daemon uses technical triggers to time entries.</td>
</tr>
<tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
<td style="padding: 12px 16px; vertical-align: top;"><a href="/Docs?section=Backtester" target="_blank" style="color: #1a73e8; font-weight: 600;">Backtester</a></td>
<td style="padding: 12px 16px; color: #ccc;">Signal quality analysis, parameter optimization, and portfolio simulation. Auto-tunes scoring weights, risk parameters, and veto thresholds. Writes updated configs back to S3 for all downstream modules.</td>
</tr>
<tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
<td style="padding: 12px 16px; vertical-align: top;"><a href="/Docs?section=Dashboard" target="_blank" style="color: #1a73e8; font-weight: 600;">Dashboard</a></td>
<td style="padding: 12px 16px; color: #ccc;">Streamlit monitoring interface for portfolio performance, signal quality, research theses, and system health. Read-only views over S3 data.</td>
</tr>
<tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
<td style="padding: 12px 16px; vertical-align: top;"><a href="/Docs?section=Data" target="_blank" style="color: #1a73e8; font-weight: 600;">Data</a></td>
<td style="padding: 12px 16px; color: #ccc;">Centralized data collection: ArcticDB price store (909 tickers), macro indicators, alternative data fetchers, feature store. Runs as the first step in both Saturday and daily pipelines.</td>
</tr>
<tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
<td style="padding: 12px 16px; vertical-align: top;"><a href="/Docs?section=Evaluation" target="_blank" style="color: #1a73e8; font-weight: 600;">Evaluation</a></td>
<td style="padding: 12px 16px; color: #ccc;">Weekly system report card with A-F grades for every component, precision/recall/F1 at each decision boundary, predictor confusion matrix, and grade trend tracking.</td>
</tr>
<tr>
<td style="padding: 12px 16px; vertical-align: top;"><a href="/Docs?section=Data+Dictionary" target="_blank" style="color: #1a73e8; font-weight: 600;">Data Dictionary</a></td>
<td style="padding: 12px 16px; color: #ccc;">Schema reference for all databases, CSV exports, and JSON data contracts used across the system.</td>
</tr>
</table>

---

### Source Code

All seven repos are open source on GitHub:

- [alpha-engine](https://github.com/cipher813/alpha-engine) — Executor + system overview
- [alpha-engine-research](https://github.com/cipher813/alpha-engine-research) — Research
- [alpha-engine-predictor](https://github.com/cipher813/alpha-engine-predictor) — Predictor
- [alpha-engine-backtester](https://github.com/cipher813/alpha-engine-backtester) — Backtester
- [alpha-engine-dashboard](https://github.com/cipher813/alpha-engine-dashboard) — Dashboard
- [alpha-engine-data](https://github.com/cipher813/alpha-engine-data) — Data
- [alpha-engine-docs](https://github.com/cipher813/alpha-engine-docs) — Documentation index
