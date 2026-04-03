"""
Feature Store page — visibility into pre-computed feature snapshots.

Shows freshness, coverage, feature distributions, store-vs-inline usage,
and drift detection alerts.
"""

import io
import os
import sys
from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loaders.s3_loader import (
    _fetch_s3_json,
    _research_bucket,
    _s3_get_object,
    get_s3_client,
)


st.set_page_config(page_title="Feature Store — Alpha Engine", layout="wide")

st.title("Feature Store")
st.caption("Pre-computed feature snapshots for GBM inference — freshness, coverage, and drift monitoring.")


# ─── Helpers ─────────────────────────────────────────────────────────────────


@st.cache_data(ttl=900)
def _load_parquet(bucket: str, key: str) -> pd.DataFrame | None:
    """Load a parquet file from S3."""
    raw = _s3_get_object(bucket, key)
    if raw is None:
        return None
    try:
        return pd.read_parquet(io.BytesIO(raw))
    except Exception:
        return None


@st.cache_data(ttl=900)
def _find_latest_feature_date(bucket: str, max_lookback: int = 10) -> str | None:
    """Find the most recent feature snapshot date."""
    for offset in range(max_lookback):
        d = (date.today() - timedelta(days=offset)).isoformat()
        raw = _s3_get_object(bucket, f"features/{d}/schema_version.json")
        if raw is not None:
            return d
    return None


@st.cache_data(ttl=900)
def _load_drift_report(bucket: str, date_str: str) -> dict | None:
    return _fetch_s3_json(bucket, f"predictor/metrics/drift_{date_str}.json")


@st.cache_data(ttl=900)
def _load_training_feature_stats(bucket: str) -> dict | None:
    return _fetch_s3_json(bucket, "predictor/metrics/training_feature_stats.json")


@st.cache_data(ttl=900)
def _load_predictions_meta(bucket: str) -> dict | None:
    return _fetch_s3_json(bucket, "predictor/predictions/latest.json")


# ─── Data Loading ────────────────────────────────────────────────────────────

bucket = _research_bucket()

with st.spinner("Finding latest feature snapshot..."):
    latest_date = _find_latest_feature_date(bucket)

if latest_date is None:
    st.error("No feature store snapshots found in the last 10 days.")
    st.stop()

schema = _fetch_s3_json(bucket, f"features/{latest_date}/schema_version.json")
tech_df = _load_parquet(bucket, f"features/{latest_date}/technical.parquet")
interaction_df = _load_parquet(bucket, f"features/{latest_date}/interaction.parquet")
macro_df = _load_parquet(bucket, f"features/{latest_date}/macro.parquet")
alt_df = _load_parquet(bucket, f"features/{latest_date}/alternative.parquet")
fundamental_df = _load_parquet(bucket, f"features/{latest_date}/fundamental.parquet")

# ─── Section 1: Freshness ────────────────────────────────────────────────────

st.subheader("Freshness")

age_days = (date.today() - date.fromisoformat(latest_date)).days

col1, col2, col3, col4 = st.columns(4)
col1.metric("Latest Snapshot", latest_date)
col2.metric("Age", f"{age_days}d", delta=None if age_days <= 1 else f"{age_days}d old",
            delta_color="off" if age_days <= 1 else "inverse")
col3.metric("Schema Version", schema.get("schema_version", "?") if schema else "?")
col4.metric("Schema Hash", (schema.get("schema_hash", "?")[:8] + "...") if schema else "?")

if age_days > 2:
    st.warning(f"Feature store is {age_days} days old. Check that DailyData pipeline ran successfully.")
elif age_days == 0:
    st.success("Feature store is up to date (today).")

# ─── Section 2: Coverage ─────────────────────────────────────────────────────

st.subheader("Coverage")

groups = {
    "Technical": tech_df,
    "Interaction": interaction_df,
    "Macro": macro_df,
    "Alternative": alt_df,
    "Fundamental": fundamental_df,
}

coverage_data = []
for name, df in groups.items():
    if df is not None and not df.empty:
        n_tickers = df["ticker"].nunique() if "ticker" in df.columns else 1
        n_features = len([c for c in df.columns if c not in ("ticker", "date")])
        n_nulls = int(df.select_dtypes(include="number").isna().sum().sum())
        coverage_data.append({
            "Group": name,
            "Tickers": n_tickers,
            "Features": n_features,
            "Null Values": n_nulls,
            "Status": "OK" if n_nulls == 0 else f"{n_nulls} nulls",
        })
    else:
        coverage_data.append({
            "Group": name,
            "Tickers": 0,
            "Features": 0,
            "Null Values": 0,
            "Status": "MISSING",
        })

