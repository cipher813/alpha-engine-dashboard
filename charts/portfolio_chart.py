"""
Portfolio charts — sector allocation donut, sector rotation stacked area.
"""

import pandas as pd
import plotly.graph_objects as go


def make_sector_allocation_chart(positions_df: pd.DataFrame) -> go.Figure:
    """
    Donut chart of sector allocation by market_value.
    Colors sectors >20% amber, >25% red.
    """
    if positions_df is None or positions_df.empty or "sector" not in positions_df.columns:
        fig = go.Figure()
        fig.update_layout(title="Sector Allocation — No data")
        return fig

    df = positions_df.copy()
    if "market_value" not in df.columns:
        fig = go.Figure()
        fig.update_layout(title="Sector Allocation — No market_value column")
        return fig

    df["market_value"] = pd.to_numeric(df["market_value"], errors="coerce").fillna(0)
    sector_agg = df.groupby("sector").agg(
        total_value=("market_value", "sum"),
        count=("sector", "count"),
    ).reset_index()

    total = sector_agg["total_value"].sum()
    if total == 0:
        fig = go.Figure()
        fig.update_layout(title="Sector Allocation — Zero total value")
        return fig

    sector_agg["pct"] = sector_agg["total_value"] / total

    # Color by concentration: >25% red, >20% amber, else green-ish
    colors = []
    for pct in sector_agg["pct"]:
        if pct > 0.25:
            colors.append("#dc3545")  # red
        elif pct > 0.20:
            colors.append("#ffc107")  # amber
        else:
            colors.append("#28a745")  # green

    fig = go.Figure(
        go.Pie(
            labels=sector_agg["sector"],
            values=sector_agg["total_value"],
            hole=0.45,
            marker=dict(colors=colors),
            textinfo="label+percent",
            hovertemplate=(
                "<b>%{label}</b><br>"
                "Value: $%{value:,.0f}<br>"
                "Weight: %{percent}<br>"
                "<extra></extra>"
            ),
        )
    )

    fig.add_annotation(
        text="25% limit",
        x=0.5, y=-0.15,
        showarrow=False,
        font=dict(size=11, color="#856404"),
        xref="paper", yref="paper",
    )

    fig.update_layout(
        title="Sector Allocation",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
        margin=dict(t=40, b=80, l=20, r=20),
        height=400,
    )
    return fig


def make_sector_rotation_chart(snapshot_records: list[dict], time_range: str = "all") -> go.Figure:
    """
    Stacked area chart of sector allocation % over time.
    snapshot_records: list of {date, sector, market_value} dicts.
    """
    if not snapshot_records:
        fig = go.Figure()
        fig.update_layout(title="Sector Rotation — No data")
        return fig

    df = pd.DataFrame(snapshot_records)
    df["date"] = pd.to_datetime(df["date"])
    df["market_value"] = pd.to_numeric(df["market_value"], errors="coerce").fillna(0)

    # Filter by time range
    if time_range == "30d":
        cutoff = df["date"].max() - pd.Timedelta(days=30)
        df = df[df["date"] >= cutoff]
    elif time_range == "90d":
        cutoff = df["date"].max() - pd.Timedelta(days=90)
        df = df[df["date"] >= cutoff]

    # Aggregate by date + sector
    daily = df.groupby(["date", "sector"])["market_value"].sum().reset_index()
    daily_total = daily.groupby("date")["market_value"].sum().rename("total")
    daily = daily.merge(daily_total, on="date")
    # Drop dates with zero total to avoid division by zero (empty portfolio days)
    daily = daily[daily["total"] > 0].copy()
    daily["pct"] = daily["market_value"] / daily["total"] * 100

    # Pivot for stacked area
    pivot = daily.pivot_table(index="date", columns="sector", values="pct", fill_value=0)
    pivot = pivot.sort_index()

    fig = go.Figure()
    for sector in pivot.columns:
        fig.add_trace(
            go.Scatter(
                x=pivot.index,
                y=pivot[sector],
                mode="lines",
                name=sector,
                stackgroup="one",
                hovertemplate=f"<b>{sector}</b><br>%{{x|%Y-%m-%d}}<br>%{{y:.1f}}%<extra></extra>",
            )
        )

    # 25% limit reference line
    fig.add_hline(
        y=25,
        line=dict(color="red", width=1.5, dash="dash"),
        annotation_text="25% limit",
        annotation_position="top right",
        annotation_font_color="red",
    )

    fig.update_layout(
        title="Sector Allocation Over Time",
        xaxis=dict(title="Date", showgrid=True, gridcolor="rgba(0,0,0,0.07)"),
        yaxis=dict(title="Portfolio %", ticksuffix="%", range=[0, 100]),
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(t=40, b=40, l=60, r=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=400,
    )
    return fig
