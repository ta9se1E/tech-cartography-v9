"""Live Operation Console UI — manual weekly operation panel (Phase 25K)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from tech_cartography.auth.basic_auth import is_login_required
from tech_cartography.runtime.user_context import resolve_user_context
from tech_cartography.services.live_operation_status import (
  SAFETY_NOTICE,
  STEP_GUIDANCE,
  STEP_ORDER,
  build_and_save_operation_cycle_status,
  build_operation_cycle_status,
)
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_warning_box
from tech_cartography.ui.email_operation_status_ui import render_email_operation_status_panel
from tech_cartography.ui.login_ui import can_use_admin_features


def should_show_live_operation_console_ui() -> bool:
  return is_login_required() and can_use_admin_features()


def _step_label(step: str) -> str:
  labels = {
    "web_signal_pack": "Web Signal Pack",
    "digest_preview": "Digest Preview",
    "self_only_email": "Self-only Email",
    "watch_expansion_proposal": "Watch Expansion",
    "watch_profile_draft": "Watch Profile Draft",
    "next_cycle_search_plan": "Next Cycle Search Plan",
    "next_cycle_web_signal_pack": "Next Cycle Web Signal Pack",
  }
  return labels.get(step, step)


def render_live_operation_console_section(
  *,
  project_root: Path | str,
  key_prefix: str = "live_operation_console",
  save_on_load: bool = True,
) -> None:
  if not should_show_live_operation_console_ui():
    return

  with st.expander("Live Operation Console（手動週次運用）", expanded=True):
    from tech_cartography.ui.live_weekly_decision_cockpit_ui import render_live_weekly_decision_cockpit_section

    st.markdown("**今週の判断（概要）**")
    render_live_weekly_decision_cockpit_section(
      project_root=project_root,
      key_prefix=f"{key_prefix}_cockpit_summary",
      expanded=False,
    )
    st.markdown(
      render_caution_box(
        "Live 成果物の週次サイクル状態を<strong>一覧表示</strong>します。"
        " 自動実行・scheduler・一斉送信はありません。"
        " 各操作は下の既存 expander から手動で行ってください。"
      ),
      unsafe_allow_html=True,
    )

    if st.button("状態を更新して保存", key=f"{key_prefix}_refresh", type="secondary"):
      st.session_state.pop(f"{key_prefix}_status", None)

    status: dict[str, Any] | None = st.session_state.get(f"{key_prefix}_status")
    saved_paths: dict[str, str] | None = st.session_state.get(f"{key_prefix}_saved_paths")
    save_error: str | None = st.session_state.get(f"{key_prefix}_save_error")

    if status is None:
      if save_on_load:
        status, saved_paths, save_error = build_and_save_operation_cycle_status(
          project_root,
          user_context=resolve_user_context(),
        )
      else:
        status = build_operation_cycle_status(project_root, user_context=resolve_user_context())
        saved_paths = None
        save_error = None
      st.session_state[f"{key_prefix}_status"] = status
      st.session_state[f"{key_prefix}_saved_paths"] = saved_paths
      st.session_state[f"{key_prefix}_save_error"] = save_error

    st.markdown(f"**active storage root:** `{status.get('active_storage_root')}`")
    st.caption(f"LIVE_OUTPUTS_ROOT: {status.get('live_outputs_root_env')}")

    runtime = status.get("runtime_flags") or {}
    flag_rows = [
      {
        "flag": "DISABLE_EXTERNAL_API",
        "active": runtime.get("external_api_disabled"),
        "meaning": "Tavily 等の外部API",
      },
      {
        "flag": "DISABLE_EMAIL_SEND",
        "active": runtime.get("email_send_disabled"),
        "meaning": "メール送信",
      },
      {
        "flag": "DISABLE_SCHEDULER",
        "active": runtime.get("scheduler_disabled"),
        "meaning": "scheduler",
      },
    ]
    st.dataframe(flag_rows, width="stretch", hide_index=True)

    render_email_operation_status_panel(
      project_root=project_root,
      key_prefix=f"{key_prefix}_email_ops",
      expanded=False,
    )

    step_rows = []
    for index, step in enumerate(STEP_ORDER, start=1):
      info = (status.get("step_statuses") or {}).get(step) or {}
      step_rows.append(
        {
          "step": f"{index}. {_step_label(step)}",
          "status": info.get("status"),
          "count": info.get("count"),
          "latest_created_at": info.get("latest_created_at"),
          "latest_path": info.get("latest_path"),
        },
      )
    st.dataframe(step_rows, width="stretch", hide_index=True)

    st.markdown(f"**next recommended action:** {status.get('next_recommended_action')}")

    watch_profile = status.get("watch_profile") or {}
    st.markdown("**Watch Profile status**")
    st.caption(
      f"status={status.get('watch_profile_status')} | "
      f"active={status.get('active_watch_profile_theme') or '(none)'} | "
      f"draft={status.get('latest_draft_theme') or '(none)'}"
    )
    if status.get("active_watch_profile_path"):
      st.caption(f"active path: {status.get('active_watch_profile_path')}")
    if status.get("latest_draft_path"):
      st.caption(f"latest draft path: {status.get('latest_draft_path')}")
    st.caption(str(status.get("watch_profile_next_recommended_action") or ""))

    ext_api = status.get("external_api_collection") or {}
    st.markdown("**External API / Web Signal Collection**")
    st.caption(
      f"DISABLE_EXTERNAL_API={ext_api.get('disable_external_api')} | "
      f"ENABLE_MANUAL_WEB_SIGNAL_COLLECTION={ext_api.get('enable_manual_web_signal_collection')} | "
      f"tavily_configured={ext_api.get('tavily_secret_configured')}"
    )
    if status.get("latest_web_signal_collection_artifact"):
      st.caption(f"latest collection: {status.get('latest_web_signal_collection_artifact')}")
      st.caption(
        f"status={status.get('latest_web_signal_collection_status')} | "
        f"results={status.get('latest_web_signal_result_count')}"
      )
    if status.get("latest_web_signal_artifact_path"):
      st.caption(f"latest web signal artifact: {status.get('latest_web_signal_artifact_path')}")
    st.caption(f"digest uses web signals: {status.get('latest_digest_preview_uses_web_signals')}")
    st.caption(str(status.get("web_signal_collection_next_recommended_action") or ""))
    st.caption(str(status.get("web_signal_digest_next_recommended_action") or ""))
    st.markdown("**Evidence Gap / Strategic Watch Brief**")
    st.caption(
      f"evidence_gap={status.get('latest_evidence_gap_artifact_path') or '(none)'} | "
      f"count={status.get('latest_evidence_gap_count')}"
    )
    st.caption(
      f"strategic_brief={status.get('latest_strategic_watch_brief_path') or '(none)'} | "
      f"next_actions={status.get('latest_next_verification_action_count')}"
    )
    st.caption(str(status.get("evidence_gap_brief_next_recommended_action") or ""))
    st.markdown("**Weekly Decision Cockpit**")
    st.caption(f"cockpit={status.get('latest_weekly_decision_cockpit_path') or '(none)'}")
    st.caption(f"readiness={status.get('latest_readiness_level') or '(unknown)'}")
    st.caption(str(status.get("cockpit_next_recommended_action") or ""))

    from tech_cartography.ui.live_evidence_gap_ui import render_live_evidence_gap_section
    from tech_cartography.ui.live_strategic_watch_brief_ui import render_live_strategic_watch_brief_section
    from tech_cartography.ui.live_web_signal_review_ui import render_live_web_signal_review_section
    from tech_cartography.ui.live_web_signal_collection_ui import render_live_web_signal_collection_section
    from tech_cartography.ui.live_watch_profile_ui import render_live_watch_profile_section
    from tech_cartography.ui.live_scheduler_dry_run_ui import render_live_scheduler_dry_run_section

    render_live_web_signal_review_section(
      project_root=project_root,
      key_prefix=f"{key_prefix}_web_signal_review",
    )
    render_live_web_signal_collection_section(
      project_root=project_root,
      key_prefix=f"{key_prefix}_web_signal_collection",
    )
    render_live_watch_profile_section(project_root=project_root, key_prefix=f"{key_prefix}_watch_profile")
    render_live_evidence_gap_section(project_root=project_root, key_prefix=f"{key_prefix}_evidence_gap")
    render_live_strategic_watch_brief_section(project_root=project_root, key_prefix=f"{key_prefix}_strategic_brief")
    render_live_scheduler_dry_run_section(project_root=project_root, key_prefix=f"{key_prefix}_scheduler_dry_run")

    history_summary = status.get("run_history_summary") or {}
    st.markdown(
      f"**Run History:** visible={history_summary.get('total_visible_count', 0)}件 / "
      f"latest by you: {(history_summary.get('latest_by_current_user') or {}).get('action_type', '(none)')}"
    )
    latest_failed = history_summary.get("latest_failed_or_blocked")
    if latest_failed:
      st.warning(
        f"直近 failed/blocked: {latest_failed.get('action_type')} — "
        f"{latest_failed.get('error_summary') or latest_failed.get('status')}"
      )

    warnings = status.get("warnings") or []
    if warnings:
      for warning in warnings:
        st.markdown(render_warning_box(warning), unsafe_allow_html=True)

    st.markdown("**各機能への案内**")
    for step in STEP_ORDER:
      guidance = STEP_GUIDANCE.get(step)
      if guidance:
        st.markdown(f"- {guidance}")

    if saved_paths:
      st.caption(f"status saved: {saved_paths.get('json')}")
    elif save_error:
      st.warning(f"状態ファイルの保存に失敗: {save_error}")

    st.markdown(render_info_box(str(status.get("safety_notice") or SAFETY_NOTICE)), unsafe_allow_html=True)
