---
title: "Multi-Agent Research: How 6 LLM Teams Analyze 900 Stocks"
date: 2026-03-27
description: "Inside Nous Ergon's sector-specialized research pipeline — ReAct agents, RAG over SEC filings, and the CIO that picks the portfolio"
tags: ["ai-engineering", "llm", "multi-agent", "rag", "langgraph"]
canonical_url: "https://nousergon.ai/blog/posts/multi-agent-research/"
ShowToc: true
TocOpen: true
---

In [Post 1](/blog/posts/building-autonomous-alpha-engine/), I introduced Nous Ergon — an autonomous trading system that splits intelligence across four layers: LLM agents for research judgment, ML for pattern recognition, deterministic rules for execution, and a backtester for system-wide learning. This post goes inside the Research module — the layer where LLMs are found hard at work.

## What a Weekend Run Looks Like

Over the weekend, an AWS Lambda fires. It loads the S&P 500 and S&P 400 — roughly 900 mid-to-large-cap US stocks — along with recent price history, and then distributes them across six sector-specialized teams that run in parallel. Each team screens, analyzes, and debates their sector's best opportunities. A CIO agent evaluates the top picks across all teams and decides which stocks enter or exit the portfolio.

The pipeline writes a single `signals.json` file to S3 that the rest of the system — Predictor, Executor, Backtester — consumes. By the time markets open Monday morning, the week's research is done.

This post walks through how this process works.

## The Funnel: 900 → ~25

There's no single bottleneck filter narrowing the universe. Instead, the ~900 stocks are distributed across six sector teams based on their GICS sector classification — Technology, Healthcare, Financials, Industrials, Consumer, and Defensives. Each team receives its full sector allocation — typically 100–200 stocks — and runs its own screening independently.

Within each team, the process follows a four-stage pipeline:

**1. Quant Analyst** — A ReAct agent with access to screening tools: volume filters, technical indicators, analyst consensus, balance sheet ratios, price performance, and options flow. The quant receives the full sector ticker list and autonomously decides which tools to call, which metrics to prioritize, and how to narrow from ~150 candidates down to a top 10. Each sector team is parameterized with focus metrics — the Technology team sees hints like revenue growth and R&D intensity, while the Financials team sees ROE and net interest margin — though the agent ultimately decides its own screening strategy.

**2. Qual Analyst** — Also a ReAct agent, reviewing the quant's top picks with deeper qualitative tools: recent news, insider transactions, institutional accumulation, SEC filing search via RAG, and lessons from past signal failures. The qual analyst adds the narrative layer — why this stock, why now, what could go wrong.

**3. Peer Review** — Quant and qual collaborate to agree on 2–3 final recommendations, each backed by a bull case, bear case, specific catalysts, and a conviction level.

**4. CIO Evaluation** — All six teams run in parallel, producing 12–18 total recommendations. A CIO agent (single Sonnet call) evaluates them together across four dimensions: team conviction, macro alignment, portfolio fit, and catalyst specificity. The CIO loads its prior decisions to maintain portfolio continuity — it's not assembling a new portfolio from scratch each week, but rather rotating a handful of out-of-favor positions (typically 2–10) and replacing them with the strongest new candidates from the investment committee review.

The result is a ~25-stock portfolio — sector-balanced, thesis-backed, refreshed weekly.

Here's what a quant analyst tool looks like in practice — a LangChain `@tool` that the ReAct agent calls when it wants balance sheet data for its top candidates:

```python
@tool
def get_balance_sheet(tickers: list[str]) -> str:
    """Get balance sheet metrics: debt/equity, current ratio, PE, revenue growth, gross margins."""
    import yfinance as yf

    results = {}
    for t in tickers[:20]:
        info = yf.Ticker(t).info
        results[t] = {
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "revenue_growth": info.get("revenueGrowth"),
            "gross_margins": info.get("grossMargins"),
        }
    return json.dumps(results)
```

The agent passes in a list of tickers from its sector subset — typically its top candidates after an initial volume and momentum screen. It sees the tool's docstring and decides when balance sheet data is relevant to its analysis. It might call `get_balance_sheet` for a value screen, then `get_technical_indicators` for momentum confirmation — the reasoning loop drives the sequence, not hardcoded logic. (Today these tools pull data live from yfinance on each run. Longer term, the plan is to read from the predictor's feature store, which already pre-computes many of the same fundamental and technical metrics — faster, more reliable, and avoids rate limiting during the pipeline.)

