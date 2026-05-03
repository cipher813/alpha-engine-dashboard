"""LLM-as-judge eval artifact loader (PR 4d, ROADMAP §1632-1633).

Loads ``decision_artifacts/_eval/{YYYY-MM-DD}/{judged_agent_id}/
{run_id}.{judge_model}.json`` artifacts from S3 and shapes them into
a long-format DataFrame the quality-trend page can pivot:

  | eval_date | judged_agent_id | criterion | score | judge_model |
  | rubric_id | rubric_version  | run_id    | overall_reasoning   |

The dashboard page reads the DataFrame directly. Per-page caching
(``@st.cache_data``) sits on this loader's public function rather
than the per-artifact fetches so the cache key is a (start, end)
date range — tight enough to update on demand but coarse enough that
flipping ticker filters in the UI doesn't re-fetch S3.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import pandas as pd
import streamlit as st

from loaders.s3_loader import (
    _fetch_s3_json,
    _research_bucket,
    get_s3_client,
)

logger = logging.getLogger(__name__)


_EVAL_PREFIX = "decision_artifacts/_eval/"


def _list_eval_dates(bucket: str, *, max_days: int = 180) -> list[str]:
    """Return YYYY-MM-DD subprefix names under decision_artifacts/_eval/.

    Each subprefix corresponds to one eval-pipeline run date. Capped
    at ``max_days`` so the dashboard never fetches an unbounded
    history (CloudWatch metric retention is 15 months; the line-chart
    page rarely needs more than ~6 months of trailing data).
    """
    client = get_s3_client()
    paginator = client.get_paginator("list_objects_v2")
    dates: set[str] = set()
    try:
        for page in paginator.paginate(
            Bucket=bucket, Prefix=_EVAL_PREFIX, Delimiter="/",
        ):
            for cp in page.get("CommonPrefixes", []):
                # cp["Prefix"] looks like "decision_artifacts/_eval/2026-05-09/"
                trailing = cp["Prefix"][len(_EVAL_PREFIX):].rstrip("/")
                if len(trailing) == 10 and trailing.count("-") == 2:
                    dates.add(trailing)
    except Exception:  # noqa: BLE001
        logger.exception("[eval_loader] list eval dates failed")
        return []
    return sorted(dates)[-max_days:]


def _list_eval_keys_for_date(bucket: str, eval_date: str) -> list[str]:
    """Return every eval-artifact JSON key under one date partition."""
    client = get_s3_client()
    prefix = f"{_EVAL_PREFIX}{eval_date}/"
    paginator = client.get_paginator("list_objects_v2")
    keys: list[str] = []
    try:
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith(".json"):
                    keys.append(key)
    except Exception:  # noqa: BLE001
        logger.exception(
            "[eval_loader] list keys failed for date=%s", eval_date,
        )
    return keys


def _explode_eval_artifact(artifact: dict[str, Any], eval_date: str) -> list[dict]:
    """One row per (artifact, dimension) — long format for plotting."""
    rows: list[dict] = []
    judge_model = artifact.get("judge_model", "")
    judged_agent_id = artifact.get("judged_agent_id", "")
    rubric_id = artifact.get("rubric_id", "")
    rubric_version = artifact.get("rubric_version", "")
    run_id = artifact.get("run_id", "")
    overall = artifact.get("overall_reasoning", "")
    for dim in artifact.get("dimension_scores", []) or []:
        rows.append({
            "eval_date": eval_date,
            "judged_agent_id": judged_agent_id,
            "criterion": dim.get("dimension", ""),
            "score": dim.get("score"),
            "reasoning": dim.get("reasoning", ""),
            "judge_model": judge_model,
            "rubric_id": rubric_id,
            "rubric_version": rubric_version,
            "run_id": run_id,
            "overall_reasoning": overall,
        })
    return rows


@st.cache_data(ttl=900)
def load_eval_artifacts(
    start_date: date | None = None,
    end_date: date | None = None,
    *,
    bucket: str | None = None,
) -> pd.DataFrame:
    """Load eval artifacts within ``[start_date, end_date]`` and return
    a long-format DataFrame.

    Defaults: ``end_date`` = today, ``start_date`` = end - 180 days.
    Returns an empty DataFrame with the expected schema when no eval
    artifacts have been written yet (first-run case during PR 4 deploy).
    """
    bkt = bucket or _research_bucket()
    end = end_date or date.today()
    start = start_date or (end - timedelta(days=180))

    all_dates = _list_eval_dates(bkt)
    in_window = [
        d for d in all_dates
        if start.isoformat() <= d <= end.isoformat()
    ]

    rows: list[dict] = []
    for d in in_window:
        for key in _list_eval_keys_for_date(bkt, d):
            artifact = _fetch_s3_json(bkt, key)
            if not artifact:
                continue
            rows.extend(_explode_eval_artifact(artifact, d))

    columns = [
        "eval_date", "judged_agent_id", "criterion", "score",
        "reasoning", "judge_model", "rubric_id", "rubric_version",
        "run_id", "overall_reasoning",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(rows, columns=columns)
    df["eval_date"] = pd.to_datetime(df["eval_date"])
    df["score"] = pd.to_numeric(df["score"], errors="coerce")
    return df.dropna(subset=["score"]).sort_values(
        ["eval_date", "judged_agent_id", "criterion", "judge_model"],
    ).reset_index(drop=True)
