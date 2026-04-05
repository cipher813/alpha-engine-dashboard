"""
System Health page — Is the infrastructure working?

Merges the former Data Inventory and Feature Store pages (Phase 5 of
dashboard-plan-optimized-260404) into two tabs:

  • Modules & Data — module freshness, data volume, feedback loop maturity,
                     pipeline manifests, missing data alerts
  • Feature Store  — feature snapshot freshness, coverage, catalog,
                     distributions, drift detection, recent snapshots
"""

import io
import os
import sys
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loaders.db_loader import load_research_db
from loaders.s3_loader import (
    _fetch_s3_json,
    _research_bucket,
    _s3_get_object,
    _trades_bucket,
    get_s3_client,
    list_s3_prefixes,
    load_eod_pnl,
    load_trades_full,
)

st.set_page_config(page_title="System Health — Alpha Engine", layout="wide")

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


@st.cache_data(ttl=900)
def _load_health(module: str) -> dict | None:
    return _fetch_s3_json(_research_bucket(), f"health/{module}.json")


@st.cache_data(ttl=900)
def _load_health_from_trades(module: str) -> dict | None:
    return _fetch_s3_json(_trades_bucket(), f"health/{module}.json")


@st.cache_data(ttl=900)
def _load_manifests(bucket: str, module: str, max_days: int = 90) -> list[dict]:
    """Load recent data manifests for a module."""
    client = get_s3_client()
    prefix = f"data_manifest/{module}/"
    manifests = []
    try:
        paginator = client.get_paginator("list_objects_v2")
        keys = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        for key in sorted(keys)[-max_days:]:
            data = _fetch_s3_json(bucket, key)
            if data:
                manifests.append(data)
    except Exception:
        pass
    return manifests


@st.cache_data(ttl=900)
def _count_s3_objects(bucket: str, prefix: str) -> int:
    client = get_s3_client()
    count = 0
    try:
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            count += page.get("KeyCount", 0)
    except Exception:
        pass
    return count


@st.cache_data(ttl=900)
def _table_counts() -> dict[str, int]:
    conn = load_research_db()
    if conn is None:
        return {}
    tables = [
        "investment_thesis",
        "score_performance",
        "predictor_outcomes",
        "scanner_appearances",
        "macro_snapshots",
        "candidate_tenures",
        "population_history",
        "stock_archive",
        "thesis_history",
        "universe_returns",
        "scanner_evaluations",
        "team_candidates",
        "cio_evaluations",
        "executor_shadow_book",
    ]
    counts = {}
    for t in tables:
        try:
            row = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()  # noqa: S608
            counts[t] = row[0] if row else 0
        except Exception:
            counts[t] = 0
    return counts


@st.cache_data(ttl=900)
def _load_parquet(bucket: str, key: str) -> pd.DataFrame | None:
    raw = _s3_get_object(bucket, key)
    if raw is None:
        return None
    try:
        return pd.read_parquet(io.BytesIO(raw))
    except Exception:
        return None


@st.cache_data(ttl=900)
def _find_latest_feature_date(bucket: str, max_lookback: int = 10) -> str | None:
    for offset in range(max_lookback):
        d = (date.today() - timedelta(days=offset)).isoformat()
        raw = _s3_get_object(bucket, f"features/{d}/technical.parquet")
        if raw is not None:
            return d
    return None


@st.cache_data(ttl=900)
def _load_drift_report(bucket: str, date_str: str) -> dict | None:
    return _fetch_s3_json(bucket, f"predictor/metrics/drift_{date_str}.json")


@st.cache_data(ttl=900)
def _load_registry(bucket: str) -> list[dict] | None:
    data = _fetch_s3_json(bucket, "features/registry.json")
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "features" in data:
        return data["features"]
    return data


@st.cache_data(ttl=900)
def _load_training_feature_stats(bucket: str) -> dict | None:
    return _fetch_s3_json(bucket, "predictor/metrics/training_feature_stats.json")


@st.cache_data(ttl=900)
def _get_s3_last_modified(bucket: str, key: str) -> str | None:
    try:
        client = get_s3_client()
        resp = client.head_object(Bucket=bucket, Key=key)
        return resp["LastModified"].strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return None


