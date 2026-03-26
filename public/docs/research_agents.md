## Research — ReAct Agents

This deep dive covers how the Research module uses the ReAct (Reasoning + Acting)
pattern to build LLM agents that analyze stocks using real-time data tools.

---

### What Is a ReAct Agent?

A ReAct agent is an LLM that can **reason** about a task and **act** by calling
tools in a loop. Instead of generating a single response, the agent:

1. **Thinks** about what information it needs
2. **Acts** by calling a tool (e.g., fetch analyst consensus)
3. **Observes** the tool's output
4. **Repeats** until it has enough information to produce a final answer

This pattern allows the LLM to dynamically decide which data sources to consult
based on what it discovers, rather than following a rigid script.

---

### Implementation

The Research module uses LangGraph's `create_react_agent` with LangChain's
`@tool` decorator to build agents:

```python
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic

# Tools are plain Python functions decorated with @tool
@tool
def get_technical_indicators(tickers: list[str]) -> dict:
    """Get RSI, MACD, moving averages, and momentum for given tickers."""
    # ... fetch and compute indicators ...
    return indicators

# Create the agent with a model and list of tools
model = ChatAnthropic(model="claude-haiku-4-5-20251001")
agent = create_react_agent(model, tools=[get_technical_indicators, ...])
```

The `@tool` decorator registers the function's name, docstring, and type hints
as a tool schema that the LLM can invoke. The agent autonomously decides which
tools to call and in what order.

---

### Tool Architecture

Tools are organized into two categories, created via **factory functions** that
close over shared context (price data, technical scores, prior theses):

#### Quantitative Tools

Created by `create_quant_tools(context)`:

| Tool | What It Does |
|------|-------------|
| `screen_by_volume` | Filter tickers by 20-day average volume |
| `get_technical_indicators` | RSI, MACD, MA ratios, momentum, ATR%, composite score |
| `get_analyst_consensus` | Rating, analyst count, mean target, upside % |
| `get_balance_sheet` | Debt/equity, current ratio, PE, PB, margins |
| `get_price_performance` | 5/20/60-day returns + current price |
| `get_options_flow` | Put/call ratio, IV rank, expected move |

#### Qualitative Tools

Created by `create_qual_tools(context)`:

| Tool | What It Does |
|------|-------------|
| `get_news_articles` | Recent headlines and excerpts (7-day window) |
| `get_analyst_reports` | Consensus, rating changes, earnings surprises |
| `get_insider_activity` | Cluster buying, unique buyers, net sentiment |
| `get_sec_filings` | Recent 8-K, 10-K, 10-Q filings |
| `get_prior_thesis` | Previous bull/bear case, catalysts, risks |
| `get_options_flow` | Put/call, IV rank, expected move |
| `get_institutional_activity` | 13F accumulation signals |
| `query_filings` | RAG semantic search over SEC filings + thesis history |

---

### Context Closure Pattern

Tools need access to shared data (price history, pre-computed technical scores,
prior investment theses) without passing it through the LLM. The factory pattern
solves this:

```python
def create_quant_tools(context: dict) -> list:
    """Create quant tools with shared context closed over."""
    price_data = context["price_data"]
    tech_scores = context["technical_scores"]

    @tool
    def get_technical_indicators(tickers: list[str]) -> dict:
        # Access price_data and tech_scores from closure
        return compute_indicators(price_data, tech_scores, tickers)

    @tool
    def get_price_performance(tickers: list[str]) -> dict:
        return compute_returns(price_data, tickers)

    return [get_technical_indicators, get_price_performance, ...]
```

This keeps expensive data (1 year of OHLCV for ~900 stocks) loaded once and
shared across all tool calls without serializing it through the LLM context.

---

### Model Allocation

The system uses different Claude models for different tasks based on
the reasoning demands of each stage:

| Task | Model | Why |
|------|-------|-----|
| Per-ticker analysis (quant/qual) | Claude Haiku | High volume (~20-25 stocks), fast throughput |
| Cross-stock ranking | Claude Sonnet | Requires comparing candidates, higher reasoning |
| Macro analysis | Claude Sonnet | Complex synthesis across sectors |
| Synthesis judge | Claude Sonnet | Resolving divergent sub-scores |
| Candidate debate | Claude Sonnet | Bull/bear argumentation quality |

Haiku handles the parallelized per-ticker work where speed and throughput matter most.
Sonnet handles the synthesis tasks where reasoning quality drives signal accuracy.

---

### Agent Execution Flow

Within a single sector team:

```
Quant Analyst (Haiku + quant tools)
  → Agent decides: "I need technicals for these 10 stocks"
  → Calls get_technical_indicators → observes results
  → "Now let me check analyst consensus for the top 5"
  → Calls get_analyst_consensus → observes
  → "And balance sheet health"
  → Calls get_balance_sheet → observes
  → Produces: ranked list with quant scores

Qual Analyst (Haiku + qual tools)
  → "Let me check recent news for top candidates"
  → Calls get_news_articles for each ticker
  → "What do the SEC filings say about risks?"
  → Calls query_filings (RAG) → semantic search results
  → "Any insider buying activity?"
  → Calls get_insider_activity → observes
  → Produces: qual scores + narrative for each ticker

Peer Review (Sonnet, no tools)
  → Single structured evaluation of both analysts' outputs
  → 4-dimension rubric: conviction, risk, timeliness, thesis quality
  → Produces: final 2-3 recommendations for the sector
```

---

### Parallelism

The six sector teams run in parallel via LangGraph's `Send()` mechanism.
Each `Send()` dispatches an independent sector team (along with the macro
economist and exit evaluator) to execute concurrently in LangGraph's thread
pool. Within each team, the three stages run sequentially — quant analyst,
then qual analyst, then peer review — because each stage depends on the
output of the previous one. This design parallelizes across sectors (the
most expensive axis) while keeping the per-sector pipeline simple and
deterministic.
