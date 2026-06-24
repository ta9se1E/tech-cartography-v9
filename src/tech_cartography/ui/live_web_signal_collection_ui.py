"""Controlled manual Web Signal collection UI (Phase 25T)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from tech_cartography.auth.basic_auth import is_login_required
from tech_cartography.runtime.cloud_run_config import is_external_api_disabled
from tech_cartography.runtime.external_api_operation_config import (
  describe_external_api_collection_runtime,
  get_web_signal_collection_confirmation_text,
  get_web_signal_max_queries,
  is_manual_web_signal_collection_enabled,
  skipped_reason_message,
)
from tech_cartography.runtime.user_context import resolve_user_context
from tech_cartography.services.live_watch_profile_manager import get_active_watch_profile
from tech_cartography.services.live_web_signal_collector import collect_live_web_signals
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_warning_box
from tech_cartography.ui.login_ui import can_use_admin_features, get_auth_role, is_app_authenticated


def should_show_live_web_signal_collection_ui() -> bool:
  return is_login_required() and can_use_admin_features()


def _planned_queries(profile: dict[str, Any] | None) -> list[str]:
  if not profile:
    return []
  queries = [str(q).strip() for q in (profile.get("search_queries") or []) if str(q).strip()]
  if not queries:
    queries = [str(k).strip() for k in (profile.get("search_keywords") or []) if str(k).strip()]
  return queries[: get_web_signal_max_queries()]


def render_live_web_signal_collection_section(
  *,
  project_root: Path | str,
  key_prefix: str = "live_web_signal_collection",
) -> None:
  if not should_show_live_web_signal_collection_ui():
    return

  runtime = describe_external_api_collection_runtime()
  active, active_path = get_active_watch_profile(project_root)
  planned = _planned_queries(active)
  expected_confirm = get_web_signal_collection_confirmation_text()
  user_context = resolve_user_context()

  with st.expander("Web Signal 手動収集（Watch Profile 連動）", expanded=False):
    st.markdown(
      render_caution_box(
        "候補情報であり、確定事実ではありません。"
        " 法的判断・FTO・侵害・有効性判断ではありません。"
        " メール送信・Scheduler起動は行いません。"
      ),
      unsafe_allow_html=True,
    )

    if not is_manual_web_signal_collection_enabled():
      st.markdown(
        render_warning_box("手動収集は無効です（ENABLE_MANUAL_WEB_SIGNAL_COLLECTION=false）。"),
        unsafe_allow_html=True,
      )
    if is_external_api_disabled():
      st.markdown(
        render_warning_box("外部API停止中（DISABLE_EXTERNAL_API=true）。"),
        unsafe_allow_html=True,
      )
    if not runtime.get("tavily_secret_configured"):
      st.markdown(render_warning_box("Tavily search key is not configured."), unsafe_allow_html=True)

    if active:
      st.markdown(f"**active theme:** {active.get('theme_name')}")
      st.caption(f"active path: {active_path}")
    else:
      st.markdown(render_warning_box("active Watch Profile がありません。"), unsafe_allow_html=True)

    st.markdown("**実行予定 query（上限内）**")
    if planned:
      for query in planned:
        st.markdown(f"- {query}")
    else:
      st.caption("(query なし)")

    confirm = st.text_input(
      f"確認文（{expected_confirm}）",
      key=f"{key_prefix}_confirm",
    )
    confirm_ok = str(confirm or "") == expected_confirm
    can_run = (
      is_manual_web_signal_collection_enabled()
      and not is_external_api_disabled()
      and bool(active)
      and bool(planned)
      and confirm_ok
      and bool(runtime.get("tavily_secret_configured"))
    )

    if st.button(
      "Web Signal候補を手動収集",
      key=f"{key_prefix}_collect",
      disabled=not can_run,
      type="secondary",
    ):
      result = collect_live_web_signals(
        output_root=project_root,
        confirm_text=confirm,
        login_required=is_login_required(),
        is_authenticated=is_app_authenticated(),
        auth_role=get_auth_role(),
        user_context=user_context,
      )
      st.session_state[f"{key_prefix}_last_result"] = result

    last_result: dict[str, Any] | None = st.session_state.get(f"{key_prefix}_last_result")
    if last_result:
      if last_result.get("ok"):
        st.success(str(last_result.get("message") or "完了"))
      else:
        st.warning(str(last_result.get("message") or skipped_reason_message(last_result.get("skipped_reason"))))
      st.caption(f"result_count: {last_result.get('result_count', 0)}")
      saved = last_result.get("saved_paths") or {}
      for label in ("json", "markdown"):
        if saved.get(label):
          st.caption(f"artifact ({label}): {saved[label]}")
      st.caption("Run History に live_web_signal_collection が記録されます。")

    st.markdown(render_info_box("Web Signalは候補情報です。原典確認が必要です。"), unsafe_allow_html=True)
