"""
NAV vs SPY cumulative return chart for the Nous Ergon public site.
Adapted from alpha-engine-dashboard/charts/nav_chart.py.
"""

import pandas as pd
import plotly.graph_objects as go


_DOWNTIME_FLOOR_PCT = 0.05  # skip trivial IB reconnect blips
_DOWNTIME_COLOR_RGB = "255, 165, 0"  # amber — distinct from red/green alpha shading


def _build_downtime_overlays(
    uptime_records: list[dict],
    dates: pd.Series,
    port_cum: pd.Series,
) -> tuple[list[dict], go.Scatter | None]:
    """Return (vrect shapes, hover-marker scatter trace) for days with meaningful downtime.

    Each vrect is a one-day amber band whose opacity scales with downtime fraction.
    The scatter trace places amber diamonds on the portfolio line for those days;
    unified hover merges their text into the per-date tooltip.
    """
    if not uptime_records or dates.empty:
        return [], None

    chart_start, chart_end = dates.min(), dates.max()
    port_cum_by_date = dict(zip(dates, port_cum))

    shapes: list[dict] = []
    hover_x, hover_y, hover_text = [], [], []

    for rec in uptime_records:
        date_str = rec.get("date")
        market_min = rec.get("market_minutes") or 0
        connected_min = rec.get("connected_minutes") or 0
        if not date_str or market_min <= 0:
            continue
        down_min = max(0, market_min - connected_min)
        down_pct = down_min / market_min
        if down_pct < _DOWNTIME_FLOOR_PCT:
            continue

        d = pd.Timestamp(date_str)
        if d < chart_start or d > chart_end:
            continue

        alpha = 0.10 + 0.45 * down_pct
        shapes.append(
            dict(
                type="rect",
                xref="x", yref="paper",
                x0=d - pd.Timedelta(hours=12),
                x1=d + pd.Timedelta(hours=12),
                y0=0, y1=1,
                fillcolor=f"rgba({_DOWNTIME_COLOR_RGB}, {alpha:.2f})",
                line=dict(width=0),
                layer="below",
            )
        )
        hover_x.append(d)
        hover_y.append(port_cum_by_date.get(d, 0))
        hover_text.append(
            f"<b>{d.strftime('%Y-%m-%d')}</b><br>"
            f"Executor downtime: {down_min} of {market_min} min "
            f"({down_pct * 100:.0f}%)"
        )

    if not hover_x:
        return shapes, None

    marker_trace = go.Scatter(
        x=hover_x,
        y=hover_y,
        mode="markers",
        marker=dict(
            size=8,
            color=f"rgba({_DOWNTIME_COLOR_RGB}, 0.9)",
            symbol="diamond-open",
            line=dict(width=1.5, color=f"rgba({_DOWNTIME_COLOR_RGB}, 1.0)"),
        ),
        name="Executor downtime",
        hovertext=hover_text,
        hoverinfo="text",
    )
    return shapes, marker_trace


def make_nav_chart(
    eod_df: pd.DataFrame,
    uptime_records: list[dict] | None = None,
) -> go.Figure:
    """
    Portfolio vs SPY cumulative return chart with shaded alpha regions.

    eod_df needs columns: date, daily_return_pct, spy_return_pct.
    uptime_records (optional) is the list returned by load_uptime_history;
    days with meaningful executor downtime get amber bands + hover markers.
    """
    if eod_df is None or eod_df.empty:
        fig = go.Figure()
        fig.update_layout(title="Portfolio vs SPY — No data available")
        return fig

    df = eod_df.copy()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # Use pre-computed cumulative returns from app.py if available
    if "port_cum" in df.columns and "spy_cum" in df.columns:
        port_cum = df["port_cum"] * 100  # convert decimal to percentage for display
        spy_cum = df["spy_cum"] * 100
    else:
        # Fallback: direct method from NAV and spy_close (avoids chaining errors)
        if "portfolio_nav" in df.columns and df["portfolio_nav"].notna().any():
            nav_0 = df["portfolio_nav"].iloc[0]
            port_cum = (df["portfolio_nav"] / nav_0 - 1) * 100
        else:
            port_ret = pd.to_numeric(df.get("daily_return_pct", 0), errors="coerce").fillna(0.0) / 100.0
            port_cum = ((1 + port_ret).cumprod() - 1) * 100

        spy_close = pd.to_numeric(df.get("spy_close"), errors="coerce")
        if spy_close.notna().sum() >= 2:
            spy_0 = spy_close.dropna().iloc[0]
            spy_cum = ((spy_close / spy_0 - 1).ffill().fillna(0.0)) * 100
        else:
            spy_ret = pd.to_numeric(df.get("spy_return_pct", 0), errors="coerce").fillna(0.0) / 100.0
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

    downtime_shapes, downtime_marker = _build_downtime_overlays(
        uptime_records or [], dates, port_cum
    )
    if downtime_marker is not None:
        traces.append(downtime_marker)

    fig = go.Figure(data=traces)
    if downtime_shapes:
        fig.update_layout(shapes=downtime_shapes)
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
    # daily_alpha is in decimal form (0.01 = 1% = 100 bps)
    alpha = pd.to_numeric(df["daily_alpha"], errors="coerce").dropna()
    alpha_bps = alpha * 10_000

    colors = ["#2e7d32" if v >= 0 else "#c62828" for v in alpha_bps]

    fig = go.Figure(
        go.Bar(
            x=list(range(len(alpha_bps))),
            y=alpha_bps,
            marker_color=colors,
            hovertemplate="%{y:+.0f} bps<extra></extra>",
        )
    )
    fig.update_layout(
        xaxis=dict(
            title="Trading Day", showgrid=False,
            tickfont=dict(color="#aaa"),
        ),
        yaxis=dict(
            title="Daily Alpha (bps)", ticksuffix=" bps",
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
