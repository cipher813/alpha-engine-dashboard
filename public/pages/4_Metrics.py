"""
Nous Ergon — Metrics Validation

Auditability layer for every headline number on the home page. Each entry
lists what the metric measures, where it comes from, how it is computed,
and what caveats apply. Deep-link via ``?metric=<id>`` from the home page's
``↓ verify`` anchors.

Per Decision 11 of the presentation revamp plan: the page sources from
existing system outputs only — never computes ad-hoc analytics. If a
metric you want to show isn't already produced upstream, ship it upstream
first.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from components.header import render_footer, render_header
from components.styles import inject_base_css, inject_docs_css
from loaders.s3_loader import (
    load_eod_pnl,
    load_latest_grading,
    load_predictor_metrics,
    load_trades_full,
    load_uptime_history,
)

st.set_page_config(
    page_title="Metrics — Nous Ergon",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_base_css()
inject_docs_css()
render_header(current_page="Metrics")

st.divider()

# ---------------------------------------------------------------------------
# Page intro
# ---------------------------------------------------------------------------

st.markdown("### Metrics Validation")
st.markdown(
    """
    Every headline number on the [home page](/) is auditable here. Each entry
    records what the metric measures, the upstream source it reads, the
    calculation that produces it, the refresh cadence, and methodology
    caveats. Phase 2 is the reliability + measurement chapter — this page is
    the receipts trail.
    """
)
st.caption(
    "Source-of-truth discipline: every metric reads from an existing system "
    "output. The presentation layer is a view, not a measurement layer."
)

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

eod = load_eod_pnl()
trades_df = load_trades_full()
uptime_history = load_uptime_history(max_sessions=20)
grading = load_latest_grading()
predictor_metrics = load_predictor_metrics()


# ---------------------------------------------------------------------------
# Derived current values (mirror app.py calculations exactly)
# ---------------------------------------------------------------------------

def _safe_pct(x: float) -> str:
    return f"{x:.1f}%" if pd.notna(x) else "—"


def _eod_derived() -> dict:
    if eod is None or eod.empty:
        return {}
    e = eod.copy()
    e["date"] = pd.to_datetime(e["date"])
    e = e.sort_values("date").reset_index(drop=True)
    e["daily_alpha"] = pd.to_numeric(e.get("daily_alpha_pct"), errors="coerce").fillna(0.0) / 100.0
    nav_0 = e["portfolio_nav"].iloc[0]
    e["port_cum"] = e["portfolio_nav"] / nav_0 - 1
    spy_close = pd.to_numeric(e.get("spy_close"), errors="coerce")
    if spy_close.notna().sum() >= 2:
        spy_0 = spy_close.dropna().iloc[0]
        e["spy_cum"] = (spy_close / spy_0 - 1).ffill().fillna(0.0)
    else:
        e["spy_cum"] = 0.0
    cum_alpha_bps = (e["port_cum"].iloc[-1] - e["spy_cum"].iloc[-1]) * 10_000
    active = e.iloc[1:] if len(e) > 1 else e
    up_days = int((active["daily_alpha"] > 0).sum())
    down_days = int((active["daily_alpha"] < 0).sum())
    total_days = len(active)
    win_rate = (up_days / total_days * 100) if total_days else 0.0
    avg_up = active.loc[active["daily_alpha"] > 0, "daily_alpha"].mean() * 10_000 if up_days else 0
    avg_down = active.loc[active["daily_alpha"] < 0, "daily_alpha"].mean() * 10_000 if down_days else 0
    return {
        "nav": float(e["portfolio_nav"].iloc[-1]),
        "cum_alpha_bps": float(cum_alpha_bps),
        "up_days": up_days,
        "down_days": down_days,
        "total_days": total_days,
        "win_rate": float(win_rate),
        "avg_up_bps": float(avg_up) if pd.notna(avg_up) else 0.0,
        "avg_down_bps": float(avg_down) if pd.notna(avg_down) else 0.0,
        "inception": e["date"].iloc[0],
        "as_of": e["date"].iloc[-1],
    }


def _uptime_derived() -> dict:
    if not uptime_history:
        return {}
    connected = sum(r.get("connected_minutes", 0) for r in uptime_history)
    market = sum(r.get("market_minutes", 0) for r in uptime_history)
    pct = (connected / market * 100.0) if market else 0.0
    last_date = max((r.get("date", "") for r in uptime_history), default="")
    return {
        "uptime_pct": pct,
        "connected_minutes": connected,
        "market_minutes": market,
        "sessions": len(uptime_history),
        "last_date": last_date,
    }


def _trade_count() -> int | None:
    if trades_df is None or trades_df.empty:
        return None
    return int(len(trades_df))


def _predictor_ic() -> dict:
    if not predictor_metrics or not isinstance(predictor_metrics, dict):
        return {}
    out: dict = {}
    for k in ("ensemble_ic", "meta_ic", "val_ic", "oos_ic"):
        if k in predictor_metrics:
            out[k] = predictor_metrics[k]
    components = predictor_metrics.get("components") or predictor_metrics.get("layer1") or {}
    if isinstance(components, dict):
        out["components"] = components
    out["_run_ts"] = predictor_metrics.get("run_ts") or predictor_metrics.get("trained_at")
    return out


eod_derived = _eod_derived()
uptime_derived = _uptime_derived()
trade_count = _trade_count()
predictor_ic = _predictor_ic()


# ---------------------------------------------------------------------------
# Entry rendering
# ---------------------------------------------------------------------------


@dataclass
class MetricEntry:
    metric_id: str
    name: str
    current: str
    measures: str
    source: str
    calculation: str
    refresh: str
    last_refresh: str
    methodology: str
    phase_context: str


def _render_entry(e: MetricEntry) -> None:
    # Anchor for ?metric=<id> deep linking; HTML id is honored by browsers.
    st.markdown(f'<a id="{e.metric_id}"></a>', unsafe_allow_html=True)
    st.markdown(f"#### {e.name}")
    st.markdown(
        f'<div style="font-size:22px; color:#1a73e8; font-weight:600; margin-bottom:10px;">'
        f"{e.current}</div>",
        unsafe_allow_html=True,
    )
    cols = st.columns(2)
    with cols[0]:
        st.markdown(f"**What this measures.** {e.measures}")
        st.markdown(f"**Source.** {e.source}")
        st.markdown(f"**Calculation.** {e.calculation}")
    with cols[1]:
        st.markdown(f"**Refresh cadence.** {e.refresh}")
        st.markdown(f"**Last refresh.** {e.last_refresh}")
        st.markdown(f"**Methodology notes.** {e.methodology}")
    st.markdown(
        f'<div style="color:#888; font-style:italic; margin-top:6px;">'
        f"Phase context: {e.phase_context}</div>",
        unsafe_allow_html=True,
    )
    st.markdown("---")


# ---------------------------------------------------------------------------
# Section 1 — Reliability metrics (Phase 2 primary)
# ---------------------------------------------------------------------------

st.markdown("## Reliability metrics")
st.caption("Phase 2 primary KPIs. Answers: *is the system actually running?*")

# --- Uptime % ---------------------------------------------------------------
_render_entry(MetricEntry(
    metric_id="uptime",
    name="Daemon uptime (rolling 20 sessions)",
    current=(
        f"{uptime_derived.get('uptime_pct', 0):.1f}% "
        f"({uptime_derived.get('connected_minutes', 0):,} / "
        f"{uptime_derived.get('market_minutes', 0):,} min)"
        if uptime_derived else "data not yet available"
    ),
    measures=(
        "Fraction of NYSE market minutes the trading daemon was connected "
        "to IB Gateway and processing the order book. Captures executor "
        "availability, IB Gateway connectivity, and instance health in one "
        "number."
    ),
    source=(
        "`s3://alpha-engine-research/uptime/{date}.json` "
        "(producer: `alpha-engine/executor/uptime_tracker.py`); read via "
        "`loaders/s3_loader.py:load_uptime_history()`. "
        "Surfaced by `components/uptime_kpi.py`."
    ),
    calculation=(
        "`sum(connected_minutes) / sum(market_minutes)` over the trailing "
        "20 market sessions. Each session record has both numerators (per "
        "`uptime_tracker.py`)."
    ),
    refresh="Once per trading day after EOD reconcile (~1:20 PM PT).",
    last_refresh=uptime_derived.get("last_date") or "—",
    methodology=(
        "Market window is 9:30–16:00 ET on NYSE trading days. Non-trading "
        "days emit `{date, skipped}` sentinel records that are dropped. "
        "Phase 2 target is 99% — incidents that take down the daemon "
        "mid-session show up here as the bar moves."
    ),
    phase_context="Phase 2 reliability metric — current chapter's primary KPI.",
))

# --- System Report Card -----------------------------------------------------
_grade_overall = (grading or {}).get("overall", {}) if grading else {}
_grade_letter = _grade_overall.get("letter") if _grade_overall else None
_grade_numeric = _grade_overall.get("grade") if _grade_overall else None
_render_entry(MetricEntry(
    metric_id="report-card",
    name="System Report Card (overall + module letter grades)",
    current=(
        f"{_grade_letter} ({_grade_numeric:.0f}/100)"
        if _grade_letter and _grade_numeric is not None
        else "no grading published yet"
    ),
    measures=(
        "Structural quality grade for each module (research / predictor / "
        "executor) plus an overall composite. Complements uptime: uptime "
        "asks *is it running?*, the report card asks *is it running well?*"
    ),
    source=(
        "`s3://alpha-engine-research/backtest/{date}/grading.json` "
        "(producer: `alpha-engine-backtester/evaluate.py` weekly Saturday "
        "Step Function); read via `loaders/s3_loader.py:load_latest_grading()`. "
        "Surfaced by `components/report_card.py`."
    ),
    calculation=(
        "Weekly evaluator scores each module on 0–100 and assigns a letter. "
        "Sub-components (e.g. CIO, GBM, VWAP, EOD reconcile) get their own "
        "letter; most show N/A while the Phase-2 sample is too thin to be "
        "meaningful (typically requires 4–8 weeks of signals)."
    ),
    refresh="Weekly, after the Saturday SF backtester run (~Sat 09:00 UTC).",
    last_refresh=(grading or {}).get("_run_date") or "—",
    methodology=(
        "Backing numerical stats (Sharpe, rank IC, alpha, hit rate) stay on "
        "the private dashboard during Phase 2 because the sample is too "
        "small to be interpreted by outside observers without context. "
        "Letter grades are surfaced here; raw stats are not."
    ),
    phase_context="Phase 2 reliability/quality metric.",
))

# ---------------------------------------------------------------------------
# Section 2 — Quality metrics (Phase 2 → Phase 3 bridge)
# ---------------------------------------------------------------------------

st.markdown("## Quality metrics")
st.caption(
    "Bridge between Phase 2 reliability and Phase 3 alpha tuning. "
    "Answers: *are the system's predictions any good?*"
)

# --- Predictor ensemble IC --------------------------------------------------
_ic_current = (
    f"L2 IC: {predictor_ic.get('val_ic') or predictor_ic.get('meta_ic') or predictor_ic.get('ensemble_ic') or '—'}"
    if predictor_ic
    else "predictor metrics file not yet available"
)
_render_entry(MetricEntry(
    metric_id="predictor-ic",
    name="Predictor ensemble IC (L2 meta-learner + per-L1 components)",
    current=_ic_current,
    measures=(
        "Information Coefficient — Spearman rank correlation between "
        "predicted 5-day market-relative alpha and realized alpha. "
        "Reported at the Layer-2 Ridge meta-learner and at each Layer-1 "
        "specialized component (LightGBM momentum, LightGBM volatility, "
        "research-score calibrator). Quality, not return."
    ),
    source=(
        "`s3://alpha-engine-research/predictor/metrics/latest.json` "
        "(producer: `alpha-engine-predictor/training/meta_trainer.py`); "
        "read via `loaders/s3_loader.py:load_predictor_metrics()`."
    ),
    calculation=(
        "Walk-forward validation IC across cross-section: predicted_alpha "
        "vs realized 5d sector-neutral alpha (`stock_5d_return − "
        "sector_etf_5d_return`). Each L1 component must clear a named "
        "baseline + isolated promotion gate before contributing to L2."
    ),
    refresh="Weekly, on Saturday SF predictor training (`PredictorTraining` state).",
    last_refresh=str(predictor_ic.get("_run_ts") or "—"),
    methodology=(
        "Sector-neutral labels (vs sector ETF return) plus cross-sectional "
        "rank normalization. Promotion gate: ensemble IC must improve and "
        "every L1 component must clear its baseline subsample gate. The "
        "2026-04-28 collapse fix wired real research features into L2 "
        "training; val_ic moved 0.053 → 0.132."
    ),
    phase_context="Phase 2 → Phase 3 bridge metric — substrate for alpha tuning.",
))

# ---------------------------------------------------------------------------
# Section 3 — Return metrics (Phase 3 horizon)
# ---------------------------------------------------------------------------

st.markdown("## Return metrics")
st.caption(
    "Phase 3 horizon. Shown honestly as a Phase 2 baseline; alpha is "
    "tracked but not optimized until uptime reaches 99%."
)

_eod_source = (
    "`s3://alpha-engine-research/trades/eod_pnl.csv` "
    "(producer: `alpha-engine/executor/eod_reconcile.py`); read via "
    "`loaders/s3_loader.py:load_eod_pnl()`."
)
_eod_refresh = "Once per trading day after EOD reconcile (~1:20 PM PT)."
_eod_last = eod_derived.get("as_of").strftime("%Y-%m-%d") if eod_derived else "—"

# --- Cumulative alpha -------------------------------------------------------
_render_entry(MetricEntry(
    metric_id="cumulative-alpha",
    name="Cumulative alpha vs SPY",
    current=(
        f"{eod_derived.get('cum_alpha_bps', 0):+.0f} bps "
        f"(since {eod_derived.get('inception').strftime('%Y-%m-%d')})"
        if eod_derived else "—"
    ),
    measures=(
        "Difference between portfolio cumulative return and SPY cumulative "
        "return since inception. Positive = outperforming the benchmark; "
        "negative = underperforming. Phase 2 sample is too short for the "
        "headline; this becomes the primary KPI in Phase 3."
    ),
    source=_eod_source,
    calculation=(
        "Portfolio cumulative: `portfolio_nav / portfolio_nav_at_inception − 1`. "
        "SPY cumulative: `spy_close / spy_close_at_inception − 1` (direct "
        "from NAV and spy_close columns; no daily chaining). Alpha = "
        "(portfolio_cum − spy_cum) × 10,000 bps."
    ),
    refresh=_eod_refresh,
    last_refresh=_eod_last,
    methodology=(
        "Inception date is configurable via `config.yaml:inception_date` "
        "to step past windows of fragmented data (see "
        "`project_inception_date_strategy.md`). Vertical amber lines on "
        "the home-page chart mark days with executor incidents (≥10% "
        "downtime or ≥5 service restarts)."
    ),
    phase_context="Phase 3 horizon metric — current value is a Phase 2 baseline.",
))

# --- Portfolio NAV ----------------------------------------------------------
_render_entry(MetricEntry(
    metric_id="nav",
    name="Portfolio NAV",
    current=f"${eod_derived.get('nav', 0):,.0f}" if eod_derived else "—",
    measures=(
        "Net asset value of the paper-trading account at the most recent "
        "EOD reconcile. Sum of marked-to-market positions plus cash."
    ),
    source=_eod_source,
    calculation=(
        "Read directly from the `portfolio_nav` column of the latest row "
        "in `eod_pnl.csv`. Computed by `eod_reconcile.py` from the "
        "Interactive Brokers paper account at session close."
    ),
    refresh=_eod_refresh,
    last_refresh=_eod_last,
    methodology=(
        "Paper-trading account; NAV starts at $1,000,000 nominal. Position "
        "marks come from IB end-of-day prices. Cash residual reconciliation "
        "fixed 2026-04-17 (PR #59) — prior values may show drift."
    ),
    phase_context="Phase 3 horizon metric — operational receipt of the paper account.",
))

# --- Win rate ---------------------------------------------------------------
_render_entry(MetricEntry(
    metric_id="win-rate",
    name="Alpha win rate",
    current=(
        f"{eod_derived.get('win_rate', 0):.1f}% "
        f"({eod_derived.get('up_days', 0)}▲ / {eod_derived.get('total_days', 0)} days)"
        if eod_derived else "—"
    ),
    measures=(
        "Fraction of trading days since inception where daily portfolio "
        "return exceeded SPY return. A directional signal-quality metric "
        "even when cumulative alpha is negative."
    ),
    source=_eod_source,
    calculation=(
        "`(daily_alpha_pct > 0).sum() / len(active_days)`. Active days "
        "exclude the inception baseline row."
    ),
    refresh=_eod_refresh,
    last_refresh=_eod_last,
    methodology=(
        "`daily_alpha_pct` is computed as `daily_return_pct − spy_return_pct` "
        "in `eod_reconcile.py`. Days with NaN alpha are treated as 0 (not "
        "wins, not losses)."
    ),
    phase_context="Phase 2 → Phase 3 bridge — measurement is working even when totals are red.",
))

# --- Avg up/down alpha day --------------------------------------------------
_render_entry(MetricEntry(
    metric_id="avg-alpha-day",
    name="Average up-alpha and down-alpha day",
    current=(
        f"+{eod_derived.get('avg_up_bps', 0):.0f} bps  /  "
        f"{eod_derived.get('avg_down_bps', 0):.0f} bps"
        if eod_derived else "—"
    ),
    measures=(
        "Average daily alpha on days where the portfolio beat SPY (up) "
        "vs days where it lagged (down). The shape of the alpha "
        "distribution — symmetric vs skewed, fat-tailed vs normal — "
        "matters more than the cumulative number while the sample is small."
    ),
    source=_eod_source,
    calculation=(
        "Mean of `daily_alpha_pct × 10,000` over rows where `daily_alpha_pct` "
        "is positive (up) and negative (down) respectively."
    ),
    refresh=_eod_refresh,
    last_refresh=_eod_last,
    methodology=(
        "Inception baseline row is excluded. NaN rows treated as 0 (drop "
        "from numerator and denominator). The home-page alpha histogram "
        "visualizes the full distribution behind these two summary numbers."
    ),
    phase_context="Phase 2 → Phase 3 bridge.",
))

# --- Trading days -----------------------------------------------------------
_render_entry(MetricEntry(
    metric_id="trading-days",
    name="Trading days since inception",
    current=str(eod_derived.get("total_days", 0)) if eod_derived else "—",
    measures=(
        "Count of EOD reconcile rows since the configured inception date. "
        "A measurement-completeness check: every market day should produce "
        "exactly one row."
    ),
    source=_eod_source,
    calculation=(
        "Row count of `eod_pnl.csv` filtered to `date >= inception_date`, "
        "minus the inception baseline row."
    ),
    refresh=_eod_refresh,
    last_refresh=_eod_last,
    methodology=(
        "Holidays and non-trading weekdays produce no row. Gaps between "
        "calendar days and trading days here mean a real EOD reconcile "
        "miss — investigate the SF execution history if the count looks "
        "off vs the trading calendar."
    ),
    phase_context="Phase 2 measurement-completeness metric.",
))

# --- Total trades -----------------------------------------------------------
_render_entry(MetricEntry(
    metric_id="total-trades",
    name="Total trades executed",
    current=str(trade_count) if trade_count is not None else "—",
    measures=(
        "Count of rows in `trades_full.csv` — one per fill (entry, exit, "
        "cover, etc.). Baseline volume metric for downstream attribution."
    ),
    source=(
        "`s3://alpha-engine-research/trades/trades_full.csv` "
        "(producer: `alpha-engine/executor/trade_logger.py`); read via "
        "`loaders/s3_loader.py:load_trades_full()`."
    ),
    calculation=(
        "`len(trades_df)` — every fill writes a row. Backed by SQLite "
        "(`trades.db`) on the trading instance; CSV is the S3 mirror."
    ),
    refresh=(
        "Continuously during the trading day; mirror to S3 happens in the "
        "EOD reconcile step. Recent Trades panel on the home page reads "
        "the last 5 trading days from this same file."
    ),
    last_refresh=_eod_last,
    methodology=(
        "Filtered universe: paper account fills only. Includes daemon "
        "intraday actions (entry triggers, exits, urgent flatten) plus "
        "morning-planner-generated orders. The 2026-04-22 PFE short-sell "
        "incident retro covers a defensive layer added to this path."
    ),
    phase_context="Phase 2 measurement-completeness metric.",
))

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.divider()
st.caption(
    "Missing a metric? V1 of this page lists only metrics already produced "
    "by an existing module's output pipeline. New metrics ship upstream "
    "first (per Decision 11 of the presentation revamp plan), then surface "
    "here."
)

render_footer()
