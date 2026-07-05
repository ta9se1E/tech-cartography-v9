"""Review and proposal UI for Study Demo."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import streamlit as st

from services_v9.study_demo_review_proposals import (
  PROPOSAL_STATUS_APPROVED,
  PROPOSAL_STATUS_REJECTED,
  apply_approved_proposals_to_profile_draft,
)
from services_v9.study_demo_review_schema import (
  normalize_decision,
  normalize_review_record,
  reason_label_ja,
  reasons_for_decision,
  validate_review_record,
)


DECISION_OPTIONS = [
  ("accept", "採用"),
  ("hold", "保留"),
  ("reject", "見送り"),
]


def _decision_label(value: str) -> str:
  for code, label in DECISION_OPTIONS:
    if code == value:
      return label
  return "保留"


def render_enhanced_review_input(
  *,
  signal: Mapping[str, Any],
  signal_id: str,
  search_run_id: str,
  context_generation: int | None = None,
  active_run_id: str,
) -> dict[str, Any]:
  session_key = f"study_demo_review_run_{active_run_id}"
  if st.session_state.get("study_demo_review_active_run") != active_run_id:
    st.session_state["study_demo_review_active_run"] = active_run_id
    st.session_state["reviews_by_signal_id"] = {}

  reviews_by_signal_id = dict(st.session_state.get("reviews_by_signal_id", {}) or {})
  existing = reviews_by_signal_id.get(signal_id, {})
  decision_key = f"review_decision_v2_{active_run_id}_{signal_id}"
  reasons_key = f"review_reasons_v2_{active_run_id}_{signal_id}"
  comment_key = f"review_comment_v2_{active_run_id}_{signal_id}"
  apply_key = f"review_apply_v2_{active_run_id}_{signal_id}"

  default_decision = normalize_decision(existing.get("decision", existing.get("review_decision", "hold")))
  if decision_key not in st.session_state:
    st.session_state[decision_key] = default_decision
  decision = st.radio(
    "レビュー判断",
    options=[code for code, _ in DECISION_OPTIONS],
    format_func=_decision_label,
    key=decision_key,
    horizontal=True,
  )
  reason_options = reasons_for_decision(decision)
  if reasons_key not in st.session_state:
    st.session_state[reasons_key] = list(existing.get("reason_codes", []) or [])
  selected_reasons = st.multiselect(
    "理由コード",
    options=reason_options,
    format_func=reason_label_ja,
    key=reasons_key,
  )
  if comment_key not in st.session_state:
    st.session_state[comment_key] = str(existing.get("comment", existing.get("review_note", "")) or "")
  comment = st.text_area("コメント", key=comment_key, height=80)

  saved = False
  if st.button("レビューを保存", key=apply_key):
    record = normalize_review_record(
      {
        "decision": decision,
        "reason_codes": selected_reasons,
        "comment": comment,
        "reviewed": True,
      },
      signal_id=signal_id,
      search_run_id=search_run_id,
      context_generation=context_generation,
    )
    warnings = validate_review_record(record)
    if warnings:
      st.warning("理由コード未選択または不整合があります。保存は可能ですが確認してください。")
    updated = dict(reviews_by_signal_id)
    updated[signal_id] = record
    st.session_state["reviews_by_signal_id"] = updated
    st.session_state[session_key] = search_run_id
    saved = True
    st.success("レビューをセッションへ保存しました。")

  if existing.get("reviewed_at"):
    st.caption(f"更新: {existing.get('reviewed_at')}")
  return {"saved": saved, "review": existing}


def render_review_proposals_section(
  *,
  downstream_bundle: Mapping[str, Any] | None,
  active_context: Mapping[str, Any] | None,
  saved_theme: Mapping[str, Any] | None,
) -> dict[str, Any]:
  st.markdown("### 人間レビューからの検索改善提案")
  bundle = dict(downstream_bundle or {})
  proposals_payload = dict(bundle.get("review_proposals", {}) or {})
  reviews = list(dict(bundle.get("reviews", {}) or {}).get("reviews", []) or [])
  summary = dict(proposals_payload.get("summary", {}) or {})
  proposals = list(proposals_payload.get("proposals", []) or [])

  st.write(f"- review件数: {summary.get('review_count', len(reviews))}")
  st.write(f"- accept/reject: {summary.get('accept_count', 0)} / {summary.get('reject_count', 0)}")
  st.write(f"- proposal件数: {summary.get('proposal_count', len(proposals))}")

  run_origin = str((active_context or {}).get("run_origin", "temporary_search") or "temporary_search")
  if run_origin == "temporary_search":
    st.info(
      "このrunは一時検索由来です。"
      "改善提案を適用するには、先にテーマ案を作成してください。"
    )

  if summary.get("observation_only"):
    st.caption("検索条件へ反映できる十分なレビューがまだありません。現在は観察結果のみ表示します。")

  approved_ids: list[str] = []
  rejected_ids: list[str] = []
  for index, proposal in enumerate(proposals):
    if proposal.get("proposal_type") == "no_change_observation":
      st.write(f"- 観察: {proposal.get('explanation')}")
      continue
    label = (
      f"{proposal.get('proposal_type')} | {proposal.get('proposed_value')} | "
      f"support={proposal.get('support_count')} | confidence={proposal.get('confidence')} | "
      f"recall={proposal.get('recall_risk')} precision={proposal.get('precision_risk')}"
    )
    cols = st.columns([4, 1, 1])
    with cols[0]:
      st.write(label)
      st.caption(str(proposal.get("explanation", "")))
    with cols[1]:
      if st.checkbox("承認候補", key=f"proposal_approve_{index}"):
        approved_ids.append(str(proposal.get("proposal_id", "")))
    with cols[2]:
      if st.checkbox("却下", key=f"proposal_reject_{index}"):
        rejected_ids.append(str(proposal.get("proposal_id", "")))

  create_draft = False
  profile_draft = None
  if st.button("選択した提案からProfile新version案を作成", key="btn_create_profile_draft_from_proposals"):
    if run_origin == "temporary_search" and not saved_theme:
      st.error("temporary runでは先にテーマ案を作成してください。")
    else:
      approved = [item for item in proposals if str(item.get("proposal_id", "")) in approved_ids]
      exclude_present = any(item.get("proposal_type") == "add_exclude_keyword" for item in approved)
      if exclude_present and not st.session_state.get("ui_exclude_proposal_confirm"):
        st.warning("除外語提案には二重確認が必要です。")
        st.session_state["ui_exclude_proposal_confirm"] = st.checkbox(
          "検索漏れの危険を理解し、この除外候補をProfile案へ反映します",
          key="ui_exclude_proposal_confirm_box",
        )
      elif approved:
        base_profile = dict(bundle.get("profile_draft", {}) or {})
        if saved_theme:
          from services_v9.study_demo_theme_lineage import build_watch_profile_from_theme

          base_profile = build_watch_profile_from_theme(saved_theme)
        for item in approved:
          item["status"] = PROPOSAL_STATUS_APPROVED
        for item in proposals:
          if str(item.get("proposal_id", "")) in rejected_ids:
            item["status"] = PROPOSAL_STATUS_REJECTED
        profile_draft = apply_approved_proposals_to_profile_draft(
          base_profile=base_profile,
          approved_proposals=approved,
          source_review_run_ids=[str((active_context or {}).get("active_search_run_id", ""))],
          theme_id=str((saved_theme or {}).get("theme_id", "theme_unassigned")),
        )
        create_draft = True
        st.success(f"Profile draft v{profile_draft.get('proposed_profile_version')} を作成しました（未適用）。")
      else:
        st.warning("承認候補を選択してください。")

  return {
    "approved_proposal_ids": approved_ids,
    "rejected_proposal_ids": rejected_ids,
    "create_profile_draft": create_draft,
    "profile_draft_from_proposals": profile_draft,
  }
