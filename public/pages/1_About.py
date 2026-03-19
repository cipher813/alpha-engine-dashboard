"""
Nous Ergon — About Page
Model overview, pipeline explanation, and blog links.
"""

import streamlit as st

st.set_page_config(
    page_title="About — Nous Ergon",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown(
    """
    <div style="text-align: center; padding: 20px 0 0 0;">
        <h1 style="margin-bottom: 0; font-size: 2.5em; letter-spacing: 2px;">
            NOUS ERGON
        </h1>
        <p style="color: #888; font-size: 14px; margin-top: 4px; font-style: italic;">
            &nu;&omicron;&upsilon;&sigmaf; &epsilon;&rho;&gamma;&omicron;&nu;
        </p>
        <p style="color: #aaa; font-size: 14px; margin-top: 6px;">
            Intelligence at work
        </p>
        <p style="color: #999; font-size: 13px; margin-top: 8px;">
            AI-driven autonomous trading system
        </p>
        <div style="margin-top: 14px; font-size: 13px; letter-spacing: 1px;">
            <a href="/" target="_self" style="color: #ccc; text-decoration: none; margin: 0 16px;">Home</a>
            <a href="https://nous-ergon.hashnode.dev" target="_blank" style="color: #ccc; text-decoration: none; margin: 0 16px;">Blog</a>
            <a href="https://dashboard.nousergon.ai" target="_blank" style="color: #ccc; text-decoration: none; margin: 0 16px;">Dashboard</a>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.divider()

# ---------------------------------------------------------------------------
# How It Works
# ---------------------------------------------------------------------------

st.markdown("### How It Works")

st.markdown(
    """
    Nous Ergon is an autonomous AI trading system that identifies stocks
    expected to outperform the S&P 500 over a 5-day rolling horizon.
    The system runs fully autonomously — no manual stock picks, no human
    intervention in trade execution.
    """
)

st.markdown("---")

col1, col2 = st.columns(2)

with col1:
    st.markdown(
        """
        #### 1. Research
        LLM agents (Claude) analyze ~900 stocks weekly, scoring each on
        news sentiment, analyst research, and sector macro conditions.
        ~20 stocks are tracked with rolling investment theses that update
        as new information arrives.

        #### 2. Prediction
        A gradient-boosted model (LightGBM) predicts 5-day sector-relative
        returns using 36 technical features computed from daily price data.
        Two models run in parallel — one calibrated for return magnitude,
        one optimized for relative ranking — and the best performer is
        promoted each week.
        """
    )

with col2:
    st.markdown(
        """
        #### 3. Execution
        Positions are sized based on conviction, sector rating, and price
        target upside. Risk rules enforce position limits, sector
        concentration caps, and graduated drawdown response. A veto gate
        blocks entry when the ML model predicts underperformance with
        high confidence.

        #### 4. Learning
        A weekly backtester measures signal quality, optimizes scoring
        weights, and auto-tunes risk parameters. Configs are written
        back to S3 and picked up by downstream modules on their next run.
        The system improves autonomously without manual intervention.
        """
    )

st.markdown("---")

# ---------------------------------------------------------------------------
# The Alpha Metric
# ---------------------------------------------------------------------------

st.markdown("### The Alpha Metric")

st.markdown(
    """
    <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08);
                border-radius: 8px; padding: 20px; text-align: center; margin: 16px 0;">
        <p style="font-size: 20px; font-family: monospace; color: #1a73e8; margin: 0;">
            &alpha; = Portfolio Return &minus; S&amp;P 500 Return
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    Every component in the system is evaluated against its contribution to
    sustained positive alpha. The goal is market-relative outperformance,
    not absolute returns. A day where the portfolio drops 1% but the S&P 500
    drops 2% is a +1% alpha day.
    """
)

st.markdown("---")

# ---------------------------------------------------------------------------
# Tech Stack
# ---------------------------------------------------------------------------

st.markdown("### Tech Stack")

col_a, col_b, col_c = st.columns(3)

with col_a:
    st.markdown(
        """
        **AI / ML**
        - Claude (Haiku + Sonnet) for research
        - LightGBM for predictions
        - LangGraph for agent orchestration
        """
    )

with col_b:
    st.markdown(
        """
        **Infrastructure**
        - AWS Lambda + EC2
        - S3 for data pipeline
        - Interactive Brokers (paper)
        """
    )

with col_c:
    st.markdown(
        """
        **Data**
        - 36 technical features
        - Sector-neutral labeling
        - Walk-forward validation
        """
    )

st.markdown("---")

# ---------------------------------------------------------------------------
# Blog
# ---------------------------------------------------------------------------

st.markdown("### Blog")

st.markdown(
    """
    *Coming soon — writing in progress.*

    - Building an AI Trading System from Scratch
    - How LLM Agents Research Stocks
    - The Case for Sector-Relative Predictions
    - What I Learned from My First Month of Autonomous Trading
    """
)

st.markdown("---")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.markdown(
    """
    <div style="text-align: center; padding: 8px 0 20px 0;">
        <p style="color: #666; font-size: 12px;">
            Paper trading account &mdash; not financial advice
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)
