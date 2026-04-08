## Executor Module

The Executor translates AI-generated signals and ML predictions into real portfolio
positions. It reads from S3, applies risk rules, sizes positions, and manages the
full trade lifecycle through Interactive Brokers.

*GitHub: [alpha-engine](https://github.com/cipher813/alpha-engine) · Last updated: 2026-04-08*

---

### Overview

The Executor is split into two programs: a **morning planner** that builds the
order book, and an **intraday daemon** that executes orders using technical triggers.
The planner places no orders — it only decides *what* to trade. The daemon decides
*when* to trade, using pullback, VWAP, and support-level triggers to optimize
entry prices.

**Alpha contribution:** Risk guardrails prevent over-concentration and shut down
new entries during drawdowns, preserving capital for recovery. Intraday entry
triggers optimize execution price versus simple market-open fills.

---

### Key Concepts

- **Order book:** JSON file separating entries, urgent exits, and stop-loss orders.
  The planner writes it; the daemon reads and executes it
- **Risk guard:** Enforces minimum score gates, conviction requirements, max position
  sizes, sector concentration limits, and graduated drawdown response
- **Graduated drawdown:** Tiered sizing reduction as portfolio drawdown increases.
  At configurable thresholds, position sizes shrink; at the halt threshold,
  new entries stop entirely
- **Entry triggers:** Four technical conditions — pullback (price dip from signal),
  VWAP discount, support bounce, and time expiry (3:30 PM ET market order)
- **Veto integration:** Predictor DOWN + high confidence → position held, not entered

---

### How It Works

**Morning (6:20 AM PT):**
```
Read signals.json + predictions.json from S3
  → Apply risk guard (min score, conviction, drawdown tier)
  → Filter vetoed tickers (Predictor DOWN signals)
  → Size positions (equal-weight adjusted by sector/conviction/upside)
  → Identify urgent exits (SELL ratings, stale positions)
  → Write order book (entries + exits + stops)
```

**Intraday (6:25 AM PT - 4:00 PM ET):**
```
Daemon starts → execute urgent exits immediately at market open
  → Monitor entry triggers every 60 seconds
  → Place limit orders when triggers fire (pullback, VWAP discount, support)
  → Manage trailing stops and profit-take levels
  → 2:00-3:30 PM: graduated expiry (accept if price <= open+1%)
  → 3:55 PM ET: unconditional time-expiry market orders for unfilled entries
```

**EOD (1:20 PM PT, Step Function orchestrated):**
```
Reconcile positions with IB
  → Capture NAV, compute daily return vs SPY
  → Sector attribution, roundtrip statistics
  → Log alpha to SQLite + S3
  → Send EOD performance email
  → Step Function stops EC2 trading instance
```

---

### Position Sizing

Base position size is equal-weight: `available_capital / n_entries`. This base
is then adjusted by three multipliers:

1. **Sector rating** — macro-favored sectors get a size boost
2. **Conviction** — rising conviction stocks get more capital
3. **Price target upside** — higher upside = larger position
4. **Drawdown tier** — sizes shrink as portfolio drawdown increases

---

### Quick Start

```bash
git clone https://github.com/cipher813/alpha-engine.git
cd alpha-engine
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Copy and configure
cp config/risk.yaml.example config/risk.yaml

# Dry run (simulated broker, no real orders)
python executor/main.py --simulate --dry-run
```

**Required environment variables:** `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`

**For live trading:** IB Gateway must be running on the same host (port 4002,
paper account only).

---

### Key Files

| File | Purpose |
|------|---------|
| `executor/main.py` | Morning order book planner |
| `executor/daemon.py` | Intraday order executor |
| `executor/order_book.py` | JSON order book (entries, exits, stops) |
| `executor/entry_triggers.py` | Pullback/VWAP/support/expiry triggers |
| `executor/risk_guard.py` | Rule enforcement + graduated drawdown |
| `executor/position_sizer.py` | Position sizing with adjustments |
| `executor/ibkr.py` | IB Gateway wrapper |
| `executor/eod_reconcile.py` | Daily P&L and alpha logging |
