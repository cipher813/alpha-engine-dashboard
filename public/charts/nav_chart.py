"""
NAV vs SPY cumulative return chart for the Nous Ergon public site.
Adapted from alpha-engine-dashboard/charts/nav_chart.py.
"""

import pandas as pd
import plotly.graph_objects as go


def make_nav_chart(eod_df: pd.DataFrame) -> go.Figure:
    """
    Portfolio vs SPY cumulative return chart with shaded alpha regions.

    eod_df needs columns: date, daily_return_pct, spy_return_pct
    """
    if eod_df is None or eod_df.empty:
        fig = go.Figure()
        fig.update_layout(title="Portfolio vs SPY — No data available")
        return fig

    df = eod_df.copy()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # Returns are already converted to decimals by app.py (port_ret, spy_ret)
    # If raw columns are present, convert; otherwise use pre-computed
    if "port_ret" in df.columns:
        port_ret = df["port_ret"]
        spy_ret = df["spy_ret"]
    else:
        port_ret = pd.to_numeric(df["daily_return_pct"], errors="coerce").fillna(0.0) / 100.0
        spy_ret = pd.to_numeric(df["spy_return_pct"], errors="coerce").fillna(0.0) / 100.0

    port_cum = ((1 + port_ret).cumprod() - 1) * 100
    spy_cum = ((1 + spy_ret).cumprod() - 1) * 100
    alpha_cum = port_cum - spy_cum

    dates = df["date"]

    # Shaded regions
    above_mask = port_cum >= spy_cum
    traces = []

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
        traces.append(
            go.Scatter(
                x=pd.concat([d_seg, d_seg[::-1]]),
                y=pd.concat([upper, lower[::-1]]),
                fill="toself",
                fillcolor=color,
                line=dict(width=0),
                showlegend=False,
                hoverinfo="skip",
            )
        )

    # Main lines
    hover_text = [
        f"<b>{d.strftime('%Y-%m-%d')}</b><br>"
        f"Portfolio: {p:+.2f}%<br>"
        f"SPY: {s:+.2f}%<br>"
        f"Alpha: {a:+.2f}%"
        for d, p, s, a in zip(dates, port_cum, spy_cum, alpha_cum)
    ]

    traces.append(
        go.Scatter(
            x=dates, y=port_cum, mode="lines",
            name="Portfolio",
            line=dict(color="#1a73e8", width=2.5),
            hovertext=hover_text, hoverinfo="text",
        )
    )
    traces.append(
        go.Scatter(
            x=dates, y=spy_cum, mode="lines",
            name="S&P 500",
            line=dict(color="#7f7f7f", width=2, dash="dash"),
            hovertext=hover_text, hoverinfo="text",
        )
    )

    # Zero line
    traces.append(
        go.Scatter(
            x=[dates.iloc[0], dates.iloc[-1]], y=[0, 0],
            mode="lines",
            line=dict(color="rgba(255,255,255,0.3)", width=0.5, dash="dot"),
            showlegend=False, hoverinfo="skip",
        )
    )

    fig = go.Figure(data=traces)
    fig.update_layout(
        xaxis=dict(
            title="", showgrid=True,
            gridcolor="rgba(255,255,255,0.06)",
            tickfont=dict(color="#aaa"),
        ),
        yaxis=dict(
            title="Cumulative Return (%)",
            ticksuffix="%", showgrid=True,
            gridcolor="rgba(255,255,255,0.06)",
            zeroline=True, zerolinecolor="rgba(255,255,255,0.15)",
            tickfont=dict(color="#aaa"),
            title_font=dict(color="#aaa"),
        ),
        hovermode="x unified",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="right", x=1, font=dict(color="#ccc"),
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=20, b=40, l=60, r=20),
    )
    return fig


def make_alpha_histogram(eod_df: pd.DataFrame) -> go.Figure:
    """Daily alpha distribution histogram."""
    if eod_df is None or eod_df.empty:
        fig = go.Figure()
        fig.update_layout(title="No data")
        return fig

    df = eod_df.copy()
    # daily_alpha is in decimal form (0.01 = 1%) — convert to percent for display
    alpha = pd.to_numeric(df["daily_alpha"], errors="coerce").dropna()
    alpha_pct = alpha * 100

    colors = ["#2e7d32" if v >= 0 else "#c62828" for v in alpha_pct]

    fig = go.Figure(
        go.Bar(
            x=list(range(len(alpha_pct))),
            y=alpha_pct,
            marker_color=colors,
            hovertemplate="%{y:+.2f}%<extra></extra>",
        )
    )
    fig.update_layout(
        xaxis=dict(
            title="Trading Day", showgrid=False,
            tickfont=dict(color="#aaa"),
        ),
        yaxis=dict(
            title="Daily Alpha (%)", ticksuffix="%",
            showgrid=True, gridcolor="rgba(255,255,255,0.06)",
            zeroline=True, zerolinecolor="rgba(255,255,255,0.15)",
            tickfont=dict(color="#aaa"), title_font=dict(color="#aaa"),
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=20, b=40, l=60, r=20),
        showlegend=False,
    )
    return fig
