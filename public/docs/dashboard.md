## Dashboard Module

The Dashboard provides read-only monitoring for the full system. It surfaces
the system report card, portfolio performance, signal quality trends, execution
evaluation, research theses, backtester results, and GBM predictions through
a Streamlit web interface.

*GitHub: [alpha-engine-dashboard](https://github.com/cipher813/alpha-engine-dashboard) · Last updated: 2026-04-08*

---

### Overview

The Dashboard runs two Streamlit apps on a single EC2 instance: a **public portfolio
page** at [nousergon.ai](https://nousergon.ai) and a **private operational dashboard**
at dashboard.nousergon.ai (protected by Cloudflare Access).

---

### Key Concepts

- **Read-only:** The dashboard never writes data — it only reads from S3 and
  renders visualizations. All state lives in the upstream modules
- **TTL caching:** `@st.cache_data` with configurable TTLs (15 min for signals/trades,
  1 hour for research/backtest) reduces S3 API calls
- **Dual-app architecture:** Public and private dashboards run as separate Streamlit
  processes on different ports, fronted by nginx
- **Zero-trust auth:** Cloudflare Access protects the private dashboard with
  Google OAuth — no application-level authentication needed

---

### Dashboard Pages

| Page | What It Shows |
|------|---------------|
| **Home** | Pipeline status, today's activity, key KPIs, **system report card** (module grades), market context |
| **Portfolio** | NAV vs SPY chart, drawdown, positions, sector allocation with HHI concentration |
| **Signals & Research** | Full signal table with date picker, sector ratings, and ticker drilldown surfacing score history, conviction, thesis timeline |
| **Analysis** | Signal accuracy trends, backtester runs with **component grade table** and **sector team grades** (precision, recall, lift), pipeline evaluation |
| **Execution** | Trade log, **execution evaluation** (trigger scorecard, shadow book with P/R/F1, exit timing MFE/MAE), slippage monitor |
| **Predictor** | GBM predictions, hit rate, IC, calibration, disagreements |

---

### How It Works

```
S3 (research bucket)     →  signals, research.db, backtest output
S3 (executor bucket)     →  trades, EOD P&L
     ↓
Streamlit loaders        →  boto3 downloads + TTL caching
     ↓
Plotly chart builders    →  Interactive visualizations
     ↓
Streamlit pages          →  Rendered in browser
```

Data flows one way: S3 → loaders → charts → pages. There are no background
workers or database connections — every data load happens during page render
with Streamlit's caching layer preventing redundant S3 calls.

---

### Quick Start

```bash
git clone https://github.com/cipher813/alpha-engine-dashboard.git
cd alpha-engine-dashboard
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Copy and configure
cp config.yaml.example config.yaml

# Run private dashboard locally
streamlit run app.py

# Run public site locally
cd public && streamlit run app.py
```

**Required environment variables:** `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
(or EC2 IAM role for production)

---

### Key Files

| File | Purpose |
|------|---------|
| `app.py` | Home page (system health) |
| `pages/1_Portfolio.py` - `pages/7_Predictor.py` | Dashboard pages |
| `loaders/s3_loader.py` | S3 downloads with TTL caching |
| `loaders/signal_loader.py` | signals.json parsing |
| `charts/` | Plotly chart builders |
| `public/app.py` | Public portfolio page |
| `public/pages/` | Public site pages |
