"""Director — the weekly advisory action plan (Layer C).

Reads ``director/{date}/action_plan.json`` + ``director/carryover_ledger.json``
(produced by the alpha-engine-evaluator-director Lambda, the final Saturday-
pipeline task once `DIRECTOR_ENABLED` is on). The Director weighs the Report
Card and *proposes* a structured action plan with carry-over — it never writes
live trading config and never self-merges. This page is read-only observability
for the observe-mode soak.
"""

import streamlit as st

from components.director_plan import render_overview
from loaders.s3_loader import load_action_plan, load_carryover_ledger

st.title("🧭 Director — Weekly Action Plan")
st.caption(
    "The slow loop: a single Opus call over the Report Card proposes the week's "
    "structured action plan (owners, priorities, horizons) with carry-over. "
    "Advisory only — it proposes; Brian disposes. Dormant until `DIRECTOR_ENABLED`."
)

render_overview(load_action_plan(), load_carryover_ledger())
