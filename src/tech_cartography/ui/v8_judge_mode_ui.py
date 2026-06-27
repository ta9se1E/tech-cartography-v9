"""Judge Mode UI helpers — conclusion cards, sidebar funnel (Phase 27R.1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from tech_cartography.runtime.v8_one_case_demo_schema import DEFAULT_ONE_CASE_ID
from tech_cartography.ui.v8_judge_mode_copy import (
  CASE_01_FUNNEL_DEFAULTS,
  DEEP_RESEARCH_DIFF,
  JUDGE_APP_SUBTITLE,
  JUDGE_APP_TITLE,
  JUDGE_CASE_01_LABEL,
  JUDGE_CONCLUSION_CARDS,
  JUDGE_DEMO_SAFETY_LINES,
  JUDGE_NEXT_TAB,
  THREE_MINUTE_DEMO_STEPS,
)
from tech_cartography.ui.v8_tab_config import V8_TAB_LABELS


def load_case1_funnel_metrics(project_root: Path | str) -> dict[str, Any]:
  """Read-only snapshot for sidebar — falls back to known Case 1 defaults."""
  metrics: dict[str, Any] = dict(CASE_01_FUNNEL_DEFAULTS)
  try:
    from tech_cartography.services.v8_claim_map import build_claim_map
    from tech_cartography.services.v8_evidence_map import build_evidence_map
    from tech_cartography.services.v8_gap_next_actions import build_gap_next_actions_report

    case_id = DEFAULT_ONE_CASE_ID
    claim_map = build_claim_map(case_id=case_id, project_root=project_root)
    evidence_map = build_evidence_map(case_id=case_id, project_root=project_root)
    gap_report = build_gap_next_actions_report(case_id=case_id, project_root=project_root)
    metrics["claims"] = claim_map.claim_count
    metrics["loaded_claims"] = claim_map.loaded_claim_count
    metrics["not_loaded_claims"] = claim_map.not_loaded_claim_count
    metrics["evidence_links"] = evidence_map.link_count
    metrics["claim_text_required"] = evidence_map.claim_text_required_count
    metrics["gaps"] = gap_report.gap_count
    if gap_report.top_3_actions:
      metrics["next_action"] = gap_report.top_3_actions[0].action_type
  except Exception:
    pass
  return metrics


def render_judge_conclusion_card(tab_id: str) -> None:
  text = JUDGE_CONCLUSION_CARDS.get(tab_id)
  if not text:
    return
  if tab_id == "intro":
    st.success(text)
    st.info(DEEP_RESEARCH_DIFF)
  else:
    st.info(text)


def render_judge_next_tab_hint(tab_id: str) -> None:
  next_id = JUDGE_NEXT_TAB.get(tab_id)
  if not next_id:
    return
  label = V8_TAB_LABELS.get(next_id, next_id)
  st.caption(f"次に見るタブ: {label}")


def render_judge_three_minute_guide(*, expanded: bool = False) -> None:
  with st.expander("3分デモ導線", expanded=expanded):
    for step in THREE_MINUTE_DEMO_STEPS:
      st.markdown(f"- {step}")


def render_judge_mode_sidebar(*, project_root: Path) -> None:
  from tech_cartography.ui.v8_input_ui import get_v8_input_state
  from tech_cartography.ui.v8_tab_config import STATE_V8_SELECTED_CASE

  st.divider()
  st.markdown(f"**{JUDGE_APP_TITLE}**")
  st.caption(JUDGE_APP_SUBTITLE)

  case_id = str(
    get_v8_input_state().get("selected_case_id")
    or st.session_state.get(STATE_V8_SELECTED_CASE)
    or DEFAULT_ONE_CASE_ID
  )
  st.markdown("**現在のケース**")
  st.caption(JUDGE_CASE_01_LABEL if case_id == DEFAULT_ONE_CASE_ID else case_id)

  metrics = load_case1_funnel_metrics(project_root)
  st.markdown("**今回の成果ファネル**")
  st.caption(f"候補特許: {metrics.get('candidates', 1000):,}件")
  st.caption(f"選抜: Top {metrics.get('top5', 5)}")
  st.caption(f"請求項: {metrics.get('claims', 35)}件投入済")
  st.caption(f"裏取り候補: {metrics.get('evidence_links', 351)} links")
  st.caption(f"未確認Gap: {metrics.get('gaps', 106)}件")
  st.caption(f"次アクション: {metrics.get('next_action', 'check_patent_examples')}")

  st.markdown("**デモモード**")
  for line in JUDGE_DEMO_SAFETY_LINES:
    st.caption(line)

  st.markdown("**次に見るタブ**")
  st.caption(V8_TAB_LABELS.get("patent_shortlist", "読むべき特許｜Top5"))
