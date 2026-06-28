"""Pure transforms for the Universe Board page (no Streamlit) — so the
cross-repo consumer contract with crucible-research ``scoring/universe_board.py``
(``scanner/universe/latest.json``, ``schema_version=1``) is unit-testable
independently of the Streamlit chrome in ``views/39_Universe_Board.py``.
"""
from __future__ import annotations

import pandas as pd

PILLARS = ["quality", "value", "momentum", "growth", "stewardship", "defensiveness"]

# Display labels for the metric columns (used by the page's filters + table).
METRIC_LABELS = {
    "pe": "P/E", "pb": "P/B", "div_yield": "Dividend yield", "fcf_yield": "FCF yield",
    "debt_to_equity": "Debt/Equity", "current_ratio": "Current ratio", "payout": "Payout ratio",
    "roe": "ROE", "gross_margin": "Gross margin", "rev_gr_3y": "Revenue growth 3y",
    "eps_gr_3y": "EPS growth 3y", "mkt_cap": "Market cap", "rsi": "RSI(14)",
    "mom_20d": "Momentum 20d", "ret_60d": "Return 60d", "ret_120d": "Return 120d",
    "vol_20d": "Realized vol 20d", "atr_pct": "ATR %", "beta": "Beta",
    "dist_52w_hi": "Dist from 52w high", "vs_ma200": "Price vs MA200", "avg_vol": "Avg volume",
    "tech": "Tech score", "focus": "Focus score",
}

# Columns that stay textual (never coerced to numeric).
_TEXT_COLS = ("ticker", "sector", "country", "industry", "stance", "gate", "fail_reason")

# metric-block key in the artifact → display column in the DataFrame.
_METRIC_MAP = {
    "current_price": "price", "market_cap": "mkt_cap", "pe": "pe", "pb": "pb",
    "fcf_yield": "fcf_yield", "dividend_yield": "div_yield", "debt_to_equity": "debt_to_equity",
    "current_ratio": "current_ratio", "payout_ratio": "payout", "roe": "roe",
    "gross_margin": "gross_margin", "revenue_growth_3y": "rev_gr_3y", "eps_growth_3y": "eps_gr_3y",
    "rsi_14": "rsi", "momentum_20d": "mom_20d", "return_60d": "ret_60d", "return_120d": "ret_120d",
    "realized_vol_20d": "vol_20d", "atr_pct": "atr_pct", "dist_from_52w_high": "dist_52w_hi",
    "price_vs_ma200": "vs_ma200", "beta": "beta", "avg_volume": "avg_vol",
}


def flatten_stock(stock: dict) -> dict:
    """One universe-board stock record → a flat display row. Missing fields
    degrade to None (a coverage gap, never a guessed value)."""
    pillars = stock.get("pillars", {}) or {}
    metrics = stock.get("metrics", {}) or {}
    gate = stock.get("gate", {}) or {}
    row = {
        "ticker": stock.get("ticker"),
        "sector": stock.get("sector") or "Unknown",
        "country": stock.get("country") or "Unknown",
        "industry": stock.get("industry"),
        "attractiveness": stock.get("attractiveness_score"),
    }
    for p in PILLARS:
        row[p] = pillars.get(p)
    row["focus"] = stock.get("focus_score")
    row["stance"] = stock.get("focus_stance")
    row["tech"] = stock.get("tech_score")
    row["gate"] = "PASS" if int(gate.get("quant_filter_pass", 0) or 0) == 1 else "FAIL"
    row["fail_reason"] = gate.get("filter_fail_reason")
    for src, dst in _METRIC_MAP.items():
        row[dst] = metrics.get(src)
    return row


def flatten_board(board: dict) -> pd.DataFrame:
    """The board artifact → a numeric-coerced display DataFrame. Empty board →
    empty frame (the page graceful-degrades to its explainer)."""
    stocks = (board or {}).get("stocks") or []
    df = pd.DataFrame([flatten_stock(s) for s in stocks])
    if df.empty:
        return df
    for col in df.columns:
        if col not in _TEXT_COLS:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df
