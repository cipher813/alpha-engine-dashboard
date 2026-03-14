# Alpha Engine Dashboard

A read-only operational dashboard for monitoring the full alpha-engine system: live signals, portfolio performance, signal quality trends, backtester output, and research history.

## Pages

| Page | URL | Refresh | Purpose |
|------|-----|---------|---------|
| Home | `/` | 15 min | System health, today's snapshot, signals, market context |
| Portfolio | `/Portfolio` | 15 min | NAV vs SPY, daily alpha, drawdown, current positions |
| Signals | `/Signals` | 15 min | Full signal table with sub-scores, date picker, ticker detail |
| Signal Quality | `/Signal_Quality` | 1 hr | Accuracy trends, score buckets, regime breakdown, weight history |
| Research | `/Research` | 1 hr | Per-ticker score history, conviction, thesis timeline, outcomes |
| Backtester | `/Backtester` | 1 hr | Param sweep heatmap, attribution, weight recommendation |
| Trade Log | `/Trade_Log` | 15 min | Full trade audit trail with filters and CSV export |

## Quick Start

### Prerequisites

- Python 3.11+
- AWS credentials with read access to `alpha-engine-research` and `alpha-engine-executor` S3 buckets (on EC2, the instance IAM role handles this automatically)
- Your EC2 `.pem` key file

### EC2 Setup

```bash
git clone https://github.com/cipher813/alpha-engine-dashboard.git
cd alpha-engine-dashboard
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running the Dashboard

```bash
source .venv/bin/activate
streamlit run app.py --server.port=8501
```

## Accessing the Dashboard via SSH Tunnel

Port 8501 is not exposed publicly. You need two things running at the same time:
1. Streamlit running on EC2
2. An SSH tunnel open on your local machine that forwards port 8501

---

### Step 1 — Start Streamlit on EC2

SSH into the server and start the dashboard in the background so it keeps running after you close the terminal:

```bash
# On EC2
cd ~/alpha-engine-dashboard
source .venv/bin/activate
nohup streamlit run app.py --server.port=8501 --server.headless=true > nohup.out 2>&1 &
```

You only need to do this once (or after a reboot). To confirm it's running:

```bash
# On EC2
pgrep -a streamlit
```

You can now close the EC2 terminal. Streamlit keeps running in the background.

---

### Step 2 — Open the tunnel from your local machine

Open a **new terminal on your Mac** (not on EC2) and run:

```bash
# On your Mac
ssh -i ~/.ssh/your-key.pem -L 8501:localhost:8501 -N ec2-user@3.236.87.228
```

Replace `your-key.pem` with your actual key file. The command will appear to hang with no output — that's correct. It's holding the tunnel open.

Then open **http://localhost:8501** in your browser.

Close the tunnel by pressing `Ctrl+C` in that terminal.

---

### Simplify with SSH config (recommended)

Add this to `~/.ssh/config` on your Mac (create the file if it doesn't exist):

```
Host alpha-engine
    HostName 3.236.87.228
    User ec2-user
    IdentityFile ~/.ssh/your-key.pem
```

After that, the tunnel command becomes:

```bash
# On your Mac
ssh -L 8501:localhost:8501 -N alpha-engine
```

And regular SSH login becomes just `ssh alpha-engine`.

---

### Summary: what runs where

| Terminal | Machine | Command |
|----------|---------|---------|
| EC2 (one-time setup) | EC2 | `nohup streamlit run app.py ...` |
| Tunnel (keep open while browsing) | Your Mac | `ssh -L 8501:localhost:8501 -N alpha-engine` |
| Browser | Your Mac | http://localhost:8501 |

## Keeping the Dashboard Running on EC2 (Permanent)

The `nohup` approach above works but stops if EC2 reboots. For a permanent setup use systemd:

### Option B: systemd service (recommended for persistence)

```bash
sudo cp infrastructure/dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable dashboard
sudo systemctl start dashboard
sudo systemctl status dashboard
```

Logs: `journalctl -u dashboard -f`

## Configuration

Edit `config.yaml` to change S3 bucket names, paths, or cache TTLs:

```yaml
s3:
  research_bucket: alpha-engine-research
  trades_bucket: alpha-engine-executor

cache_ttl:
  signals: 900      # 15 min
  trades: 900       # 15 min
  research: 3600    # 1 hour
  backtest: 3600    # 1 hour

drawdown_circuit_breaker: -0.08
```

## Data Sources

All data is **read-only**. The dashboard never writes to S3 or any database.

| Source | S3 Path | Cache |
|--------|---------|-------|
| Today's signals | `s3://alpha-engine-research/signals/{date}/signals.json` | 15 min |
| EOD P&L | `s3://alpha-engine-executor/trades/eod_pnl.csv` | 15 min |
| Full trade log | `s3://alpha-engine-executor/trades/trades_full.csv` | 15 min |
| Research database | `s3://alpha-engine-research/research.db` | 1 hr |
| Backtest output | `s3://alpha-engine-research/backtest/{date}/` | 1 hr |
| Scoring weights | `s3://alpha-engine-research/config/scoring_weights.json` | 1 hr |

## Project Structure

```
alpha-engine-dashboard/
├── app.py                    # Home page (entry point)
├── pages/
│   ├── 1_Portfolio.py
│   ├── 2_Signals.py
│   ├── 3_Signal_Quality.py
│   ├── 4_Research.py
│   ├── 5_Backtester.py
│   └── 6_Trade_Log.py
├── loaders/
│   ├── s3_loader.py          # S3 download helpers with caching
│   ├── db_loader.py          # SQLite read helpers (research.db)
│   └── signal_loader.py      # signals.json parsing
├── charts/
│   ├── nav_chart.py
│   ├── alpha_chart.py
│   ├── accuracy_chart.py
│   └── attribution_chart.py
├── config.yaml
├── requirements.txt
└── infrastructure/
    ├── dashboard.service     # systemd unit
    └── nginx.conf            # optional SSL reverse proxy
```

## See Also

- `alpha-engine-design-dashboard-260309.md` — full design document
- `docs/data-sources.md` — data schema reference
- `docs/pages.md` — per-page field and chart reference
