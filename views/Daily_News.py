"""Daily News — Alpha Engine (private console)

Human-readable reverse-chronological feed of the weekday news pull for the
held + tracked universe. Producer: ``alpha-engine-data`` ``daily_news`` step
→ ``s3://alpha-engine-research/data/news_articles_daily/{run_id}_articles.parquet``
(raw per-article companion to the per-(ticker, date) sentiment aggregate).

Older days are reachable via the date picker (one entry per run date). The
feed is deterministic — sourced from Polygon / GDELT / Yahoo RSS with
dictionary-based Loughran-McDonald sentiment + rule-based event flags. No
LLM is involved in producing this data.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import streamlit as st

from loaders.s3_loader import list_news_article_runs, load_news_articles

_MAX_FEED_ROWS = 300


def _badge(sentiment: float) -> str:
    if sentiment > 0.05:
        return "🟢 positive"
    if sentiment < -0.05:
        return "🔴 negative"
    return "⚪ neutral"


def _json_list(val) -> list:
    if isinstance(val, (list, tuple)):
        return list(val)
    if not val:
        return []
    try:
        out = json.loads(val)
        return out if isinstance(out, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


st.title("📰 Daily News")
st.caption(
    "Weekday news for the held + tracked universe — deterministic pull "
    "(Polygon / GDELT / Yahoo RSS) with dictionary sentiment + rule-based "
    "events. No LLM. Older days via the date picker."
)

runs = list_news_article_runs()
if not runs:
    st.info(
        "No daily news archived yet "
        "(`data/news_articles_daily/{run_id}_articles.parquet`). "
        "The weekday `daily_news` producer writes the first artifact on its "
        "next post-deploy run."
    )
    st.stop()

# ── Date picker (one entry per run date, newest first) ──────────────────────
date_options = [r["date"] for r in runs]
selected_date = st.selectbox("News date", date_options, index=0)
selected = next(r for r in runs if r["date"] == selected_date)

with st.spinner(f"Loading news for {selected_date}…"):
    df = load_news_articles(selected["key"])

if df is None or df.empty:
    st.warning(f"No articles found for {selected_date}.")
    st.stop()

# Normalize / derive display fields.
df = df.copy()
df["_tickers"] = df["tickers_json"].apply(_json_list) if "tickers_json" in df else [[]] * len(df)
df["_sources"] = df["sources_json"].apply(_json_list) if "sources_json" in df else [[]] * len(df)
df["_published"] = pd.to_datetime(df.get("published_at"), errors="coerce", utc=True)
df = df.sort_values("_published", ascending=False, na_position="last").reset_index(drop=True)

sentiment = pd.to_numeric(df.get("lm_sentiment", 0.0), errors="coerce").fillna(0.0)
event_count = pd.to_numeric(df.get("event_count", 0), errors="coerce").fillna(0)

# ── Header summary ──────────────────────────────────────────────────────────
all_tickers = sorted({t for ts in df["_tickers"] for t in ts})
all_sources = sorted({s for ss in df["_sources"] for s in ss})

c1, c2, c3, c4 = st.columns(4)
c1.metric("Stories", len(df))
c2.metric("Tickers covered", len(all_tickers))
c3.metric("With events", int((event_count > 0).sum()))
pos = int((sentiment > 0.05).sum())
neg = int((sentiment < -0.05).sum())
c4.metric("Sentiment +/–", f"{pos} / {neg}")

if (sentiment == 0.0).all():
    st.warning(
        "All sentiment is 0.00 for this day — the Loughran-McDonald dictionary "
        "was unavailable when this artifact was produced (a known soak issue). "
        "Headlines, sources, and events are still accurate."
    )

# ── Filters ────────────────────────────────────────────────────────────────
f1, f2, f3 = st.columns([2, 2, 1])
ticker_filter = f1.multiselect("Filter by ticker", all_tickers, default=[])
source_filter = f2.multiselect("Filter by source", all_sources, default=[])
events_only = f3.toggle("Events only", value=False)

mask = pd.Series(True, index=df.index)
if ticker_filter:
    sel = set(ticker_filter)
    mask &= df["_tickers"].apply(lambda ts: bool(sel.intersection(ts)))
if source_filter:
    sel_s = set(source_filter)
    mask &= df["_sources"].apply(lambda ss: bool(sel_s.intersection(ss)))
if events_only:
    mask &= event_count > 0

feed = df[mask]
total_matches = len(feed)
truncated = total_matches > _MAX_FEED_ROWS
feed = feed.head(_MAX_FEED_ROWS)

st.caption(f"Showing {len(feed)} of {total_matches} matching stories.")
if truncated:
    st.info(
        f"Feed capped at {_MAX_FEED_ROWS} stories — narrow the filters to see "
        f"the remaining {total_matches - _MAX_FEED_ROWS}."
    )

st.divider()

# ── Feed (reverse-chron) ────────────────────────────────────────────────────
for _, row in feed.iterrows():
    title = str(row.get("title") or "(untitled)")
    url = str(row.get("url") or "")
    if url:
        st.markdown(f"#### [{title}]({url})")
    else:
        st.markdown(f"#### {title}")

    published = row["_published"]
    when = published.strftime("%H:%M UTC") if pd.notna(published) else "—"
    sources = row["_sources"]
    primary = str(row.get("primary_source") or (sources[0] if sources else "—"))
    n_more = max(len(sources) - 1, 0)
    src_str = primary + (f" +{n_more}" if n_more else "")
    tickers = row["_tickers"]
    ticker_str = " ".join(f"`{t}`" for t in tickers) if tickers else "—"
    sent = float(row.get("lm_sentiment") or 0.0)

    meta = f"🕑 {when}  ·  📡 {src_str}  ·  {ticker_str}  ·  {_badge(sent)}"
    if int(row.get("event_count") or 0) > 0:
        cats = str(row.get("event_categories") or "").replace(",", ", ")
        sev = float(row.get("event_severity_max") or 0.0)
        if cats:
            meta += f"  ·  ⚡ {cats} (sev {sev:.2f})"
    st.caption(meta)

    top_event = str(row.get("top_event_description") or "").strip()
    if top_event:
        st.markdown(f"**Event:** {top_event}")

    excerpt = str(row.get("body_excerpt") or "").strip()
    if excerpt:
        st.write(excerpt)

    st.divider()