@st.cache_data(ttl=900)
def _load_predictions_meta(bucket: str) -> dict | None:
    return _fetch_s3_json(bucket, "predictor/predictions/latest.json")


# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.title("System Health")
st.caption("Is the plumbing working? Module freshness, data volume, feedback loops, and feature store.")

tab_modules, tab_features = st.tabs(["Modules & Data", "Feature Store"])


# ===========================================================================
# TAB 1: Modules & Data (from former Data Inventory)
# ===========================================================================
with tab_modules:
    # ─── Section 1: Module Health & Freshness ───────────────────────────────
    st.subheader("Module Health & Freshness")

    health_modules = [
        ("research", _research_bucket()),
        ("predictor_training", _research_bucket()),
        ("predictor_inference", _research_bucket()),
        ("executor", _research_bucket()),
        ("eod_reconcile", _trades_bucket()),
    ]

    now = datetime.utcnow()
    health_rows = []
    health_cache: dict[str, dict | None] = {}

    for module_name, bucket in health_modules:
        if bucket == _trades_bucket():
            health = _load_health_from_trades(module_name)
        else:
            health = _load_health(module_name)
        health_cache[module_name] = health

        if health is None:
            health_rows.append({
                "Module": module_name,
                "Status": "unknown",
                "Last Run": "—",
                "Age (hrs)": "—",
                "Duration (s)": "—",
            })
            continue

        last_success = health.get("last_success")
        age_str = "—"
        if last_success:
            try:
                last_dt = datetime.fromisoformat(last_success.replace("Z", "+00:00")).replace(tzinfo=None)
                age_hrs = (now - last_dt).total_seconds() / 3600
                age_str = f"{age_hrs:.1f}"
            except (ValueError, TypeError):
                pass

        health_rows.append({
            "Module": module_name,
            "Status": health.get("status", "unknown"),
            "Last Run": health.get("run_date", "—"),
            "Age (hrs)": age_str,
            "Duration (s)": health.get("duration_seconds", "—"),
        })

    health_df = pd.DataFrame(health_rows)

    def _status_color(val):
        if val == "ok":
            return "background-color: #d4edda"
        elif val == "failed":
            return "background-color: #f8d7da"
        elif val == "degraded":
            return "background-color: #fff3cd"
        return ""

    st.dataframe(
        health_df.style.map(_status_color, subset=["Status"]),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    # ─── Section 2: Data Volume Growth ──────────────────────────────────────
    st.subheader("Data Volume Growth")

    with st.spinner("Loading data counts..."):
        table_counts = _table_counts()
        trades_df = load_trades_full()
        eod_df = load_eod_pnl()
        n_signals_dates = len(list_s3_prefixes(_research_bucket(), "signals/"))
        n_predictions_dates = len(list_s3_prefixes(_research_bucket(), "predictor/predictions/"))
        n_daily_closes = _count_s3_objects(_research_bucket(), "predictor/daily_closes/")
        n_price_cache = _count_s3_objects(_research_bucket(), "predictor/price_cache_slim/")

    n_trades = len(trades_df) if trades_df is not None else 0
    n_eod = len(eod_df) if eod_df is not None else 0

    volume_data = {
        "Dataset": [
            "Signals (investment_thesis)",
            "Score Performance (10d/30d)",
            "Predictor Outcomes",
            "Trades (executed)",
            "EOD P&L (days)",
            "Macro Snapshots",
            "Scanner Appearances",
            "Candidate Tenures",
            "Population History",
            "Signal Dates (S3)",
            "Prediction Dates (S3)",
            "Daily Closes (S3)",
            "Price Cache Slim (tickers)",
            "Universe Returns (eval)",
            "Scanner Evaluations (eval)",
            "Team Candidates (eval)",
            "CIO Evaluations (eval)",
            "Executor Shadow Book (eval)",
        ],
        "Records": [
            table_counts.get("investment_thesis", "—"),
            table_counts.get("score_performance", "—"),
            table_counts.get("predictor_outcomes", "—"),
            n_trades,
            n_eod,
            table_counts.get("macro_snapshots", "—"),
            table_counts.get("scanner_appearances", "—"),
            table_counts.get("candidate_tenures", "—"),
            table_counts.get("population_history", "—"),
            n_signals_dates,
            n_predictions_dates,
            n_daily_closes,
            n_price_cache,
            table_counts.get("universe_returns", "—"),
            table_counts.get("scanner_evaluations", "—"),
            table_counts.get("team_candidates", "—"),
            table_counts.get("cio_evaluations", "—"),
            table_counts.get("executor_shadow_book", "—"),
        ],
    }

    st.dataframe(pd.DataFrame(volume_data), use_container_width=True, hide_index=True)

    if eod_df is not None and not eod_df.empty:
        eod_df.columns = [c.strip().lower().replace(" ", "_") for c in eod_df.columns]
        if "date" in eod_df.columns:
            eod_df["date"] = pd.to_datetime(eod_df["date"])
            eod_df = eod_df.sort_values("date")
            eod_df["trading_day_number"] = range(1, len(eod_df) + 1)
            fig = px.line(
                eod_df, x="date", y="trading_day_number",
                title="Cumulative Trading Days",
                labels={"trading_day_number": "Days", "date": "Date"},
            )
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

    if trades_df is not None and not trades_df.empty:
        trades_df.columns = [c.strip().lower().replace(" ", "_") for c in trades_df.columns]
        if "date" in trades_df.columns:
            trades_by_date = trades_df.groupby("date").size().reset_index(name="count")
            trades_by_date["date"] = pd.to_datetime(trades_by_date["date"])
            trades_by_date = trades_by_date.sort_values("date")
            trades_by_date["cumulative"] = trades_by_date["count"].cumsum()
            fig2 = px.line(
                trades_by_date, x="date", y="cumulative",
                title="Cumulative Trade Records",
                labels={"cumulative": "Trades", "date": "Date"},
            )
            fig2.update_layout(height=300)
            st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # ─── Section 3: Feedback Loop Maturity ──────────────────────────────────
    st.subheader("Feedback Loop Maturity")

    n_score_perf = table_counts.get("score_performance", 0)
    n_pred_outcomes = table_counts.get("predictor_outcomes", 0)

    conn = load_research_db()
    n_resolved_10d = 0
    n_resolved_30d = 0
    if conn:
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM score_performance WHERE return_10d IS NOT NULL"
            ).fetchone()
            n_resolved_10d = row[0] if row else 0
            row = conn.execute(
                "SELECT COUNT(*) FROM score_performance WHERE return_30d IS NOT NULL"
            ).fetchone()
            n_resolved_30d = row[0] if row else 0
        except Exception:
            pass

    n_roundtrips = 0
    if trades_df is not None and not trades_df.empty and "entry_trade_id" in trades_df.columns:
        n_roundtrips = int(trades_df["entry_trade_id"].notna().sum())

    n_ur_weeks = n_se_weeks = n_tc_weeks = n_cio_weeks = 0
    if conn:
        for tbl, attr in [
            ("universe_returns", "n_ur_weeks"),
            ("scanner_evaluations", "n_se_weeks"),
            ("team_candidates", "n_tc_weeks"),
            ("cio_evaluations", "n_cio_weeks"),
        ]:
            try:
                row = conn.execute(f"SELECT COUNT(DISTINCT eval_date) FROM {tbl}").fetchone()  # noqa: S608
                cnt = row[0] if row else 0
                if attr == "n_ur_weeks":
                    n_ur_weeks = cnt
                elif attr == "n_se_weeks":
                    n_se_weeks = cnt
                elif attr == "n_tc_weeks":
                    n_tc_weeks = cnt
                elif attr == "n_cio_weeks":
                    n_cio_weeks = cnt
            except Exception:
                pass

    maturity_data = [
        {
            "Optimizer": "Scoring weights",
            "Metric": "10d resolved signals",
            "Current": n_resolved_10d,
            "Threshold": 30,
            "Status": "Active" if n_resolved_10d >= 30 else "Blocked",
        },
        {
            "Optimizer": "Attribution analysis",
            "Metric": "10d resolved signals",
            "Current": n_resolved_10d,
            "Threshold": 50,
            "Status": "Active" if n_resolved_10d >= 50 else "Blocked",
        },
        {
            "Optimizer": "Predictor veto tuning",
            "Metric": "Resolved predictions",
            "Current": n_pred_outcomes,
            "Threshold": 20,
            "Status": "Active" if n_pred_outcomes >= 20 else "Blocked",
        },
        {
            "Optimizer": "Research param optimizer",
            "Metric": "Total signals",
            "Current": n_score_perf,
            "Threshold": 200,
            "Status": "Active" if n_score_perf >= 200 else "Deferred",
        },
        {
            "Optimizer": "Roundtrip linkage",
            "Metric": "Paired exit trades",
            "Current": n_roundtrips,
            "Threshold": "—",
            "Status": "Collecting" if n_roundtrips > 0 else "Pending deploy",
        },
        {
            "Optimizer": "4a Scanner auto-relax",
            "Metric": "Scanner eval weeks",
            "Current": n_se_weeks,
            "Threshold": 8,
            "Status": "Active" if n_se_weeks >= 8 else "Collecting",
        },
        {
            "Optimizer": "4b Team slot allocation",
            "Metric": "Team candidate weeks",
            "Current": n_tc_weeks,
            "Threshold": 8,
            "Status": "Active" if n_tc_weeks >= 8 else "Collecting",
        },
        {
            "Optimizer": "4c CIO fallback",
            "Metric": "CIO eval weeks",
            "Current": n_cio_weeks,
            "Threshold": 8,
            "Status": "Active" if n_cio_weeks >= 8 else "Collecting",
        },
        {
            "Optimizer": "4d Predictor p_up sizing",
            "Metric": "Resolved predictions",
            "Current": n_pred_outcomes,
            "Threshold": 30,
            "Status": "Active" if n_pred_outcomes >= 30 else "Collecting",
        },
        {
            "Optimizer": "4e Trigger optimizer",
            "Metric": "Total trades",
            "Current": n_trades,
            "Threshold": 200,
            "Status": "Active" if n_trades >= 200 else "Collecting",
        },
        {
            "Optimizer": "4f Sizing A/B test",
            "Metric": "Total trades",
            "Current": n_trades,
            "Threshold": 50,
            "Status": "Active" if n_trades >= 50 else "Collecting",
        },
    ]

    maturity_df = pd.DataFrame(maturity_data)
    st.dataframe(maturity_df, use_container_width=True, hide_index=True)

    for row in maturity_data:
        if isinstance(row["Threshold"], int) and row["Threshold"] > 0:
            pct = min(row["Current"] / row["Threshold"], 1.0)
            st.progress(pct, text=f"{row['Optimizer']}: {row['Current']}/{row['Threshold']}")

    st.divider()

    # ─── Section 4: Data Manifests ──────────────────────────────────────────
    st.subheader("Data Manifests")

    manifest_modules = [
        ("executor_morning", _research_bucket()),
        ("daemon", _research_bucket()),
        ("eod_reconcile", _trades_bucket()),
        ("research", _research_bucket()),
        ("predictor_training", _research_bucket()),
        ("predictor_inference", _research_bucket()),
    ]

    for module_name, bucket in manifest_modules:
        manifests = _load_manifests(bucket, module_name, max_days=30)
        if manifests:
            with st.expander(f"{module_name} — {len(manifests)} manifests"):
                latest = manifests[-1]
                st.json(latest)
        else:
            st.caption(f"{module_name} — no manifests yet (will appear after next run)")

    st.divider()

    # ─── Section 5: Missing Data Alerts ─────────────────────────────────────
    st.subheader("Missing Data Alerts")

    alerts = []

    if eod_df is not None and not eod_df.empty and "date" in eod_df.columns:
        eod_dates = set(pd.to_datetime(eod_df["date"]).dt.date)
        today = date.today()
        check_date = today
        missing_eod = []
        for _ in range(30):
            check_date -= timedelta(days=1)
            if check_date.weekday() < 5 and check_date not in eod_dates:
                missing_eod.append(str(check_date))
        if missing_eod:
            alerts.append(f"Missing EOD records for {len(missing_eod)} trading day(s): {', '.join(missing_eod[:5])}")

    for module_name, _ in health_modules:
        health = health_cache.get(module_name)
        if health and health.get("status") == "failed":
            alerts.append(f"Module **{module_name}** last status: FAILED — {health.get('error', 'unknown error')}")
        elif health is None:
            alerts.append(f"Module **{module_name}** has no health status (never run?)")

    if n_score_perf > 0 and n_resolved_10d < n_score_perf:
        n_pending = n_score_perf - n_resolved_10d
        alerts.append(f"{n_pending} score_performance rows awaiting 10d return resolution")

    if alerts:
        for alert in alerts:
            st.warning(alert)
    else:
        st.success("No data alerts. All systems nominal.")


