"""Submission demo readiness UI (Phase 27S.7)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from tech_cartography.runtime.v8_demo_flow_export_schema import (
  DEMO_FLOW_SAFETY_NOTICES,
  READINESS_STATUS_DEMO_OFF,
  READINESS_STATUS_READY,
  READINESS_STATUS_REMAINING,
)
from tech_cartography.services.v8_demo_flow_export_readiness import build_submission_demo_readiness


def render_submission_demo_readiness_card(
  case_id: str,
  project_root: Path,
  *,
  expanded: bool = True,
) -> None:
  items = build_submission_demo_readiness(case_id, project_root=project_root)
  with st.expander("Demo readiness（提出デモ）", expanded=expanded):
    st.caption("メール未送信・Scheduler OFF・外部API OFF は Judge Mode では正常状態です。")
    rows = []
    for item in items:
      icon = "ready" if item.status == READINESS_STATUS_READY else (
        "demo_off" if item.status == READINESS_STATUS_DEMO_OFF else "remaining"
      )
      rows.append({
        "state": icon,
        "item": item.label,
        "status": item.status,
        "detail": item.detail[:120],
      })
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    ready_count = sum(1 for i in items if i.status == READINESS_STATUS_READY)
    demo_off_count = sum(1 for i in items if i.status == READINESS_STATUS_DEMO_OFF)
    remaining = sum(1 for i in items if i.status == READINESS_STATUS_REMAINING)
    c1, c2, c3 = st.columns(3)
    c1.metric("ready", ready_count)
    c2.metric("remaining_next_action", remaining)
    c3.metric("demo_off (OK)", demo_off_count)
    for notice in DEMO_FLOW_SAFETY_NOTICES[:2]:
      st.caption(notice)
