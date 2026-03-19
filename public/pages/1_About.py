"""
Nous Ergon — About Page
Model overview, pipeline explanation, and links.
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
            <a href="https://github.com/cipher813/alpha-engine" target="_blank" style="color: #ccc; text-decoration: none; margin: 0 16px;">GitHub</a>
            <a href="https://dashboard.nousergon.ai" target="_blank" style="color: #ccc; text-decoration: none; margin: 0 16px;">Dashboard</a>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.divider()

# ---------------------------------------------------------------------------
# What is Nous Ergon?
# ---------------------------------------------------------------------------

st.markdown("### What is Nous Ergon?")

st.markdown(
    """
    Nous Ergon is a fully autonomous AI trading system. It researches stocks,
    predicts which ones will outperform the market, executes trades, and
    learns from its own results — all without human intervention.

    The system measures itself against one metric: **alpha**, the difference
    between its portfolio return and the S&P 500. A day where the portfolio
    drops 1% but the S&P drops 2% is a +1% alpha day. Everything in the
    system exists to sustain positive alpha over time.
    """
)

st.markdown("---")

# ---------------------------------------------------------------------------
# How It Works
# ---------------------------------------------------------------------------

st.markdown("### How It Works")

st.markdown(
    """
    The system is built around a simple idea: **use the right tool for each
    job**. LLMs are good at reading and reasoning over unstructured text.
    Machine learning models are good at finding patterns in numerical data.
    Deterministic rules are good at enforcing hard constraints. Nous Ergon
    combines all three.
    """
)

col1, col2 = st.columns(2)

with col1:
    st.markdown(
        """
        #### Research
        AI agents scan the S&P 500 and S&P 400 each week, filtering the full
        universe down to a manageable set of candidates. The top candidates
        get deep analysis — news sentiment, analyst research, and macro
        conditions — producing a composite attractiveness score for each stock.

        #### Prediction
        A machine learning model predicts short-term sector-relative returns
        using technical features computed from daily price data. It retrains
        weekly on years of history but refreshes predictions every morning
        with the latest market data. Research asks "is this a good stock?"
        while the predictor asks "is now the right time?"
        """
    )

with col2:
    st.markdown(
        """
        #### Execution
        Signals and predictions flow into a rule-based executor that sizes
        positions, manages risk, and places trades on Interactive Brokers.
        Risk guardrails enforce position limits, sector concentration caps,
        and graduated drawdown response. A veto gate blocks entry when the
        ML model predicts underperformance with high confidence.

        #### Learning
        A weekly backtester closes the feedback loop. It measures how
        accurate past signals were, identifies which scoring factors are
        most predictive, and auto-tunes parameters across the entire system.
        Updated configs are written back and picked up by all downstream
        modules — the system improves itself without manual intervention.
        """
    )

st.markdown("---")

# ---------------------------------------------------------------------------
# Architecture
# ---------------------------------------------------------------------------

st.markdown("### Architecture")

st.markdown(
    """
    The five modules communicate exclusively through S3 — there are no shared
    databases or direct API calls between them. Each module reads its inputs,
    does its work, and writes its outputs. This means any module can be
    replaced independently as long as it respects the shared data contracts.

    The system runs on two cadences: a **daily trading loop** (predictions
    and execution every market morning, reconciliation at close) and a
    **weekly optimization cycle** (research, model retraining, and
    backtesting on Mondays).
    """
)

st.markdown(
    """
    <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08);
                border-radius: 8px; padding: 20px; text-align: center; margin: 16px 0;">
        <p style="font-size: 15px; font-family: monospace; color: #aaa; margin: 0;">
            Research &rarr; Predictor &rarr; Executor &rarr; Backtester &rarr;
            <span style="color: #1a73e8;">(feedback loop)</span>
        </p>
    </div>
    """,
    unsafe_allow_html=True,
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
        - Claude (Haiku + Sonnet)
        - LightGBM
        - LangGraph
        """
    )

with col_b:
    st.markdown(
        """
        **Infrastructure**
        - AWS (Lambda, EC2, S3)
        - Interactive Brokers
        - Cloudflare
        """
    )

with col_c:
    st.markdown(
        """
        **Stack**
        - Python
        - Streamlit
        - SQLite
        """
    )

st.markdown("---")

# ---------------------------------------------------------------------------
# Learn More
# ---------------------------------------------------------------------------

st.markdown("### Learn More")

st.markdown(
    """
    For a deeper look at the design decisions, architecture, and lessons
    learned, check out the
    [blog series on Hashnode](https://nous-ergon.hashnode.dev).
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
