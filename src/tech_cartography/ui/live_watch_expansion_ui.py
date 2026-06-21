"""Watch Expansion Proposals UI — human approval only (Phase 25I)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from tech_cartography.auth.basic_auth import is_login_required
from tech_cartography.services.live_digest_preview import find_latest_live_digest_preview_path
from tech_cartography.services.live_watch_expansion_proposal import (
  SAFETY_NOTICE,
  create_live_watch_expansion_proposals_from_latest,
  find_latest_live_watch_expansion_proposals_path,
  load_latest_live_watch_expansion_proposals,
)
from tech_cartography.services.live_web_signal_pack import find_latest_live_web_signal_pack_path
from tech_cartography.services.watch_profile_draft import (
  DRAFT_SAFETY_NOTICE,
  apply_human_watch_expansion_decisions,
  load_latest_watch_profile_draft,
)
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_warning_box
from tech_cartography.ui.login_ui import (
  can_use_admin_features,
  get_auth_role,
  get_basic_auth_session,
  is_basic_authenticated,
)
from tech_cartography.users.watch_profile_store import get_active_watch_profile


def should_show_live_watch_expansion_ui() -> bool:
  return is_login_required() and can_use_admin_features()


def _approved_by_label() -> str:
  session = get_basic_auth_session()
  if session:
    return str(session.get("username") or session.get("display_name") or "admin")
  return "admin"


def _resolve_watch_profile() -> dict[str, Any] | None:
  session = get_basic_auth_session()
  if not session:
    return None
  username = str(session.get("username") or "admin")
  return get_active_watch_profile(f"basic-auth:{username}")


def render_live_watch_expansion_section(
  *,
  project_root: Path | str,
  key_prefix: str = "live_watch_expansion",
) -> None:
  if not should_show_live_watch_expansion_ui():
    return

  pack_path = find_latest_live_web_signal_pack_path(project_root)
  digest_path = find_latest_live_digest_preview_path(project_root)
  proposals_path = find_latest_live_watch_expansion_proposals_path(project_root)

  with st.expander("Watch Expansion Proposals（承認前）", expanded=False):
    st.markdown(
      render_caution_box(
        "保存済み Web Signal / Digest Preview から監視範囲拡張候補を<strong>提案</strong>します。"
        " 自動反映はしません。チェックした項目を人間が承認または却下した場合のみ Watch Profile Draft に保存します。"
        " 本番 Watch Profile は更新しません。"
      ),
      unsafe_allow_html=True,
    )
    st.markdown(render_info_box(SAFETY_NOTICE), unsafe_allow_html=True)

    if not pack_path:
      st.markdown(
        render_warning_box("latest live_web_signal_pack がありません。先に Web Signal Pack を作成してください。"),
        unsafe_allow_html=True,
      )
      return

    st.caption(f"source pack: {pack_path}")
    if digest_path:
      st.caption(f"source digest: {digest_path}")
    else:
      st.caption("source digest: (optional — not found)")

    theme_name = st.text_input(
      "theme_name",
      value="Carbon Fiber Intelligence",
      key=f"{key_prefix}_theme_name",
    )

    if st.button("監視範囲の拡張候補を作成", key=f"{key_prefix}_create", type="primary"):
      result = create_live_watch_expansion_proposals_from_latest(
        output_root=project_root,
        theme_name=theme_name,
        watch_profile=_resolve_watch_profile(),
        login_required=is_login_required(),
        is_authenticated=is_basic_authenticated(),
        auth_role=get_auth_role(),
      )
      st.session_state[f"{key_prefix}_last_create"] = result
      if result.get("ok"):
        st.session_state[f"{key_prefix}_active_document"] = result.get("document")
        st.session_state[f"{key_prefix}_active_path"] = (result.get("saved_paths") or {}).get("json")

    create_result: dict[str, Any] | None = st.session_state.get(f"{key_prefix}_last_create")
    if create_result and not create_result.get("ok"):
      st.warning(str(create_result.get("message") or "候補作成に失敗しました"))

    document: dict[str, Any] | None = st.session_state.get(f"{key_prefix}_active_document")
    active_path = st.session_state.get(f"{key_prefix}_active_path")
    if document is None:
      document = load_latest_live_watch_expansion_proposals(project_root)
      if document and proposals_path:
        active_path = str(proposals_path)

    proposals = list((document or {}).get("proposals") or [])
    if not proposals:
      st.info("拡張候補がありません。「監視範囲の拡張候補を作成」を実行してください。")
      return

    if active_path:
      st.caption(f"proposals file: {active_path}")

    display_rows = [
      {
        "select": False,
        "proposal_id": row.get("proposal_id"),
        "proposal_type": row.get("proposal_type"),
        "proposed_value": row.get("proposed_value"),
        "confidence_label": row.get("confidence_label"),
        "review_status": row.get("review_status"),
        "safety_label": row.get("safety_label"),
        "reason": row.get("reason"),
      }
      for row in proposals
    ]
    st.dataframe(
      pd.DataFrame(display_rows).drop(columns=["select"]),
      use_container_width=True,
      hide_index=True,
    )

    selected_ids: list[str] = []
    for row in proposals:
      proposal_id = str(row.get("proposal_id") or "")
      if not proposal_id:
        continue
      if st.checkbox(
        f"{row.get('proposal_type')}: {row.get('proposed_value')}",
        key=f"{key_prefix}_pick_{proposal_id}",
      ):
        selected_ids.append(proposal_id)

    col_approve, col_reject = st.columns(2)
    with col_approve:
      approve_clicked = st.button(
        "選択を承認して Watch Profile Draft に保存",
        key=f"{key_prefix}_approve",
        type="primary",
        disabled=not selected_ids,
      )
    with col_reject:
      reject_clicked = st.button(
        "選択を却下として記録",
        key=f"{key_prefix}_reject",
        disabled=not selected_ids,
      )

    if not active_path or not document:
      return

    if approve_clicked:
      decision = apply_human_watch_expansion_decisions(
        proposals_document=document,
        approved_proposal_ids=selected_ids,
        rejected_proposal_ids=[],
        approved_by=_approved_by_label(),
        source_proposal_path=str(active_path),
        output_root=project_root,
      )
      st.session_state[f"{key_prefix}_last_decision"] = decision

    if reject_clicked:
      decision = apply_human_watch_expansion_decisions(
        proposals_document=document,
        approved_proposal_ids=[],
        rejected_proposal_ids=selected_ids,
        approved_by=_approved_by_label(),
        source_proposal_path=str(active_path),
        output_root=project_root,
      )
      st.session_state[f"{key_prefix}_last_decision"] = decision

    decision_result: dict[str, Any] | None = st.session_state.get(f"{key_prefix}_last_decision")
    if not decision_result:
      return

    if decision_result.get("ok"):
      st.success(str(decision_result.get("message") or "Watch Profile Draft を保存しました。"))
      saved_paths = decision_result.get("saved_paths") or {}
      for label in ("json", "markdown"):
        if saved_paths.get(label):
          st.caption(f"draft ({label}): {saved_paths[label]}")
    else:
      st.warning(str(decision_result.get("message") or "保存に失敗しました。"))


def render_watch_profile_draft_reports_section(
  *,
  project_root: Path | str,
  key_prefix: str = "reports_watch_profile_draft",
) -> None:
  """Show latest human-approved Watch Profile Draft on reports/settings (analyst/live)."""
  draft = load_latest_watch_profile_draft(project_root)
  if not draft:
    return

  with st.expander("Approved Watch Profile Draft（人間承認済み）", expanded=False):
    st.markdown(
      render_caution_box(
        "これは人間承認済みの Watch Profile Draft です。"
        " 本番 Watch Profile は自動更新されていません。"
      ),
      unsafe_allow_html=True,
    )
    st.markdown(f"**theme_name:** {draft.get('theme_name')}")
    st.caption(f"approved_by: {draft.get('approved_by')} | approved_at: {draft.get('approved_at')}")

    for label, title in (
      ("approved_keywords", "approved keywords"),
      ("approved_companies", "approved companies"),
      ("approved_public_projects", "approved public projects"),
      ("approved_technology_terms", "approved technology terms"),
      ("approved_market_applications", "approved market applications"),
    ):
      items = draft.get(label) or []
      if items:
        st.markdown(f"**{title}**")
        for item in items:
          st.markdown(f"- {item}")

    queries = draft.get("next_monitoring_query_candidates") or []
    if queries:
      st.markdown("**next monitoring query候補**")
      for query in queries:
        st.markdown(f"- `{query}`")

    st.markdown(render_info_box(str(draft.get("safety_notice") or DRAFT_SAFETY_NOTICE)), unsafe_allow_html=True)
