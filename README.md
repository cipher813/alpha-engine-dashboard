# Alpha Engine Dashboard

Read-only Streamlit dashboard for monitoring the full Alpha Engine system: portfolio performance, signal quality trends, research history, backtester output, and trade audit trail.

> Part of [Nous Ergon: Alpha Engine](https://github.com/cipher813/alpha-engine).

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
| Home | 15 min | System health, today's snapshot, signals, market context |
| Portfolio | 15 min | NAV vs SPY, daily alpha, drawdown, current positions |
| Signals | 15 min | Full signal table with sub-scores, date picker, ticker detail |
| Signal Quality | 1 hr | Accuracy trends, score buckets, regime breakdown, weight history |
| Research | 1 hr | Per-ticker score history, conviction timeline, thesis outcomes |
| Backtester | 1 hr | Parameter sweep heatmap, attribution, weight recommendations |
| Trade Log | 15 min | Full trade audit trail with filters and CSV export |
| Predictor | 15 min | GBM predictions, hit rate, IC, calibration |
| Slippage | 15 min | Execution quality: fill price vs order price, by action/regime |

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
│   ├── 2_Signals.py
│   ├── 3_Signal_Quality.py
│   ├── 4_Research.py
│   ├── 5_Backtester.py
│   ├── 6_Trade_Log.py
│   ├── 7_Predictor.py
│   └── 8_Slippage.py
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

## Opportunities for Improvement

### Missing Views

- **Sector allocation visualization** — can't see portfolio concentration by sector. Essential for monitoring the 25% sector limit.
- **Veto status display** — executor has a veto gate but the dashboard can't show which ENTER signals are currently blocked by the predictor.
- **Correlation/concentration analysis** — can't see if holdings are clustered in correlated stocks (e.g., MSFT + AAPL + GOOGL all >0.8 correlation).
- **Position-level P&L** — can't see entry price, unrealized P&L, or days held for each position.

### Missing Analysis Views

- **Model drift tracking** — predictor page shows 30-day rolling hit rate but no long-term trend (6-month degradation chart).
- **Regime-specific alpha tracking** — can't see portfolio alpha split by bull vs bear markets.
- **Win rate confidence intervals** — accuracy by score bucket shown without sample sizes or confidence bands.
- **Sector rotation tracking** — can't see how sector allocations have shifted over time.
- **Drawdown recovery speed** — can't measure how quickly the portfolio recovers from drawdowns.

### System Health

- **Health checks lack historical context** — "Yesterday's signals present" shows a yellow badge but should be red after 48 hours.
- **Backtester health only checks recency** — doesn't check if the backtest actually failed, only if it ran recently.
- **No executor failure detection** — IB Gateway health only checks that an eod_pnl entry exists, not whether the executor actually processed trades.

### Data Loading

- **Silent failures in S3 loader** — `_s3_get_object()` returns None on any exception without logging. Network errors, permission denials, and missing keys all look the same.
- **Fragile schema assumptions** — hardcoded SQL and JSON field names throughout. Schema drift from upstream modules breaks pages silently.

---

## EC2 Memory Constraints

The micro instance (t3.micro, 1GB RAM) runs two Streamlit processes:

- **Port 8501** — Private dashboard (`dashboard.nousergon.ai`, Cloudflare Access protected)
- **Port 8502** — Public portfolio page (`nousergon.ai`)

With ~60-150MB per Streamlit process plus nginx and OS overhead, the instance runs near its memory limit. Mitigations in place:

- **1GB swap file** (`/swapfile`) prevents OOM freezes
- **systemd MemoryMax=300M** per Streamlit service caps runaway memory

If memory issues recur, options to reduce footprint:

1. **Upgrade to t3.small** (2GB RAM, ~$6/month more) — simplest, doubles headroom
2. **Static public site** — render portfolio chart as static HTML via cron, serve with nginx directly (zero RAM for public page)
3. **Merge into single Streamlit app** — add public pages to dashboard, use Cloudflare Access path rules to protect `/dashboard/*`. Requires refactoring the public app's custom CSS/layout into conditional page logic.

---

## Related Modules

- [`alpha-engine`](https://github.com/cipher813/alpha-engine) — Executor (trade execution + system overview)
- [`alpha-engine-research`](https://github.com/cipher813/alpha-engine-research) — Autonomous LLM research pipeline
- [`alpha-engine-predictor`](https://github.com/cipher813/alpha-engine-predictor) — GBM predictor (5-day alpha predictions)
- [`alpha-engine-backtester`](https://github.com/cipher813/alpha-engine-backtester) — Signal quality analysis and parameter optimization

---

## License

MIT — see [LICENSE](LICENSE).
