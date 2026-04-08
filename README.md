# alpha-engine-dashboard

[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-218_passing-brightgreen.svg)]()
[![Coverage](https://img.shields.io/badge/coverage-81%25-green.svg)]()

> Read-only Streamlit dashboard for monitoring the full Alpha Engine system: portfolio performance, system report card, signal quality, execution evaluation, research history, and trade audit trail.

**Part of the [Nous Ergon](https://nousergon.ai) autonomous trading system.**
See the [system overview](https://github.com/cipher813/alpha-engine#readme) for how all modules connect, or the [full documentation index](https://github.com/cipher813/alpha-engine-docs#readme).

---

## Role in the System

The Dashboard is the observation layer. It reads data from three upstream modules via S3 (Research, Executor, Predictor) and never writes to S3 or any database. It surfaces the information needed to identify when signal quality is degrading, when risk parameters need adjustment, or when specific sectors are underperforming.

---

## Quick Start

### Prerequisites

- Python 3.11+
- AWS credentials with read access to the `alpha-engine-research` S3 bucket

### Setup

```bash
git clone https://github.com/cipher813/alpha-engine-dashboard.git
cd alpha-engine-dashboard
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# No config changes needed for default setup
streamlit run app.py --server.port=8501
```

If your S3 bucket names differ from the defaults, edit `config.yaml`.

---

## Pages

| Page | Refresh | Purpose |
|------|---------|---------|
| Overview (Home) | 15 min | Pipeline status, today's activity, key KPIs, **system report card** (module grades), market context, alerts |
| Portfolio | 15 min | NAV vs SPY, daily alpha, drawdown, current positions, sector allocation |
| Signals & Research | 15 min | Full signal table with sub-scores, ticker drilldown with score history, conviction, thesis timeline |
| Analysis | 1 hr | Signal accuracy, backtester runs (with **component grade table** and **sector team grades**), and pipeline evaluation (lift + component diagnostics + self-adjustment) |
| Execution | 15 min | Trade log, **execution evaluation** (trigger scorecard, shadow book with P/R/F1, exit timing MFE/MAE), slippage monitor |
| Predictor | 15 min | GBM predictions, hit rate, IC, mode history, feature importance, calibration |
| System Health | 15 min | Module freshness, data volume, feedback loop maturity, feature store coverage + drift |

---

## Configuration

Edit `config.yaml` to change S3 bucket names, paths, or cache TTLs:

```yaml
s3:
  research_bucket: alpha-engine-research

cache_ttl:
  signals: 900      # 15 min
  trades: 900       # 15 min
  research: 3600    # 1 hour
  backtest: 3600    # 1 hour
```

---

## Data Sources

All data is **read-only** — the dashboard never writes to S3 or any database.

| Source | S3 Path | Cache |
|--------|---------|-------|
| Today's signals | `signals/{date}/signals.json` | 15 min |
| EOD P&L | `trades/eod_pnl.csv` | 15 min |
| Full trade log | `trades/trades_full.csv` | 15 min |
| Research database | `research.db` | 1 hr |
| Backtest output | `backtest/{date}/` | 1 hr |
| Scoring weights | `config/scoring_weights.json` | 1 hr |

---

## Key Files

```
alpha-engine-dashboard/
├── app.py                    # Home page (Streamlit entry point)
├── pages/
│   ├── 1_Portfolio.py
│   ├── 2_Signals_and_Research.py
│   ├── 3_Analysis.py
│   ├── 4_System_Health.py
│   ├── 6_Execution.py
│   └── 7_Predictor.py
├── loaders/
│   ├── s3_loader.py          # S3 download helpers with TTL caching
│   ├── db_loader.py          # SQLite read helpers (research.db)
│   └── signal_loader.py      # signals.json parsing
├── charts/                   # Plotly chart builders
├── config.yaml               # S3 bucket names and cache TTLs
├── requirements.txt
└── infrastructure/
    ├── dashboard.service     # systemd unit for persistence
    └── nginx.conf            # Optional SSL reverse proxy
```

---

## Deployment (EC2 + SSH Tunnel)

The dashboard runs on EC2 with port 8501 not publicly exposed. Access it via SSH tunnel.

### Start Streamlit on EC2

```bash
# On EC2 (one-time — survives terminal close)
cd ~/alpha-engine-dashboard
source .venv/bin/activate
nohup streamlit run app.py --server.port=8501 --server.headless=true > nohup.out 2>&1 &
```

### Open SSH Tunnel (Your Machine)

```bash
ssh -L 8501:localhost:8501 -N alpha-engine
# Then open http://localhost:8501
```

### Persistent Setup (systemd)

For automatic restart on reboot:

```bash
sudo cp infrastructure/dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable dashboard
sudo systemctl start dashboard
```

---

---

## EC2 Memory Constraints

The micro instance (t3.micro, 1GB RAM) runs two Streamlit processes:

- **Port 8501** — Private dashboard (`dashboard.nousergon.ai`, Cloudflare Access protected)
- **Port 8502** — Public portfolio page (`nousergon.ai`)

With ~60-150MB per Streamlit process plus nginx and OS overhead, the instance runs near its memory limit. Mitigations in place:

- **1GB swap file** (`/swapfile`) prevents OOM freezes
- **systemd MemoryMax=300M** per Streamlit service caps runaway memory

Database queries are capped at 50,000 rows (`_MAX_QUERY_ROWS` in `loaders/db_loader.py`) to prevent OOM on large tables. S3 `_s3_get_object()` retries transient errors up to 3 times with exponential backoff (1s, 2s, 4s).

If memory issues recur, options to reduce footprint:

1. **Upgrade to t3.small** (2GB RAM, ~$6/month more) — simplest, doubles headroom
2. **Static public site** — render portfolio chart as static HTML via cron, serve with nginx directly (zero RAM for public page)
3. **Merge into single Streamlit app** — add public pages to dashboard, use Cloudflare Access path rules to protect `/dashboard/*`. Requires refactoring the public app's custom CSS/layout into conditional page logic.
4. **Lower `_MAX_QUERY_ROWS`** — reduce from 50,000 if tables grow large. Monitor with System Health page.

---

## Related Modules

- [`alpha-engine`](https://github.com/cipher813/alpha-engine) — Executor + system overview
- [`alpha-engine-research`](https://github.com/cipher813/alpha-engine-research) — Autonomous LLM research pipeline
- [`alpha-engine-predictor`](https://github.com/cipher813/alpha-engine-predictor) — Meta-model predictor
- [`alpha-engine-backtester`](https://github.com/cipher813/alpha-engine-backtester) — Evaluation framework and parameter optimization
- [`alpha-engine-data`](https://github.com/cipher813/alpha-engine-data) — Centralized data collection and ArcticDB
- [`alpha-engine-docs`](https://github.com/cipher813/alpha-engine-docs) — Documentation index

---

## License

MIT — see [LICENSE](LICENSE).