## Why Sector Teams?

Comparing a biotech awaiting an FDA decision to a utility with stable regulated earnings is an apples-to-oranges problem. The metrics that matter, the catalysts that move prices, and the risks worth watching are fundamentally different. A single generalist prompt can't evaluate all of these well.

Sector teams solve this by making comparisons *within* a peer group. The Healthcare team compares drug pipelines to drug pipelines. The Financials team compares credit portfolios to credit portfolios. Each team's prompts are parameterized with sector-specific focus metrics — the Technology quant is nudged toward revenue growth and R&D intensity, while the Defensives quant is nudged toward dividend yield and payout stability. When stocks are evaluated against true peers, the rankings should be more meaningful and the catalysts more specific.

An important caveat: I'm describing the *intended* behavior. Whether each sector's quant actually uses different tools and metrics in practice — and whether that differentiation produces better recommendations — is an empirical question. The system logs every tool call and iteration count per agent via LangSmith traces, which means I'm accumulating the data needed to answer it. As the dataset grows, I'll be able to analyze whether the Technology quant really does call `get_balance_sheet` less frequently than the Financials quant, or whether agent behavior converges across sectors despite the sector-specific parameterization. This kind of agentic evaluation is a planned area of investigation.

## ReAct Agents and the Tool Ecosystem

