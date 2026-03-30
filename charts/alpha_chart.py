"""
Daily alpha bar chart with cumulative alpha overlay for the Alpha Engine Dashboard.
"""

import pandas as pd
import plotly.graph_objects as go


def make_alpha_chart(eod_df: pd.DataFrame) -> go.Figure:
    """
    Daily alpha bar chart with cumulative alpha line overlay on secondary axis.

    eod_df needs: date, daily_alpha_pct
    Positive bars green, negative bars red.
    Cumulative alpha line plotted on secondary Y axis.
    """
    if eod_df is None or eod_df.empty:
        fig = go.Figure()
        fig.update_layout(title="Daily Alpha — No data available")
        return fig

    df = eod_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # Parse alpha values — detect decimal vs percent scale (max-based, not mean)
    alpha = pd.to_numeric(df["daily_alpha_pct"], errors="coerce").fillna(0.0)
    if len(alpha) > 0 and alpha.abs().max() > 1.0:
        alpha = alpha / 100.0

    alpha_pct = alpha * 100  # display as percent

    # Cumulative alpha
    cum_alpha = alpha_pct.cumsum()

    # Bar colors
    bar_colors = ["#2ca02c" if v >= 0 else "#d62728" for v in alpha_pct]

    # Hover text
    hover_bar = [
        f"<b>{d.strftime('%Y-%m-%d')}</b><br>Daily Alpha: {a:+.3f}%"
        for d, a in zip(df["date"], alpha_pct)
    ]
    hover_cum = [
        f"<b>{d.strftime('%Y-%m-%d')}</b><br>Cumulative Alpha: {ca:+.2f}%"
        for d, ca in zip(df["date"], cum_alpha)
    ]

    fig = go.Figure()

    # Daily alpha bars (primary y-axis)
    fig.add_trace(
        go.Bar(
            x=df["date"],
            y=alpha_pct,
            name="Daily Alpha",
            marker_color=bar_colors,
            hovertext=hover_bar,
            hoverinfo="text",
            yaxis="y1",
            opacity=0.85,
        )
    )

    # Cumulative alpha line (secondary y-axis)
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=cum_alpha,
            name="Cumulative Alpha",
            mode="lines",
            line=dict(color="#ff7f0e", width=2.5),
            hovertext=hover_cum,
            hoverinfo="text",
            yaxis="y2",
        )
    )

    # Zero reference line
    fig.add_hline(
        y=0,
        line=dict(color="rgba(0,0,0,0.3)", width=1, dash="dot"),
        yref="y1",
    )

    fig.update_layout(
        title="Daily Alpha vs Cumulative Alpha",
        xaxis=dict(title="Date", showgrid=True, gridcolor="rgba(0,0,0,0.07)"),
        yaxis=dict(
            title="Daily Alpha (%)",
            ticksuffix="%",
            showgrid=True,
            gridcolor="rgba(0,0,0,0.07)",
            zeroline=True,
            zerolinecolor="rgba(0,0,0,0.2)",
        ),
        yaxis2=dict(
            title="Cumulative Alpha (%)",
            ticksuffix="%",
            overlaying="y",
            side="right",
            showgrid=False,
            zeroline=False,
        ),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        barmode="overlay",
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(t=60, b=40, l=60, r=60),
    )

    return fig