coverage_df = pd.DataFrame(coverage_data)
st.dataframe(coverage_df, use_container_width=True, hide_index=True)

total_tickers = tech_df["ticker"].nunique() if tech_df is not None and "ticker" in tech_df.columns else 0
total_features = schema.get("n_features", "?") if schema else "?"
st.caption(f"Total: {total_tickers} tickers, {total_features} features across {len([g for g in groups.values() if g is not None])} groups")

# ─── Section 3: Feature Distributions ────────────────────────────────────────

st.subheader("Feature Distributions")

if tech_df is not None and not tech_df.empty:
    numeric_cols = [c for c in tech_df.columns if c not in ("ticker", "date")]

    # Summary stats table
    with st.expander("Summary Statistics (Technical Features)", expanded=False):
        stats = tech_df[numeric_cols].describe().T
        stats = stats[["mean", "std", "min", "25%", "50%", "75%", "max"]]
        st.dataframe(stats.round(4), use_container_width=True)

    # Distribution chart for selected feature
    selected = st.selectbox("Feature to visualize", numeric_cols, index=0)
    if selected:
        fig = px.histogram(
            tech_df, x=selected, nbins=50,
            title=f"Distribution of {selected} ({latest_date})",
            labels={selected: selected, "count": "Tickers"},
        )
        fig.update_layout(height=350, margin=dict(t=40, b=30))
        st.plotly_chart(fig, use_container_width=True)

    # Training baseline comparison
    training_stats = _load_training_feature_stats(bucket)
    if training_stats and selected in training_stats.get("features", []):
        idx = training_stats["features"].index(selected)
        train_mean = training_stats["mean"][idx]
        train_std = training_stats["std"][idx]
        today_mean = float(tech_df[selected].mean())
        today_std = float(tech_df[selected].std())

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Today Mean", f"{today_mean:.4f}")
        c2.metric("Training Mean", f"{train_mean:.4f}")
        c3.metric("Today Std", f"{today_std:.4f}")
        c4.metric("Training Std", f"{train_std:.4f}")

        if train_std > 0:
            zscore = abs(today_mean - train_mean) / train_std
            if zscore > 3.0:
                st.warning(f"Feature drift detected: z-score = {zscore:.2f} (>{3.0} threshold)")
            else:
                st.caption(f"Z-score vs training: {zscore:.2f} (within normal range)")
else:
    st.info("No technical features available for the latest snapshot.")

# ─── Section 4: Drift Detection ──────────────────────────────────────────────

st.subheader("Drift Detection")

drift = _load_drift_report(bucket, latest_date)
if drift:
    if drift.get("status") == "ok":
        st.success(f"No drift detected ({latest_date})")
    else:
        st.error(f"Drift alerts ({drift.get('n_alerts', 0)}):")
        for alert in drift.get("alerts", []):
            st.warning(alert)
else:
    st.info("No drift report available. Drift detection runs after inference — check back after the next daily pipeline.")

# ─── Section 5: Store vs Inline Usage ────────────────────────────────────────

st.subheader("Store vs Inline Usage")
st.caption(
    "Tracks whether GBM inference is reading from the feature store or falling back to inline computation. "
    "Goal: 100% from store, 0% inline."
)

# Check predictions metadata for any store/inline info
preds = _load_predictions_meta(bucket)
if preds:
    pred_date = preds.get("date", "?")
    n_preds = preds.get("n_predictions", 0)
    st.metric("Latest Predictions", f"{n_preds} tickers on {pred_date}")
    st.info(
        "Store vs inline metrics are logged in the predictor inference logs. "
        "Look for: `GBM features: N from store, M from inline, K skipped` in CloudWatch."
    )
else:
    st.info("No predictions metadata available.")

# ─── Section 6: Historical Snapshots ─────────────────────────────────────────

st.subheader("Recent Snapshots")

snapshot_dates = []
for offset in range(14):
    d = (date.today() - timedelta(days=offset)).isoformat()
    raw = _s3_get_object(bucket, f"features/{d}/schema_version.json")
    if raw is not None:
        snapshot_dates.append(d)

if snapshot_dates:
    st.dataframe(
        pd.DataFrame({"Date": snapshot_dates, "Age (days)": [(date.today() - date.fromisoformat(d)).days for d in snapshot_dates]}),
        use_container_width=True,
        hide_index=True,
    )
    st.caption(f"{len(snapshot_dates)} snapshots found in the last 14 days")
else:
    st.warning("No snapshots found in the last 14 days")
