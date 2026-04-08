## Research — LangGraph

This deep dive covers how the Research module uses LangGraph to orchestrate
its multi-agent pipeline, manage state, and coordinate parallel execution.

*GitHub: [alpha-engine-research](https://github.com/cipher813/alpha-engine-research) · Last updated: 2026-04-08*

---

### Why LangGraph?

The research pipeline involves multiple interdependent stages with complex
data flow: scanning hundreds of stocks, running LLM agents in parallel,
aggregating scores, resolving disagreements, and writing results. LangGraph
provides:

- **Typed state management** — A shared state dictionary that flows between
  nodes, with reducer functions handling concurrent writes
- **Graph-based orchestration** — Nodes and edges define execution order,
  with conditional branching where needed
- **Parallel execution** — `Send()` API dispatches work to multiple nodes
  simultaneously
- **Fault tolerance** — Node failures are captured in state rather than
  crashing the entire pipeline

---

### StateGraph Basics

A LangGraph `StateGraph` is defined by three things:

1. **State schema** — A TypedDict defining all fields that flow through the graph
2. **Nodes** — Python functions that read from and write to state
3. **Edges** — Connections between nodes defining execution order

```python
from langgraph.graph import StateGraph

class ResearchState(TypedDict):
    run_date: str
    price_data: dict
    current_population: dict
    investment_theses: dict
    # ... more fields

graph = StateGraph(ResearchState)
graph.add_node("fetch_data", fetch_data_fn)
graph.add_node("scanner", run_scanner_fn)
graph.add_node("agents", run_agents_fn)
graph.add_edge("fetch_data", "scanner")
graph.add_edge("scanner", "agents")
# ... more edges
app = graph.compile()
```

Each node receives the full state dict and returns a partial dict of fields
to update. LangGraph merges the updates back into the state automatically.

---

### State Design

The Research state schema uses ~20 fields organized by pipeline stage:

**Inputs (set by `fetch_data`):**
- `run_date`, `price_data`, `macro_data`, `analyst_data`, `sector_map`
- `current_population` (existing tracked stocks from SQLite)
- `scanner_universe` (full S&P 500+400 ticker list)

**Agent outputs (set by analysis nodes):**
- `news_reports` / `news_scores` — Per-ticker news analysis
- `research_reports` / `research_scores` — Per-ticker fundamental analysis
- `macro_report` / `sector_modifiers` — Global macro context

**Enrichment data (set by fetcher nodes):**
- `revision_data`, `options_data`, `insider_data`, `institutional_data`

**Post-aggregation (set by scoring/evaluation nodes):**
- `investment_theses` — Fully scored thesis records
- `debate_results` — Bull/bear debate outcomes
- `new_population` — Updated tracked universe

---

### Reducer Functions

When multiple nodes write to the same state field (common in parallel
execution), LangGraph uses **reducer functions** to merge the writes:

```python
from typing import Annotated

def _take_last(existing, new):
    """Last write wins — for singleton fields."""
    return new

def _merge_dicts(existing, new):
    """Merge dictionaries — for team outputs that write different keys."""
    merged = existing.copy() if existing else {}
    merged.update(new)
    return merged

class ResearchState(TypedDict):
    macro_report: Annotated[str, _take_last]
    team_outputs: Annotated[dict, _merge_dicts]
```

This is critical for parallel sector teams. Each team writes its results
under its own team key (e.g., `{"technology": [...], "healthcare": [...]}`),
and `_merge_dicts` combines them without conflicts.

---

### Send() for Parallel Execution

LangGraph's `Send()` API dispatches work to multiple instances of a node
simultaneously. The architecture uses this to run sector teams in parallel:

```python
from langgraph.constants import Send

def dispatch_all(state: ResearchState) -> list[Send]:
    """Fan out to sector teams + macro + exit evaluator."""
    sends = []
    for team_id, tickers in state["sector_assignments"].items():
        sends.append(Send("sector_team", {
            "team_id": team_id,
            "tickers": tickers,
            "price_data": state["price_data"],
            # ... shared context
        }))
    sends.append(Send("macro_economist", {
        "macro_data": state["macro_data"],
    }))
    sends.append(Send("exit_evaluator", {
        "current_population": state["current_population"],
    }))
    return sends
```

This creates 8 parallel work items (6 sector teams + macro + exit evaluator)
that execute concurrently in LangGraph's thread pool. Results are collected
and merged via reducer functions before the next sequential node runs.

---

### Conditional Edges

Some transitions depend on state. For example, the synthesis judge only
runs if there are divergent scores to resolve:

```python
def should_run_judge(state: ResearchState) -> str:
    divergent = [t for t in state["investment_theses"]
                 if abs(t["news_score"] - t["research_score"]) > threshold]
    if divergent:
        return "synthesis_judge"
    return "thesis_updater"  # Skip judge, go directly to updater

graph.add_conditional_edges("score_aggregator", should_run_judge)
```

---

### Graph Topology

```
fetch → dispatch ──→ [team_tech, team_health, team_fin, team_ind, team_cons, team_def, macro, exit]
                      ↓ (fan-in)
                   merge → scorer → archive → email
```

The expensive analysis stage fans out to 8 parallel nodes (6 sector teams +
macro economist + exit evaluator). The merge node collects all results before
scoring.

---

### Error Handling

Nodes capture failures in state rather than raising exceptions that would
crash the pipeline:

- **Agent failures:** If a per-ticker agent fails (LLM timeout, tool error),
  the failure is logged and the ticker is skipped. If >50% of agents fail,
  a critical alert is triggered.
- **Data fetch failures:** Missing data for a ticker results in `None` values
  that downstream nodes handle gracefully (e.g., signal boosts default to 0).
- **Idempotency:** The Lambda handler checks for existing output before running,
  so a retry after partial failure doesn't produce duplicate signals.
