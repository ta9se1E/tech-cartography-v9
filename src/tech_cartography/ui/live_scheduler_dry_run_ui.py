"""Scheduler dry-run UI (Phase 25S)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from tech_cartography.auth.basic_auth import is_login_required
from tech_cartography.runtime.user_context import resolve_user_context
from tech_cartography.services.live_scheduler_dry_run import run_live_scheduler_dry_run
from tech_cartography.services.live_watch_profile_manager import describe_watch_profile_status
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_warning_box
from tech_cartography.ui.login_ui import can_use_admin_features, get_auth_role, is_app_authenticated


def should_show_live_scheduler_dry_run_ui() -> bool:
  return is_login_required() and can_use_admin_features()


def render_live_scheduler_dry_run_section(
  *,
  project_root: Path | str,
  key_prefix: str = "live_scheduler_dry_run",
) -> None:
  if not should_show_live_scheduler_dry_run_ui():
    return

  profile_status = describe_watch_profile_status(project_root)
  with st.expander("Scheduler Dry-Run（計画のみ・実行なし）", expanded=False):
    st.markdown(
      render_caution_box(
        "Scheduler は起動しません。外部APIも呼びません。メール送信もしません。"
        " active Watch Profile を参照した計画 artifact のみ保存します。"
      ),
      unsafe_allow_html=True,
    )
    st.markdown(render_info_box(f"watch_profile_status: {profile_status.get('watch_profile_status')}"), unsafe_allow_html=True)
    if not profile_status.get("active_watch_profile_exists"):
      st.markdown(render_warning_box("active Watch Profile がありません。"), unsafe_allow_html=True)

    if st.button("Scheduler dry-run 計画を保存", key=f"{key_prefix}_run", type="secondary"):
      result = run_live_scheduler_dry_run(
        output_root=project_root,
        login_required=is_login_required(),
        is_authenticated=is_app_authenticated(),
        auth_role=get_auth_role(),
        user_context=resolve_user_context(),
      )
      st.session_state[f"{key_prefix}_last_result"] = result

    last_result: dict[str, Any] | None = st.session_state.get(f"{key_prefix}_last_result")
    if last_result:
      if last_result.get("ok"):
        st.success("dry-run 計画を保存しました。")
        payload = last_result.get("payload") or {}
        st.markdown("**planned_steps**")
        for step in payload.get("planned_steps") or []:
          st.markdown(f"- {step}")
        st.caption(f"active_watch_profile_path: {payload.get('active_watch_profile_path')}")
      else:
        st.warning(str(last_result.get("message") or last_result.get("error")))
      for warning in last_result.get("warnings") or []:
        st.markdown(render_warning_box(warning), unsafe_allow_html=True)
      saved = last_result.get("saved_paths") or {}
      for label in ("json", "markdown"):
        if saved.get(label):
          st.caption(f"artifact ({label}): {saved[label]}")
