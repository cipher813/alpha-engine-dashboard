"""
NAV vs SPY cumulative return chart for the Alpha Engine Dashboard.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go


def make_nav_chart(eod_df: pd.DataFrame) -> go.Figure:
    """
    NAV vs SPY cumulative return chart.

    eod_df needs columns:
        date, portfolio_nav, daily_return_pct, spy_return_pct, daily_alpha_pct

    Returns a Plotly Figure with:
    - Portfolio cumulative return line (blue)
    - SPY cumulative return line (gray)
    - Shaded region between them (green where portfolio > SPY, red otherwise)
    - Hover showing date, portfolio %, SPY %, alpha %
    """
    if eod_df is None or eod_df.empty:
        fig = go.Figure()
        fig.update_layout(title="NAV vs SPY — No data available")
        return fig

    df = eod_df.copy()

    # Ensure date column is datetime
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # Compute cumulative returns from daily_return_pct and spy_return_pct
    # Expects values as decimals (e.g., 0.01 = 1%) or percent (e.g., 1.0 = 1%)
    # Detect scale: if mean absolute value > 1, assume percent — convert to decimal
    def _to_decimal(series: pd.Series) -> pd.Series:
        s = pd.to_numeric(series, errors="coerce").fillna(0.0)
        if s.abs().mean() > 1.0:
            s = s / 100.0
        return s

    port_ret = _to_decimal(df["daily_return_pct"])
    spy_ret = _to_decimal(df["spy_return_pct"])
    alpha = _to_decimal(df["daily_alpha_pct"])

    port_cum = ((1 + port_ret).cumprod() - 1) * 100  # percent
    spy_cum = ((1 + spy_ret).cumprod() - 1) * 100     # percent
    alpha_cum = port_cum - spy_cum

    dates = df["date"]

    # ---------- Shaded region ----------
    # Build fill traces: green where portfolio > SPY, red where below
    # We create two filled traces by masking
    above_mask = port_cum >= spy_cum

    # Helper to build segment traces (fill between two lines)
    def _fill_segment(dates_seg, upper, lower, color, name):
        return go.Scatter(
            x=pd.concat([dates_seg, dates_seg[::-1]]),
            y=pd.concat([upper, lower[::-1]]),
            fill="toself",
            fillcolor=color,
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
            name=name,
        )

    traces = []

    # Identify contiguous segments
    segments = []
    current_above = above_mask.iloc[0]
    seg_start = 0
    for i in range(1, len(above_mask)):
        if above_mask.iloc[i] != current_above:
            segments.append((seg_start, i, current_above))
            seg_start = i
            current_above = above_mask.iloc[i]
    segments.append((seg_start, len(above_mask), current_above))

    for seg_start, seg_end, is_above in segments:
        idx = range(seg_start, seg_end)
        d_seg = dates.iloc[idx]
        p_seg = port_cum.iloc[idx]
        s_seg = spy_cum.iloc[idx]
        upper = p_seg if is_above else s_seg
        lower = s_seg if is_above else p_seg
        color = "rgba(0,200,100,0.15)" if is_above else "rgba(220,50,50,0.15)"
        name = "Outperformance" if is_above else "Underperformance"
        traces.append(_fill_segment(d_seg, upper, lower, color, name))

    # ---------- Main lines ----------
    hover_text = [
        f"<b>{d.strftime('%Y-%m-%d')}</b><br>"
        f"Portfolio: {p:+.2f}%<br>"
        f"SPY: {s:+.2f}%<br>"
        f"Alpha: {a:+.2f}%"
        for d, p, s, a in zip(dates, port_cum, spy_cum, alpha_cum)
    ]

    traces.append(
        go.Scatter(
            x=dates,
            y=port_cum,
            mode="lines",
            name="Portfolio",
            line=dict(color="#1f77b4", width=2.5),
            hovertext=hover_text,
            hoverinfo="text",
        )
    )

    traces.append(
        go.Scatter(
            x=dates,
            y=spy_cum,
            mode="lines",
            name="SPY",
            line=dict(color="#7f7f7f", width=2, dash="dash"),
            hovertext=hover_text,
            hoverinfo="text",
        )
    )

    # Zero reference line
    traces.append(
        go.Scatter(
            x=[dates.iloc[0], dates.iloc[-1]],
            y=[0, 0],
            mode="lines",
            line=dict(color="black", width=0.5, dash="dot"),
            showlegend=False,
            hoverinfo="skip",
        )
    )

    fig = go.Figure(data=traces)
    fig.update_layout(
        title="Portfolio vs SPY — Cumulative Return",
        xaxis=dict(title="Date", showgrid=True, gridcolor="rgba(0,0,0,0.07)"),
        yaxis=dict(
            title="Cumulative Return (%)",
            ticksuffix="%",
            showgrid=True,
            gridcolor="rgba(0,0,0,0.07)",
            zeroline=True,
            zerolinecolor="rgba(0,0,0,0.2)",
        ),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(t=60, b=40, l=60, r=20),
    )
    return fig