The qual analysts aren't just reading pre-fetched data. They're [ReAct agents](https://arxiv.org/abs/2210.03629) — they reason about what information they need and call tools to get it. Each agent has several tools available:

| Tool | Data Source | What It Provides |
|------|-------------|-----------------|
| News articles | Yahoo Finance RSS | Headlines, sentiment, catalysts from recent coverage |
| Analyst consensus | FMP API | Ratings, price targets, earnings surprises |
| Insider activity | SEC EDGAR Form 4 | Cluster buys/sells, net sentiment |
| SEC filings | SEC EDGAR | 8-K event filings |
| Prior thesis | SQLite archive | Last week's bull/bear case for continuity |
| Options flow | yfinance | Put/call ratio, IV rank, expected move |
| Institutional activity | SEC EDGAR 13F | Fund accumulation/distribution |
| **Filing search (RAG)** | Neon pgvector | Semantic search over 10-K/10-Q full text |
| **Lessons (episodic memory)** | SQLite | Past signal failures and extracted lessons |

The last two tools deserve deeper explanation — they represent two different forms of persistent knowledge that the agents build up over time.

### RAG: Searching SEC Filings

The `query_filings` tool uses retrieval-augmented generation (RAG) to search hundreds of SEC filings stored as embedded chunks in a vector database. When the agent asks "What are the competitive risks in the memory semiconductor market?", it gets real Risk Factors text from Micron's latest 10-Q — not a summary, but the actual filing language that management signed off on.

This is where RAG adds depth beyond headlines. An analyst consensus report tells you the price target is $150. The 10-K Risk Factors section tells you *why* that target might be wrong — competitive threats management disclosed, regulatory risks they're navigating, customer concentration they're exposed to. The qual agent can search for this context on demand, and it integrates naturally because it's just another tool in the ReAct loop.

Under the hood, the RAG retrieval is a metadata-filtered vector similarity search. The query is embedded using Voyage, filtered by ticker and document type, then ranked by cosine similarity against an HNSW (Hierarchical Navigable Small World) index over thousands of filing chunks. The agent gets back the most relevant excerpts with source metadata — filing type, date, and section label.

If RAG is unavailable (database down, embedding service unreachable), the agent proceeds with the other tools. New capabilities are additive — they never block the pipeline.

### Agent Memory: Learning from Mistakes

The memory system gives agents access to accumulated knowledge from past performance.

**Episodic memory** captures lessons from past signal failures. The Research module tracks the outcome of every BUY signal it generates — specifically, whether each signal beat the S&P 500 over a 10-day window (via the `score_performance` table in the research database). For signals that underperformed, the system uses an LLM call to extract a structured lesson — what the thesis was, what the market conditions were (regime, VIX level), and what the agent should watch for next time. When a qual analyst evaluates a stock, it can call `get_lessons` to retrieve any prior lessons for that ticker. If the system recommended SMCI three months ago based on rising data center demand but the stock collapsed on accounting concerns, the qual analyst sees that context before making its current recommendation.

Beyond the tool-based episodic memory, the system also accumulates **semantic observations** — cross-agent insights about sector dynamics and macro reasoning. After each run, the system extracts thematic patterns from sector team reports, macro analysis, and CIO decisions — observations like "semiconductor stocks are rotating from memory to AI accelerators" or "the CIO has been underweighting utilities due to rate sensitivity." These observations are loaded as context for the qual analysts in subsequent runs, giving them awareness of patterns that emerged from other teams' analysis in prior weeks. Repeated observations are reinforced rather than duplicated, so persistent themes naturally rise in prominence.

Both memory types are stored in SQLite and accumulate over time. The episodic memory teaches the system not to repeat specific mistakes; the semantic observations help it recognize recurring patterns.

## Living Theses and Material Triggers

The agents don't start from scratch each week. For every stock in the population, the system maintains a living investment thesis — a structured document covering the bull case, bear case, key catalysts, risk factors, and conviction level.

Each week, agents receive the prior thesis — but they don't blindly rewrite it. Thesis updates are triggered only when something material has changed: a significant news event, a price move exceeding 2x the stock's average true range (ATR), an analyst rating revision, approaching earnings, insider cluster activity, or a shift in the sector's macro regime. If nothing material has happened, the thesis is preserved as-is. This prevents the stateless behavior where an LLM rewrites a perfectly good thesis just because it was asked to, potentially losing nuance that accumulated over prior weeks.

Conviction tracking captures the momentum of the thesis itself: a stock whose bull case keeps strengthening gets "rising" conviction, while one where risks are accumulating gets "declining." These signals feed directly into position sizing downstream — the Executor gives larger positions to rising conviction and smaller positions to declining.

All theses are archived in S3 and SQLite, creating a historical record of what the system believed about each stock and when.

## Observability: Validating the Pipeline

With six teams running in parallel, a macro agent, an exit evaluator, and a CIO all executing autonomously, things can go wrong silently. A sector team might fail to produce recommendations. The macro agent might not load its prior report. A node might execute out of order.

To catch these issues, the system runs trajectory validation after every pipeline execution using LangSmith. The validator checks that all required nodes fired (all 6 sector teams, macro, CIO, consolidator), that they executed in the correct order, and that the graph completed successfully. Currently, failures are logged to CloudWatch — surfacing them more prominently (via Telegram alerts or the morning briefing email) is a planned improvement.

This is the kind of observability investment that doesn't add alpha directly, but prevents the silent degradation that erodes it over time.

## What I'm Still Iterating On

This is an active project, not a finished product. Some areas I'm working through:

- **RAG efficacy** — The filing search infrastructure is in place and wired to the qual analysts. Whether access to full SEC filing text produces materially better theses compared to headlines and consensus data alone is a question I want to answer over time.
- **Document coverage** — SEC 10-K/10-Q filings are ingested. Earnings call transcripts are a natural next source, though the data pipeline for transcripts is still in progress.
- **Memory accumulation** — The episodic and semantic memory systems are new. As the lesson database grows, I'll be watching whether agents actually use the memory tools effectively and whether the lessons improve signal quality.
- **Agentic evaluation** — I'm logging tool calls and agent iterations per team, which will eventually let me answer questions like: do sector teams actually behave differently? Do agents that use more tools produce better signals? This requires time — the system needs to accumulate enough signal history for these evaluations to be statistically meaningful. Building up this kind of proprietary dataset is a natural limiting factor on how fast the research layer can develop and be evaluated.
- **Scoring calibration** — The backtester auto-tunes scoring weights weekly, but needs more sample history before the optimization converges.

## What's Next

The Research module identifies *what's attractive*. The next posts in this series cover how the rest of the system acts on those signals:

- **ML Prediction** — LightGBM feature engineering, sector-neutral labeling (benchmarking each stock against its sector ETF rather than the broad market), and the veto gate
- **Autonomous Backtesting** — How the system evaluates its own signal quality and auto-tunes parameters
- **Execution** — The order book, intraday technical triggers, and risk management

The full signal chain: Research identifies what's attractive → Predictor validates short-term timing → Executor sizes and executes positions → Backtester measures what worked and feeds optimized parameters back upstream. Each module reads from S3 and is independently replaceable — the architecture is designed so I can swap any component without touching the others.

---

*Nous Ergon is an open-source autonomous trading system. Follow along at [nousergon.ai](https://nousergon.ai) or explore the code on [GitHub](https://github.com/cipher813).*
