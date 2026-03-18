"""
Predictor charts — model drift / rolling accuracy trend.
"""

import pandas as pd
import plotly.graph_objects as go


def make_model_drift_chart(outcomes_df: pd.DataFrame) -> go.Figure:
    """
    Rolling accuracy trend: 30-day (blue thin) and 90-day (orange thick).
    Horizontal bands: green >55%, red <48%, yellow between.
    Requires ≥60 resolved predictions.
    """
    if outcomes_df is None or outcomes_df.empty:
        fig = go.Figure()
        fig.update_layout(title="Model Performance Trend — No data")
        return fig

    df = outcomes_df.copy()
    df["prediction_date"] = pd.to_datetime(df["prediction_date"])
    df = df.sort_values("prediction_date")
    df["correct_5d"] = pd.to_numeric(df["correct_5d"], errors="coerce")

    resolved = df[df["correct_5d"].notna()].copy()
    if len(resolved) < 60:
        fig = go.Figure()
        fig.update_layout(title=f"Model Performance Trend — Need ≥60 resolved predictions ({len(resolved)} available)")
        return fig

    resolved["roll_30d"] = resolved["correct_5d"].rolling(30, min_periods=15).mean() * 100
    resolved["roll_90d"] = resolved["correct_5d"].rolling(90, min_periods=30).mean() * 100

    fig = go.Figure()

    # Background bands
    fig.add_hrect(y0=55, y1=100, fillcolor="rgba(0,200,100,0.08)", line_width=0)
    fig.add_hrect(y0=48, y1=55, fillcolor="rgba(255,193,7,0.08)", line_width=0)
    fig.add_hrect(y0=0, y1=48, fillcolor="rgba(220,53,69,0.06)", line_width=0)

    # 50% reference
    fig.add_hline(y=50, line=dict(color="gray", width=1, dash="dash"), annotation_text="50%", annotation_position="bottom right")

    # 30d rolling
    fig.add_trace(go.Scatter(
        x=resolved["prediction_date"], y=resolved["roll_30d"],
        mode="lines", name="30-day rolling",
        line=dict(color="#1f77b4", width=1.5),
        hovertemplate="<b>%{x|%Y-%m-%d}</b><br>30d: %{y:.1f}%<extra></extra>",
    ))

    # 90d rolling
    fig.add_trace(go.Scatter(
        x=resolved["prediction_date"], y=resolved["roll_90d"],
        mode="lines", name="90-day rolling",
        line=dict(color="#ff7f0e", width=2.5),
        hovertemplate="<b>%{x|%Y-%m-%d}</b><br>90d: %{y:.1f}%<extra></extra>",
    ))

    # Current 30d annotation
    current_30d = resolved["roll_30d"].dropna().iloc[-1] if not resolved["roll_30d"].dropna().empty else None
    if current_30d is not None:
        fig.add_annotation(
            x=resolved["prediction_date"].iloc[-1],
            y=current_30d,
            text=f"Current 30d: {current_30d:.1f}%",
            showarrow=True, arrowhead=2,
            font=dict(size=11, color="#1f77b4"),
        )

    fig.update_layout(
        title="Model Performance Trend (Rolling Hit Rate)",
        xaxis=dict(title="Date", showgrid=True, gridcolor="rgba(0,0,0,0.07)"),
        yaxis=dict(title="Hit Rate (%)", ticksuffix="%", range=[30, 80], showgrid=True, gridcolor="rgba(0,0,0,0.07)"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(t=60, b=40, l=60, r=20),
        height=350,
    )
    return fig
