## Research Module

The Research module is the system's signal generator. It runs weekly (Saturday),
scanning the S&P 500 and S&P 400 (~900 stocks) to identify buy candidates,
maintain rolling investment theses, and produce composite attractiveness scores
for a tracked universe of 20-25 stocks.

*GitHub: [alpha-engine-research](https://github.com/cipher813/alpha-engine-research) · Last updated: 2026-04-08*

---

### Overview

The module combines quantitative screening with LLM-driven qualitative analysis.
A three-stage scanner filters ~900 stocks down to ~50 candidates. LLM agents then
perform deep analysis — reading news, analyst reports, SEC filings, and macro data —
to produce a composite score (0-100) for each stock.

**Alpha contribution:** The quality of research signals directly determines which
stocks enter the portfolio. Scores drive position sizing, and rating changes
(BUY/HOLD/SELL) trigger entries and exits.

---

### Key Concepts

- **Composite score:** Weighted blend of news sentiment and analyst research sub-scores,
  adjusted by sector-level macro modifiers and signal boosts from earnings, revisions,
  options flow, and insider activity
- **Scanner pipeline:** Three-stage quantitative filter (liquidity, momentum, deep value)
  that reduces the full universe to a manageable candidate set before LLM analysis
- **Sector teams:** Six independent analysis teams (Technology, Healthcare, Financials,
  Industrials, Consumer, Defensives) running in parallel via LangGraph
- **Population management:** The tracked universe rotates based on score-based tenure —
  weak performers get replaced by stronger candidates

---

### How It Works

```
Stage 1: Quant Filter       ~900 stocks → ~60    (liquidity, momentum, deep value)
Stage 2: Data Enrichment     ~60 → ~50            (balance sheet, analyst consensus)
Stage 3: LLM Ranking         ~50 → ~35            (Sonnet ranks candidates)
Stage 4: Deep Analysis       ~35 + incumbents     (sector teams with ReAct agents)
Stage 5: Scoring & Rating    all tracked stocks   (composite score, BUY/HOLD/SELL)
Stage 6: Output              signals.json → S3    (consumed by Predictor + Executor)
```

1. **Quantitative filtering** removes illiquid, low-momentum, and high-volatility
   stocks. Two parallel paths: momentum (strong technicals) and deep value (oversold
   with analyst support).

2. **Data enrichment** adds balance sheet data and analyst consensus. Overleveraged
   companies (debt/equity > 1.5x) are filtered out.

3. **LLM ranking** uses Claude Sonnet to rank the ~50 candidates by investment
   potential, selecting the top 35 for full analysis.

4. **Sector teams** run deep analysis using ReAct agents with tool access to news,
   analyst reports, SEC filings (via RAG), insider activity, and options flow.

5. **Scoring** produces a composite attractiveness score with macro adjustments and
   signal boosts. Each stock gets a BUY/HOLD/SELL rating based on score thresholds.

6. **Output** writes `signals.json` to S3, consumed by the Predictor and Executor
   the following morning.

---

### Quick Start

```bash
git clone https://github.com/cipher813/alpha-engine-research.git
cd alpha-engine-research
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Copy and configure
cp config/universe.yaml.example config/universe.yaml
cp config/scoring.yaml.example config/scoring.yaml

# Dry run (no S3 writes, no emails)
python local/run.py --dry-run
```

**Required environment variables:** `ANTHROPIC_API_KEY`, `FMP_API_KEY`, `FRED_API_KEY`,
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`

---

### Key Files

| File | Purpose |
|------|---------|
| `graph/research_graph.py` | LangGraph state machine orchestrator |
| `data/scanner.py` | Three-stage quantitative filter |
| `scoring/aggregator.py` | Composite score calculation |
| `agents/sector_teams/` | ReAct agents with quant and qual tools |
| `rag/` | Semantic search over SEC filings |
| `archive/manager.py` | S3 + SQLite persistence |
| `lambda/handler.py` | AWS Lambda entry point |

---

### Deep Dives

For more detail on specific aspects of the Research module:

- <a href="/Docs?section=Research+%E2%80%94+Architecture+%26+Stack" target="_blank" style="color: #1a73e8;">Architecture & Stack</a> — Graph topology, node pipeline, data flow
- <a href="/Docs?section=Research+%E2%80%94+ReAct+Agents" target="_blank" style="color: #1a73e8;">ReAct Agents</a> — How LLM agents use tools for stock analysis
- <a href="/Docs?section=Research+%E2%80%94+LangGraph" target="_blank" style="color: #1a73e8;">LangGraph</a> — State machine design, parallel execution, reducers
- <a href="/Docs?section=Research+%E2%80%94+RAG+%26+Vector+DB" target="_blank" style="color: #1a73e8;">RAG & Vector DB</a> — Semantic search over SEC filings and thesis history
