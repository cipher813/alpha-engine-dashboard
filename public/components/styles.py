"""Shared CSS styles for the Nous Ergon public site."""

import streamlit as st


def inject_base_css():
    """Inject base CSS shared across all public pages."""
    st.markdown(
        """
        <style>
        /* Hide Streamlit default header and footer for cleaner public look */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}

        /* Match page background to logo */
        .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
            background-color: #000000 !important;
        }

        /* Subtle link styling */
        a { color: #1a73e8; }
        a:hover { color: #4a9af5; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_metric_css():
    """Inject metric card CSS (home page only)."""
    st.markdown(
        """
        <style>
        [data-testid="stMetric"] {
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 8px;
            padding: 12px 16px;
        }
        [data-testid="stMetricLabel"] {
            font-size: 12px;
            color: #888;
        }
        [data-testid="stMetricValue"] {
            font-size: 24px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_docs_css():
    """Inject documentation-specific CSS."""
    st.markdown(
        """
        <style>
        .stMarkdown h2 {
            margin-top: 1.5em;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            padding-bottom: 8px;
        }
        .stMarkdown code {
            background: rgba(255,255,255,0.06);
            padding: 2px 6px;
            border-radius: 4px;
        }
        .stMarkdown pre {
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
