"""Research value card rendering for Study Demo Simple Mode."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import streamlit as st

from services_v9.research_value_pipeline import build_research_value_top3
from services_v9.run_baseline_state import is_initial_baseline as is_initial_baseline_state
from services_v9.simple_review_state import (
  SIMPLE_REVIEW_OPTIONS,
  can_save_review,
  is_saved_review,
  normalize_simple_decision,
  save_review_blocked_message,
  to_backend_decision,
)
from services_v9.study_demo_ui_mode import should_show_technical_ids
from services_v9.study_demo_review_schema import normalize_review_record, validate_review_record
from services_v9.study_demo_theme_lineage import sizing_fixture_theme
from ui_v9.labels import type_label_ja
from ui_v9.study_demo_source_link import render_external_source_link


def resolve_theme_for_research_value(source_info: Mapping[str, Any]) -> dict[str, Any]:
  bundle = dict(source_info.get("study_demo_downstream", {}) or {})
  profile_draft = dict(bundle.get("profile_draft", {}) or {})
  if profile_draft.get("keywords"):
    return {
      "name": str(profile_draft.get("theme_name", "") or ""),
      "description": str(profile_draft.get("theme_description", "") or ""),
      "keywords": dict(profile_draft.get("keywords", {}) or {}),
    }
  active_context = dict(source_info.get("active_context", {}) or {})
  theme_name = str(active_context.get("theme", "") or "")
  if theme_name:
    theme = sizing_fixture_theme()
    theme["name"] = theme_name
    theme["theme_id"] = str(active_context.get("source_theme_id", "") or theme.get("theme_id", ""))
    return theme
  return sizing_fixture_theme()


def display_signal_to_integrated(display_signal: Mapping[str, Any]) -> dict[str, Any]:
  study_demo = dict(display_signal.get("study_demo", {}) or {})
  source_type = str(study_demo.get("source_type_raw", "") or display_signal.get("type", "") or "")
  if source_type == "web":
    source_type = "web_company"
  score = study_demo.get("relevance_score")
  if score is None:
    score = float(display_signal.get("score", 0) or 0) * 100.0
  return {
    "signal_id": str(display_signal.get("id", "") or ""),
    "source_type": source_type,
    "title": str(display_signal.get("title", "") or ""),
    "summary": str(display_signal.get("summary", "") or ""),
    "url": str(display_signal.get("source_url", "") or display_signal.get("resolved_url", "") or ""),
    "organization": str(display_signal.get("source_name", "") or ""),
    "relevance_tier": str(study_demo.get("relevance_tier", "") or ""),
    "relevance_score": score,
    "relevance_reason": str(study_demo.get("relevance_reason", "") or ""),
    "matched_core_terms": list(study_demo.get("matched_core_terms", []) or []),
    "matched_process_terms": list(display_signal.get("tags", []) or []),
  }


def integrated_signals_from_source(
  *,
  display_signals: Sequence[Mapping[str, Any]],
  source_info: Mapping[str, Any],
) -> list[dict[str, Any]]:
  bundle = dict(source_info.get("study_demo_downstream", {}) or {})
  integrated = dict(bundle.get("integrated", {}) or {})
  raw_signals = list(integrated.get("signals", []) or [])
  if raw_signals:
    return [dict(item) for item in raw_signals]
  return [display_signal_to_integrated(item) for item in display_signals if isinstance(item, dict)]


def is_initial_baseline_run(source_info: Mapping[str, Any]) -> bool:
  bundle = dict(source_info.get("study_demo_downstream", {}) or {})
  weekly_state = dict(bundle.get("weekly_state", {}) or {})
  return is_initial_baseline_state(weekly_state)


def render_simple_review_input(
  *,
  signal_id: str,
  search_run_id: str,
  active_run_id: str,
) -> None:
  session_key = f"study_demo_review_run_{active_run_id}"
  if st.session_state.get("study_demo_review_active_run") != active_run_id:
    st.session_state["study_demo_review_active_run"] = active_run_id
    st.session_state["reviews_by_signal_id"] = {}

  reviews_by_signal_id = dict(st.session_state.get("reviews_by_signal_id", {}) or {})
  existing = reviews_by_signal_id.get(signal_id, {})
  decision_key = f"simple_review_decision_{active_run_id}_{signal_id}"
  comment_key = f"simple_review_comment_{active_run_id}_{signal_id}"
  apply_key = f"simple_review_apply_{active_run_id}_{signal_id}"

  labels = [label for _, label in SIMPLE_REVIEW_OPTIONS]
  codes = [code for code, _ in SIMPLE_REVIEW_OPTIONS]
  default_code = "unreviewed"
  if is_saved_review(existing):
    default_code = normalize_simple_decision(existing.get("decision", ""))
  default_label = next((label for code, label in SIMPLE_REVIEW_OPTIONS if code == default_code), "未判断")
  if decision_key not in st.session_state:
    st.session_state[decision_key] = default_label
  if comment_key not in st.session_state:
    st.session_state[comment_key] = str(existing.get("comment", "") or "")

  selected_label = st.radio("人間レビュー", labels, key=decision_key, horizontal=True)
  selected_code = codes[labels.index(selected_label)]
  comment = st.text_area("メモ（任意）", key=comment_key, height=68)
  if st.button("レビューを保存", key=apply_key):
    if not can_save_review(selected_code):
      st.error(save_review_blocked_message())
      return
    backend_decision = to_backend_decision(selected_code)
    if not backend_decision:
      st.error(save_review_blocked_message())
      return
    record = normalize_review_record(
      {
        "signal_id": signal_id,
        "decision": backend_decision,
        "reason_codes": ["unclear_relevance"] if backend_decision == "hold" else ["direct_evidence"],
        "comment": comment,
        "reviewed": True,
      },
      signal_id=signal_id,
      search_run_id=search_run_id,
    )
    warnings = validate_review_record(record)
    if warnings:
      st.warning(" / ".join(warnings))
    updated = dict(reviews_by_signal_id)
    updated[signal_id] = record
    st.session_state["reviews_by_signal_id"] = updated
    st.success("レビューを保存しました（セッション内）")


def render_research_value_card(
  *,
  item: Mapping[str, Any],
  display_signal: Mapping[str, Any],
  search_run_id: str,
  key_namespace: str,
  index: int,
  initial_baseline: bool = False,
) -> None:
  output = dict(item.get("output", {}) or {})
  role = dict(output.get("role", {}) or {})
  signal = dict(item.get("signal", {}) or {})
  source_type = str(signal.get("source_type", "") or display_signal.get("type", "") or "")
  if source_type == "web_company":
    source_type = "web"
  type_label = type_label_ja(source_type if source_type in {"patent", "paper", "web"} else display_signal.get("type", "web"))

  rank = int(item.get("rank", index) or index)
  st.markdown(f"**{rank}位** | {type_label}")
  if initial_baseline:
    st.caption("変更: 初回候補")
  st.markdown(f"**{role.get('label_ja', '')}**")
  st.markdown(f"##### {output.get('short_title_ja', '')}")
  st.caption(str(output.get("original_title", "") or signal.get("title", "")))
  st.markdown("**この文献で確認できる可能性**")
  st.write(str(output.get("research_value", "") or ""))
  st.markdown("**原典で確認する問い**")
  for question in list(output.get("verification_questions", []) or []):
    st.write(f"- {question}")
  st.markdown("**読後に残すもの**")
  st.write(str(output.get("readout_artifact", "") or ""))
  caveat = str(output.get("caveat", "") or "")
  if caveat:
    st.caption(caveat)

  class _LinkSignal:
    def __init__(self, payload: Mapping[str, Any], display: Mapping[str, Any]) -> None:
      self.title = str(payload.get("title", "") or display.get("title", ""))
      self.type = str(display.get("type", "") or payload.get("source_type", ""))
      self.source_url = str(payload.get("url", "") or display.get("source_url", "") or "")
      self.resolved_url = display.get("resolved_url", "")

  render_external_source_link(
    _LinkSignal(signal, display_signal),
    key_namespace=key_namespace,
    search_run_id=search_run_id,
    label="原典を確認",
  )

  signal_id = str(display_signal.get("id", "") or signal.get("signal_id", "") or "")
  if signal_id:
    with st.expander("人間レビュー", expanded=False):
      render_simple_review_input(
        signal_id=signal_id,
        search_run_id=search_run_id,
        active_run_id=search_run_id,
      )

  ranking_basis = dict(output.get("ranking_basis", {}) or {})
  with st.expander("ランキング根拠", expanded=False):
    st.write(str(ranking_basis.get("summary", "") or ""))
    for label in list(ranking_basis.get("human_labels", []) or []):
      st.write(label)
    if should_show_technical_ids():
      for evidence in list(ranking_basis.get("raw_evidence", []) or []):
        st.write(f"- {evidence.get('kind', '')}: {evidence.get('value', '')}")
      for evidence in list(ranking_basis.get("evidence", []) or []):
        st.write(f"- verified {evidence.get('field', '')}: {evidence.get('term', '')}")
      st.write(f"- confidence: {output.get('confidence', '')}")


def build_research_value_bundle(
  *,
  display_signals: Sequence[Mapping[str, Any]],
  source_info: Mapping[str, Any],
  limit: int = 3,
) -> dict[str, Any]:
  theme = resolve_theme_for_research_value(source_info)
  integrated = integrated_signals_from_source(display_signals=display_signals, source_info=source_info)
  return build_research_value_top3(integrated, theme, limit=limit)


__all__ = [
  "build_research_value_bundle",
  "display_signal_to_integrated",
  "integrated_signals_from_source",
  "is_initial_baseline_run",
  "render_research_value_card",
  "render_simple_review_input",
  "resolve_theme_for_research_value",
]