# ===========================================================================
# TAB 2: Feature Store (from former Feature Store page)
# ===========================================================================
with tab_features:
    st.caption("Pre-computed feature snapshots for GBM inference — freshness, coverage, and drift monitoring.")

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

    # ─── Freshness ──────────────────────────────────────────────────────────
    st.subheader("Freshness")
    age_days = (date.today() - date.fromisoformat(latest_date)).days

    fc1, fc2, fc3, fc4 = st.columns(4)
    fc1.metric("Latest Snapshot", latest_date)
    fc2.metric(
        "Age", f"{age_days}d",
        delta=None if age_days <= 1 else f"{age_days}d old",
        delta_color="off" if age_days <= 1 else "inverse",
    )
    if schema:
        fc3.metric("Schema Version", schema.get("schema_version", "?"))
        fc4.metric("Schema Hash", (schema.get("schema_hash", "?")[:8] + "..."))
    else:
        n_feat = len([c for c in (tech_df.columns if tech_df is not None else []) if c not in ("ticker", "date")])
        fc3.metric("Features", n_feat)
        fc4.metric("Schema", "not versioned yet")

    if age_days > 2:
        st.warning(f"Feature store is {age_days} days old. Check that DailyData pipeline ran successfully.")
    elif age_days == 0:
        st.success("Feature store is up to date (today).")

    # ─── Coverage ───────────────────────────────────────────────────────────
    st.subheader("Coverage")

    _group_filenames = {
        "Technical": "technical.parquet",
        "Interaction": "interaction.parquet",
        "Macro": "macro.parquet",
        "Alternative": "alternative.parquet",
        "Fundamental": "fundamental.parquet",
    }
    groups = {
        "Technical": tech_df,
        "Interaction": interaction_df,
        "Macro": macro_df,
        "Alternative": alt_df,
        "Fundamental": fundamental_df,
    }

    coverage_data = []
    for name, df in groups.items():
        last_modified = _get_s3_last_modified(bucket, f"features/{latest_date}/{_group_filenames[name]}")
        if df is not None and not df.empty:
            n_tickers = df["ticker"].nunique() if "ticker" in df.columns else 1
            n_features = len([c for c in df.columns if c not in ("ticker", "date")])
            n_nulls = int(df.select_dtypes(include="number").isna().sum().sum())
            coverage_data.append({
                "Group": name,
                "Tickers": n_tickers,
                "Features": n_features,
                "Last Updated": last_modified or "?",
                "Null Values": n_nulls,
                "Status": "OK" if n_nulls == 0 else f"{n_nulls} nulls",
            })
        else:
            coverage_data.append({
                "Group": name,
                "Tickers": 0,
                "Features": 0,
                "Last Updated": last_modified or "MISSING",
                "Null Values": 0,
                "Status": "MISSING",
            })

    coverage_df = pd.DataFrame(coverage_data)
    st.dataframe(coverage_df, use_container_width=True, hide_index=True)

    total_tickers = tech_df["ticker"].nunique() if tech_df is not None and "ticker" in tech_df.columns else 0
    total_features = schema.get("n_features", "?") if schema else "?"
    st.caption(
        f"Total: {total_tickers} tickers, {total_features} features across "
        f"{len([g for g in groups.values() if g is not None])} groups"
    )

    # ─── Feature Catalog ────────────────────────────────────────────────────
    st.subheader("Feature Catalog")

    registry = _load_registry(bucket)
    _registry_lookup: dict[str, dict] = {}
    if registry:
        for entry in registry:
            name = entry.get("name", "")
            if name:
                _registry_lookup[name] = entry

    _meta_cols = {"ticker", "date"}
    catalog_rows = []
    for group_name, df in groups.items():
        if df is not None and not df.empty:
            for col in df.columns:
                if col in _meta_cols:
                    continue
                series = df[col]
                reg = _registry_lookup.get(col, {})
                catalog_rows.append({
                    "Group": group_name,
                    "Feature": col,
                    "Description": reg.get("description", ""),
                    "Source": reg.get("source", ""),
                    "Refresh": reg.get("refresh", ""),
                    "Mean": round(float(series.mean()), 4) if pd.api.types.is_numeric_dtype(series) else None,
                    "Std": round(float(series.std()), 4) if pd.api.types.is_numeric_dtype(series) else None,
                    "Nulls": int(series.isna().sum()),
                })

    if catalog_rows:
        catalog_df = pd.DataFrame(catalog_rows)
        st.caption(f"{len(catalog_rows)} features across {catalog_df['Group'].nunique()} groups")

        for group_name in ["Technical", "Interaction", "Macro", "Alternative", "Fundamental"]:
            group_slice = catalog_df[catalog_df["Group"] == group_name]
            if group_slice.empty:
                continue
            with st.expander(f"{group_name} ({len(group_slice)} features)", expanded=False):
                display_cols = ["Feature", "Description", "Source", "Refresh", "Mean", "Std", "Nulls"]
                st.dataframe(
                    group_slice[display_cols].reset_index(drop=True),
                    use_container_width=True,
                    hide_index=True,
                )

    # ─── Feature Distributions ──────────────────────────────────────────────
    st.subheader("Feature Distributions")

    if tech_df is not None and not tech_df.empty:
        numeric_cols = [c for c in tech_df.columns if c not in ("ticker", "date")]

        with st.expander("Summary Statistics (Technical Features)", expanded=False):
            stats = tech_df[numeric_cols].describe().T
            stats = stats[["mean", "std", "min", "25%", "50%", "75%", "max"]]
            st.dataframe(stats.round(4), use_container_width=True)

        selected = st.selectbox("Feature to visualize", numeric_cols, index=0)
        if selected:
            fig = px.histogram(
                tech_df, x=selected, nbins=50,
                title=f"Distribution of {selected} ({latest_date})",
                labels={selected: selected, "count": "Tickers"},
            )
            fig.update_layout(height=350, margin=dict(t=40, b=30))
            st.plotly_chart(fig, use_container_width=True)

        training_stats = _load_training_feature_stats(bucket)
        if training_stats and selected in training_stats.get("features", []):
            idx = training_stats["features"].index(selected)
            train_mean = training_stats["mean"][idx]
            train_std = training_stats["std"][idx]
            today_mean = float(tech_df[selected].mean())
            today_std = float(tech_df[selected].std())

            tc1, tc2, tc3, tc4 = st.columns(4)
            tc1.metric("Today Mean", f"{today_mean:.4f}")
            tc2.metric("Training Mean", f"{train_mean:.4f}")
            tc3.metric("Today Std", f"{today_std:.4f}")
            tc4.metric("Training Std", f"{train_std:.4f}")

            if train_std > 0:
                zscore = abs(today_mean - train_mean) / train_std
                if zscore > 3.0:
                    st.warning(f"Feature drift detected: z-score = {zscore:.2f} (>{3.0} threshold)")
                else:
                    st.caption(f"Z-score vs training: {zscore:.2f} (within normal range)")
    else:
        st.info("No technical features available for the latest snapshot.")

    # ─── Drift Detection ────────────────────────────────────────────────────
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

    # ─── Store vs Inline Usage ──────────────────────────────────────────────
    st.subheader("Store vs Inline Usage")
    st.caption(
        "Tracks whether GBM inference is reading from the feature store or falling back to inline computation. "
        "Goal: 100% from store, 0% inline."
    )

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

    # ─── Recent Snapshots ───────────────────────────────────────────────────
    st.subheader("Recent Snapshots")

    snapshot_dates = []
    for offset in range(14):
        d = (date.today() - timedelta(days=offset)).isoformat()
        raw = _s3_get_object(bucket, f"features/{d}/technical.parquet")
        if raw is not None:
            snapshot_dates.append(d)

    if snapshot_dates:
        st.dataframe(
            pd.DataFrame({
                "Date": snapshot_dates,
                "Age (days)": [(date.today() - date.fromisoformat(d)).days for d in snapshot_dates],
            }),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(f"{len(snapshot_dates)} snapshots found in the last 14 days")
    else:
        st.warning("No snapshots found in the last 14 days")
