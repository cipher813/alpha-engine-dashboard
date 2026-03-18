"""
Utility helpers for the Alpha Engine Dashboard loaders and pages.
"""

import pandas as pd


def safe_column(df: pd.DataFrame, *candidates: str) -> str | None:
    """Return the first column name from *candidates* that exists in *df*, or None."""
    for col in candidates:
        if col in df.columns:
            return col
    return None
