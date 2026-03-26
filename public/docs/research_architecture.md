## Research — Architecture & Stack

This deep dive covers the Research module's graph topology, node pipeline,
and how data flows from raw market data to scored investment signals.

---

### Graph Architecture

The Research module is built as a **LangGraph StateGraph** — a directed acyclic
graph where each node performs one stage of the research pipeline. State is passed
between nodes as a typed dictionary, and the graph runs synchronously from start
to finish.

The graph uses LangGraph's `Send()` API to fan out work to 6 independent sector
teams running in parallel, then merges results before scoring.

---

### Pipeline

```
fetch_data
  → dispatch_all ──Send()──→ [6 sector teams + macro + exit evaluator]
  → merge_results (fan-in)
  → score_aggregator
  → archive_writer
  → email_sender_node
```

**Six sector teams:** Technology, Healthcare, Financials, Industrials, Consumer,
Defensives. Each team runs three stages:

1. **Quant Analyst** — ReAct agent with quantitative tools screens sector stocks
2. **Qual Analyst** — ReAct agent with qualitative tools (including RAG) scores candidates
3. **Peer Review** — Single LLM call evaluates the team's picks against a rubric

The **macro economist** and **exit evaluator** run in parallel with the sector teams,
not sequentially after them.

**Key nodes:**

| Node | What It Does |
|------|-------------|
| `fetch_data` | Load population from SQLite, 1y price data, macro data (FRED), prior reports |
| `dispatch_all` | Fan out to 6 sector teams + macro economist + exit evaluator via `Send()` |
| `merge_results` | Collect all team picks, compute sector fill order, open slots |
| `score_aggregator` | Composite scores (news + research + macro shift + signal boosts) |
| `archive_writer` | Write signals.json + theses to S3 and SQLite |
| `email_sender_node` | Send morning research report |

Within each sector team, the quant and qual analysts run as ReAct agents with
tool access. A three-stage scanner pipeline (900 → 50 → 35) runs before dispatch
to narrow the candidate universe.

---

### State Management

The graph state is a Python `TypedDict` with annotated reducer functions that handle
concurrent writes from parallel nodes:

- **`_take_last()`** — For singleton fields (macro report, market regime). Last write wins.
- **`_merge_dicts()`** — For team outputs. Each team writes to its own key; the merge
  combines all dictionaries without conflicts.

Key state fields:
- `current_population` — The tracked universe (20-25 tickers with scores and theses)
- `scanner_universe` — Full S&P 500+400 for scanning
- `investment_theses` — Scored thesis records per ticker
- `sector_modifiers` — Per-sector macro multipliers from the macro economist

---

### Scoring Pipeline

After agents complete their analysis, the `score_aggregator` node computes
final scores:

```
base_score = news_score × w_news + research_score × w_research    [0-100]
macro_shift = (sector_modifier - 1.0) / 0.30 × 10                [-10, +10]
signal_boosts = O10 + O11 + O12 + O13 + short_interest + 13F     [capped ±10]
final_score = clip(base_score + macro_shift + signal_boosts, 0, 100)
```

**Signal boost sources:**

| Boost | Source | What It Captures |
|-------|--------|-----------------|
| O10 (PEAD) | Earnings surprises | Post-earnings announcement drift |
| O11 | EPS revision streaks | Analyst estimate momentum |
| O12 | Options flow | Put/call ratio, IV rank (contrarian) |
| O13 | Insider activity | Cluster buying by executives |
| Short interest | Float data | High short interest on BUY signals |
| 13F | Institutional filings | Large fund accumulation patterns |

---

### Technology Stack

| Component | Technology | Role |
|-----------|-----------|------|
| Orchestration | LangGraph (StateGraph) | Node pipeline, state management, fan-out |
| LLM agents | LangChain + Anthropic | ReAct agents with tool access |
| Models | Claude Haiku (per-ticker), Sonnet (synthesis) | Task-appropriate model allocation |
| Data APIs | yfinance, FMP, FRED, SEC EDGAR | Market data, fundamentals, macro |
| Semantic search | Voyage embeddings + pgvector | RAG over SEC filings |
| Storage | S3 + SQLite | Signal output + historical persistence |
| Compute | AWS Lambda (Docker on ECR) | Weekly serverless execution |

---

### Infrastructure

The Research module runs as an **AWS Lambda function** packaged as a Docker container
on ECR. Key deployment details:

- **Trigger:** EventBridge rule fires Monday 06:00 UTC
- **Runtime:** Python 3.12, ~8 min execution
- **Memory:** 1024 MB Lambda allocation
- **Idempotency:** Checks if `signals/{date}/signals.json` already exists before running
- **Output:** `signals.json` written to S3, consumed by Predictor + Executor next morning
