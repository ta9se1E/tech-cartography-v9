"""Live Watch Profile management UI (Phase 25S)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from tech_cartography.auth.basic_auth import is_login_required
from tech_cartography.runtime.watch_profile_management_config import (
  get_activation_confirmation_text,
  get_archive_confirmation_text,
  get_rollback_confirmation_text,
  is_watch_profile_management_enabled,
)
from tech_cartography.runtime.watch_profile_schema import diff_watch_profiles
from tech_cartography.runtime.user_context import resolve_user_context
from tech_cartography.services.live_watch_profile_manager import (
  archive_active_watch_profile,
  create_watch_profile_draft,
  describe_watch_profile_status,
  get_active_watch_profile,
  get_latest_watch_profile_draft,
  import_next_cycle_plan_to_draft,
  promote_draft_to_active,
  rollback_to_previous_watch_profile,
)
from tech_cartography.services.live_next_cycle_search_plan import (
  find_latest_next_cycle_search_plan_path,
  load_next_cycle_search_plan,
)
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_warning_box
from tech_cartography.ui.login_ui import can_use_admin_features, get_auth_role, is_app_authenticated


def should_show_live_watch_profile_ui() -> bool:
  return is_login_required() and can_use_admin_features()


def _parse_csv_field(value: str) -> list[str]:
  return [part.strip() for part in str(value or "").replace("\n", ",").split(",") if part.strip()]


def render_live_watch_profile_section(
  *,
  project_root: Path | str,
  key_prefix: str = "live_watch_profile",
) -> None:
  if not should_show_live_watch_profile_ui():
    return

  status = describe_watch_profile_status(project_root)
  active, active_path = get_active_watch_profile(project_root)
  draft, draft_path = get_latest_watch_profile_draft(project_root)
  user_context = resolve_user_context()
  management_enabled = is_watch_profile_management_enabled()
  is_admin = get_auth_role() == "admin" or bool(user_context.get("is_admin"))

  with st.expander("Watch Profile Management（監視条件台帳）", expanded=False):
    st.markdown(
      render_caution_box(
        "これは監視条件の保存であり、外部検索は実行しません。"
        " active化してもSchedulerは起動しません。メール送信は行いません。"
        " 監視範囲の拡張は人間の承認後に反映されます。"
      ),
      unsafe_allow_html=True,
    )
    st.markdown(render_info_box(f"watch_profile_status: {status.get('watch_profile_status')}"), unsafe_allow_html=True)
    st.caption(str(status.get("next_recommended_action") or ""))

    if active:
      st.markdown(f"**active theme:** {active.get('theme_name')}")
      st.caption(f"active path: {active_path}")
    else:
      st.markdown(render_warning_box("active Watch Profile がありません。"), unsafe_allow_html=True)

    if draft:
      st.markdown(f"**latest draft theme:** {draft.get('theme_name')}")
      st.caption(f"draft path: {draft_path}")
      if active:
        st.markdown("**diff (draft vs active)**")
        st.json(diff_watch_profiles(draft, active))

    if not management_enabled:
      st.markdown(
        render_warning_box("編集は無効です（ENABLE_WATCH_PROFILE_MANAGEMENT=false）。状態表示のみ。"),
        unsafe_allow_html=True,
      )
      return

    if not is_admin:
      st.markdown(render_warning_box("member は閲覧のみです。active化は admin のみ。"), unsafe_allow_html=True)
      return

    with st.form(f"{key_prefix}_draft_form"):
      theme_name = st.text_input("theme_name", value=str((draft or active or {}).get("theme_name") or ""))
      theme_description = st.text_area(
        "theme_description",
        value=str((draft or {}).get("theme_description") or ""),
      )
      search_keywords = st.text_area(
        "search_keywords（カンマ区切り）",
        value=", ".join((draft or active or {}).get("search_keywords") or []),
      )
      search_queries = st.text_area(
        "search_queries（カンマ区切り）",
        value=", ".join((draft or active or {}).get("search_queries") or []),
      )
      exclude_keywords = st.text_input(
        "exclude_keywords",
        value=", ".join((draft or {}).get("exclude_keywords") or []),
      )
      target_assignees = st.text_input(
        "target_assignees",
        value=", ".join((draft or {}).get("target_assignees") or []),
      )
      target_jurisdictions = st.text_input(
        "target_jurisdictions",
        value=", ".join((draft or {}).get("target_jurisdictions") or []),
      )
      weekly_priority = st.selectbox(
        "weekly_priority",
        options=["standard", "high", "low"],
        index=["standard", "high", "low"].index(str((draft or active or {}).get("weekly_priority") or "standard")),
      )
      notes = st.text_area("notes", value=str((draft or {}).get("notes") or ""))
      save_draft = st.form_submit_button("Watch Profile draft を保存")

    if save_draft:
      result = create_watch_profile_draft(
        profile_input={
          "theme_name": theme_name,
          "theme_description": theme_description,
          "search_keywords": _parse_csv_field(search_keywords),
          "search_queries": _parse_csv_field(search_queries),
          "exclude_keywords": _parse_csv_field(exclude_keywords),
          "target_assignees": _parse_csv_field(target_assignees),
          "target_jurisdictions": _parse_csv_field(target_jurisdictions),
          "weekly_priority": weekly_priority,
          "notes": notes,
        },
        output_root=project_root,
        login_required=is_login_required(),
        is_authenticated=is_app_authenticated(),
        auth_role=get_auth_role(),
        user_context=user_context,
      )
      st.session_state[f"{key_prefix}_last_result"] = result

    activate_confirm = st.text_input(
      f"active化確認文（{get_activation_confirmation_text()}）",
      key=f"{key_prefix}_activate_confirm",
    )
    if st.button("Watch Profile を active 化", key=f"{key_prefix}_activate", disabled=not draft_path):
      if draft_path:
        result = promote_draft_to_active(
          draft_path=draft_path,
          confirm_text=activate_confirm,
          output_root=project_root,
          login_required=is_login_required(),
          is_authenticated=is_app_authenticated(),
          auth_role=get_auth_role(),
          user_context=user_context,
        )
        st.session_state[f"{key_prefix}_last_result"] = result

    archive_confirm = st.text_input(
      f"archive確認文（{get_archive_confirmation_text()}）",
      key=f"{key_prefix}_archive_confirm",
    )
    if st.button("active Watch Profile を archive", key=f"{key_prefix}_archive"):
      result = archive_active_watch_profile(
        confirm_text=archive_confirm,
        output_root=project_root,
        login_required=is_login_required(),
        is_authenticated=is_app_authenticated(),
        auth_role=get_auth_role(),
        user_context=user_context,
      )
      st.session_state[f"{key_prefix}_last_result"] = result

    rollback_confirm = st.text_input(
      f"rollback確認文（{get_rollback_confirmation_text()}）",
      key=f"{key_prefix}_rollback_confirm",
    )
    if st.button("previous Watch Profile へ rollback", key=f"{key_prefix}_rollback"):
      result = rollback_to_previous_watch_profile(
        confirm_text=rollback_confirm,
        output_root=project_root,
        login_required=is_login_required(),
        is_authenticated=is_app_authenticated(),
        auth_role=get_auth_role(),
        user_context=user_context,
      )
      st.session_state[f"{key_prefix}_last_result"] = result

    plan_path = find_latest_next_cycle_search_plan_path(project_root)
    if plan_path and st.button("Next Cycle Plan を draft 候補として取り込む", key=f"{key_prefix}_import_plan"):
      plan = load_next_cycle_search_plan(plan_path)
      if plan:
        result = import_next_cycle_plan_to_draft(
          plan=plan,
          plan_path=str(plan_path),
          output_root=project_root,
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
        st.warning(str(last_result.get("message") or last_result.get("error")))
      saved = last_result.get("saved_paths") or {}
      for label in ("json", "markdown"):
        if saved.get(label):
          st.caption(f"artifact ({label}): {saved[label]}")
      st.caption("Run History に action_type が記録されます。")
