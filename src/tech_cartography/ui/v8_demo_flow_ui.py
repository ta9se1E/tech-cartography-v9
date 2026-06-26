"""v8 Demo flow UI — shared header / step guide (Phase 27M)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from tech_cartography.runtime.v8_demo_readiness_schema import V8CaseDemoReadiness, V8DemoStepStatus
from tech_cartography.services.v8_demo_readiness import assess_case_demo_readiness
from tech_cartography.ui.easy_japanese_ui import render_info_box, render_warning_box
from tech_cartography.ui.v8_tab_config import (
  STATE_V8_INPUT,
  STATE_V8_SELECTED_CASE,
  V8_CASE_SAMPLES,
  V8_TAB_LABELS,
)
from tech_cartography.ui.v8_text_rendering import render_next_action_card

STATE_V8_DEMO_READINESS = "v8_demo_readiness_cache"

STATUS_BADGE: dict[str, str] = {
  "ready": "✅ ready",
  "warning": "⚠️ warning",
  "missing": "❌ missing",
  "not_generated": "⬜ not_generated",
  "needs_previous_step": "⏳ needs_previous_step",
  "skipped": "⏭ skipped",
}

FLOW_STEPS: tuple[tuple[str, str], ...] = (
  ("input", "input"),
  ("sources", "sources"),
  ("large_candidate_shortlist", "patent_shortlist"),
  ("claim_map", "claim_map"),
  ("manual_claim_injection", "claim_map"),
  ("evidence_map", "evidence_map"),
  ("gap_next_actions", "gap_next_actions"),
  ("fixed_point_observation", "fixed_point_observation"),
  ("export", "export"),
)


def _case_options() -> list[tuple[str, str]]:
  return [(s["case_id"], s["label"]) for s in V8_CASE_SAMPLES]


def get_selected_case_id() -> str:
  state = st.session_state.get(STATE_V8_INPUT)
  if isinstance(state, dict) and state.get("selected_case_id"):
    return str(state["selected_case_id"]).strip()
  return str(
    st.session_state.get(STATE_V8_SELECTED_CASE)
    or V8_CASE_SAMPLES[0]["case_id"]
  ).strip()


def _load_readiness(case_id: str, project_root: Path, *, force: bool = False) -> V8CaseDemoReadiness:
  cache_key = f"{STATE_V8_DEMO_READINESS}:{case_id}"
  if not force and isinstance(st.session_state.get(cache_key), V8CaseDemoReadiness):
    return st.session_state[cache_key]
  try:
    readiness = assess_case_demo_readiness(case_id, project_root=project_root)
    st.session_state[cache_key] = readiness
    st.session_state[STATE_V8_DEMO_READINESS] = {
      "case_id": case_id,
      "readiness": readiness.to_dict(),
    }
    return readiness
  except Exception as exc:
    st.warning(f"Demo Readiness 取得エラー: {exc}")
    return V8CaseDemoReadiness(
      case_id=case_id,
      case_name=case_id,
      generated_at="",
      overall_status="not_ready",
      current_recommended_step="入力",
    )


def render_case_selector(*, key: str = "v8_demo_flow_case") -> str:
  case_ids = [c for c, _ in _case_options()]
  labels = {c: label for c, label in _case_options()}
  current = get_selected_case_id()
  default_idx = case_ids.index(current) if current in case_ids else 0
  selected = st.selectbox(
    "案件 (Demo Readiness)",
    options=case_ids,
    index=default_idx,
    format_func=lambda cid: labels[cid],
    key=key,
  )
  st.session_state[STATE_V8_SELECTED_CASE] = selected
  if isinstance(st.session_state.get(STATE_V8_INPUT), dict):
    st.session_state[STATE_V8_INPUT]["selected_case_id"] = selected
  return selected


def _step_for_tab(current_tab: str, steps: list[V8DemoStepStatus]) -> V8DemoStepStatus | None:
  tab_to_step = {
    "input": "input",
    "sources": "sources",
    "patent_shortlist": "large_candidate_shortlist",
    "claim_map": "claim_map",
    "evidence_map": "evidence_map",
    "gap_next_actions": "gap_next_actions",
    "fixed_point_observation": "fixed_point_observation",
    "export": "export",
  }
  step_name = tab_to_step.get(current_tab)
  if not step_name:
    return None
  for step in steps:
    if step.step_name == step_name:
      return step
  return None


def format_count_label(value: int | None, *, artifact_label: str) -> str:
  if value is None:
    return f"{artifact_label}: artifact missing (not true zero)"
  return str(value)


def render_demo_flow_header(
  *,
  project_root: Path | str,
  current_tab: str = "",
  compact: bool = True,
) -> V8CaseDemoReadiness | None:
  """Render shared demo flow header. Returns readiness or None on error."""
  root = Path(project_root)
  col_case, col_refresh = st.columns([4, 1])
  with col_case:
    case_id = render_case_selector(key=f"v8_demo_flow_case_{current_tab}")
  with col_refresh:
    if st.button("Readiness更新", key=f"v8_demo_readiness_refresh_{current_tab}"):
      _load_readiness(case_id, root, force=True)
      st.rerun()

  readiness = _load_readiness(case_id, root)
  c1, c2, c3, c4 = st.columns(4)
  c1.metric("overall", readiness.overall_status)
  c2.metric("steps", f"{readiness.completed_step_count}/{readiness.total_step_count}")
  c3.metric("evidence", format_count_label(readiness.evidence_link_count, artifact_label="links"))
  c4.metric("gap", format_count_label(readiness.gap_count, artifact_label="gaps"))

  if readiness.next_3_user_actions:
    st.markdown(
      render_next_action_card("次にやること", readiness.next_3_user_actions[:3]),
      unsafe_allow_html=True,
    )

  if not compact:
    _render_step_guide(readiness, current_tab=current_tab)
  return readiness


def _render_step_guide(readiness: V8CaseDemoReadiness, *, current_tab: str = "") -> None:
  step_map = {s.step_name: s for s in readiness.step_statuses}
  st.markdown("**デモステップガイド**")
  for step_name, tab_key in FLOW_STEPS:
    step = step_map.get(step_name)
    if not step:
      continue
    badge = STATUS_BADGE.get(step.status, step.status)
    label = V8_TAB_LABELS.get(tab_key, tab_key)
    highlight = " ← 今ここ" if tab_key == current_tab or step_name == current_tab else ""
    st.caption(f"{badge} {label}{highlight}: {step.summary[:80]}")


def render_demo_flow_banner(
  *,
  project_root: Path | str,
  current_tab: str,
  tab_purpose: str,
  next_tab_key: str,
) -> None:
  """Lightweight banner: purpose + next tab + artifact status for current tab."""
  root = Path(project_root)
  case_id = get_selected_case_id()
  try:
    readiness = _load_readiness(case_id, root)
  except Exception:
    return

  current_step = _step_for_tab(current_tab, readiness.step_statuses)
  next_label = V8_TAB_LABELS.get(next_tab_key, next_tab_key)

  lines = [f"<strong>{tab_purpose}</strong>"]
  if current_step:
    badge = STATUS_BADGE.get(current_step.status, current_step.status)
    lines.append(f"status: {badge} — {current_step.summary}")
    if current_step.status == "not_generated":
      lines.append("artifact missing — true zero ではありません")
      if current_step.next_user_action:
        lines.append(f"→ {current_step.next_user_action}")
  lines.append(f"次: 「{next_label}」タブへ")
  st.markdown(render_info_box("<br>".join(lines)), unsafe_allow_html=True)


def render_artifact_count_metric(
  label: str,
  count: int | None,
  *,
  artifact_exists: bool,
) -> None:
  if not artifact_exists:
    st.metric(label, "未生成", help="artifact missing — true zero ではありません")
  elif count is None:
    st.metric(label, "—", help="artifact あり — 件数未取得")
  else:
    st.metric(label, count, help="artifact 生成済みの true count")
