"""Run History UI — operational execution records (Phase 25M)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from tech_cartography.auth.basic_auth import is_login_required
from tech_cartography.runtime.user_context import resolve_user_context
from tech_cartography.services.live_run_history import SAFETY_LABEL, list_run_history_entries
from tech_cartography.ui.easy_japanese_ui import render_info_box
from tech_cartography.ui.login_ui import can_use_admin_features, can_use_production_features


def should_show_run_history_ui() -> bool:
  return is_login_required() and can_use_production_features()


def render_run_history_section(
  *,
  project_root: Path | str,
  key_prefix: str = "live_run_history",
  expanded: bool = False,
) -> None:
  if not should_show_run_history_ui():
    return

  viewer = resolve_user_context()
  is_admin = bool(viewer.get("is_admin"))

  with st.expander("Run History（実行履歴）", expanded=expanded):
    st.markdown(
      render_info_box(
        "ログインユーザーの Live 手動実行記録です。"
        " これは<strong>監査ログではなく</strong>業務上の実行履歴です。"
        f" {SAFETY_LABEL}。"
      ),
      unsafe_allow_html=True,
    )
    st.caption(
      f"viewer: {viewer.get('display_name')} ({viewer.get('user_id')}) / role={viewer.get('role')}"
    )

    filter_user = None
    filter_action = None
    filter_status = None
    if is_admin:
      cols = st.columns(3)
      with cols[0]:
        filter_user = st.text_input("user_id 絞り込み", value="", key=f"{key_prefix}_filter_user") or None
      with cols[1]:
        filter_action = st.selectbox(
          "action_type",
          options=["(all)", "live_web_signal_pack", "live_digest_preview", "live_digest_preview_with_web_signals",
                   "live_web_signal_review", "live_web_signal_collection", "live_evidence_gap_build",
                   "live_strategic_watch_brief_build", "live_weekly_decision_cockpit_build", "self_only_email_send",
                   "watch_expansion_proposal", "watch_profile_draft", "next_cycle_search_plan",
                   "next_cycle_web_signal_pack", "live_operation_status", "live_beta_release_pack"],
          key=f"{key_prefix}_filter_action",
        )
        if filter_action == "(all)":
          filter_action = None
      with cols[2]:
        filter_status = st.selectbox(
          "status",
          options=["(all)", "success", "failed", "blocked", "skipped"],
          key=f"{key_prefix}_filter_status",
        )
        if filter_status == "(all)":
          filter_status = None
    else:
      st.caption("自分の実行履歴のみ表示します。")

    entries = list_run_history_entries(
      project_root,
      limit=20,
      user_id=filter_user,
      action_type=filter_action,
      status=filter_status,
      viewer_user_context=viewer,
    )

    if not entries:
      st.info("実行履歴がありません。Live 機能を実行するとここに記録されます。")
      return

    rows: list[dict[str, Any]] = []
    for entry in entries:
      outputs = entry.get("output_artifact_paths") or {}
      output_preview = ", ".join(f"{k}" for k in outputs.keys()) if outputs else ""
      rows.append(
        {
          "finished_at": entry.get("finished_at"),
          "action_type": entry.get("action_type"),
          "status": entry.get("status"),
          "user_id": entry.get("user_id"),
          "theme_name": entry.get("theme_name"),
          "run_id": entry.get("run_id"),
          "outputs": output_preview,
          "error_summary": entry.get("error_summary"),
        },
      )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with st.expander("詳細 preview", expanded=False):
      for entry in entries[:5]:
        st.markdown(f"**{entry.get('run_id')}** — {entry.get('action_type')} / {entry.get('status')}")
        st.caption(f"input: {entry.get('input_summary') or '(none)'}")
        if entry.get("output_artifact_paths"):
          st.json(entry.get("output_artifact_paths"))
        if entry.get("error_summary"):
          st.warning(str(entry.get("error_summary")))
