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

The EC2 security group does not expose port 8501 publicly. Access is via SSH tunnel from your local machine.

### One-time: add your key to SSH config

Add this to `~/.ssh/config` on your local machine (create the file if it doesn't exist):

```
Host alpha-engine
    HostName 3.236.87.228
    User ec2-user
    IdentityFile ~/.ssh/your-key.pem
    LocalForward 8501 localhost:8501
```

Replace `your-key.pem` with your actual key filename.

### Open the tunnel

```bash
ssh alpha-engine
```

Then open **http://localhost:8501** in your browser. The tunnel stays open as long as the SSH session is alive.

### Without SSH config (one-liner)

```bash
ssh -i ~/.ssh/your-key.pem -L 8501:localhost:8501 ec2-user@3.236.87.228
```

### Background tunnel (no interactive shell)

```bash
ssh -i ~/.ssh/your-key.pem -L 8501:localhost:8501 -N -f ec2-user@3.236.87.228
```

`-N` = no remote command, `-f` = go to background. Close it later with:

```bash
pkill -f "8501:localhost:8501"
```

## Keeping the Dashboard Running on EC2

### Option A: Keep alive in your SSH session (simplest)

```bash
source .venv/bin/activate
nohup streamlit run app.py --server.port=8501 --server.headless=true &
```

Logs go to `nohup.out`. Stop with `pkill -f streamlit`.

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
