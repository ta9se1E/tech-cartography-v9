"""User and watch profile settings tab."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from tech_cartography.ui.developer_mode_visibility import (
  developer_mode_hidden_notice,
  is_show_developer_mode_enabled,
)
from tech_cartography.ui.easy_japanese_ui import (
  render_caution_box,
  render_info_box,
  render_ok_box,
  render_watch_profile_card,
)
from tech_cartography.ui.japanese_labels import (
  explain_watch_profile,
  translate_user_setting,
  translate_weekly_email_status,
)
from tech_cartography.ui.streamlit_session import (
  STATE_CURRENT_USER,
  STATE_WEEKLY_EMAIL_ENABLED,
  WIDGET_SETTINGS_COMPANY_NAME,
  WIDGET_SETTINGS_DISPLAY_NAME,
  WIDGET_EMAIL_DESTINATION_DISPLAY,
  WIDGET_WATCH_THEME_DISPLAY,
  WIDGET_WEEKLY_DAY,
  WIDGET_WEEKLY_EMAIL,
  WIDGET_WEEKLY_TIME,
)
from tech_cartography.users.user_store import set_last_run_id, set_weekly_email_enabled, update_user_profile
from tech_cartography.users.watch_profile_store import (
  get_active_watch_profile,
  update_watch_profile,
)

WEEKDAY_OPTIONS = {
  "monday": "月曜日",
  "tuesday": "火曜日",
  "wednesday": "水曜日",
  "thursday": "木曜日",
  "friday": "金曜日",
}


def render_user_settings_tab(
  user: dict[str, Any],
  *,
  current_run_id: str | None = None,
  developer_mode: bool = False,
) -> None:
  from tech_cartography.ui.login_ui import can_use_production_features, render_production_access_blocked

  st.markdown(render_info_box(explain_watch_profile()), unsafe_allow_html=True)
  watch = get_active_watch_profile(user["user_id"])
  st.markdown(render_watch_profile_card(watch), unsafe_allow_html=True)

  if not can_use_production_features():
    render_production_access_blocked("Watch Profile / 週次メール設定の更新")
    st.divider()
    if not is_show_developer_mode_enabled():
      st.caption(developer_mode_hidden_notice())
    return

  with st.expander("ユーザープロファイル編集", expanded=False):
    display_name = st.text_input(
      "表示名",
      value=user.get("display_name") or "",
      key=WIDGET_SETTINGS_DISPLAY_NAME,
    )
    company_name = st.text_input(
      "会社名",
      value=user.get("company_name") or "",
      key=WIDGET_SETTINGS_COMPANY_NAME,
    )
    if st.button("プロファイルを保存", key="save_user_profile"):
      updated = update_user_profile(
        user["user_id"],
        {"display_name": display_name.strip() or None, "company_name": company_name.strip() or None},
      )
      st.session_state[STATE_CURRENT_USER] = updated
      st.success("プロファイルを保存しました。")
      st.rerun()

  st.subheader("週次メール設定")
  st.markdown(
    render_caution_box(
      "現在は週次メール設定の保存のみです。メール送信処理はまだ実装していません。"
    ),
    unsafe_allow_html=True,
  )

  weekly_enabled = st.checkbox(
    translate_user_setting("weekly_email_enabled"),
    value=bool(user.get("weekly_email_enabled")),
    key=WIDGET_WEEKLY_EMAIL,
  )
  st.text_input(
    translate_user_setting("email_destination"),
    value=user.get("email", ""),
    disabled=True,
    key=WIDGET_EMAIL_DESTINATION_DISPLAY,
  )
  st.text_input(
    translate_user_setting("watch_theme"),
    value=watch.get("theme", ""),
    disabled=True,
    key=WIDGET_WATCH_THEME_DISPLAY,
  )
  day_options = list(WEEKDAY_OPTIONS.keys())
  day_default = str(user.get("weekly_email_day", "monday"))
  day_key = st.selectbox(
    translate_user_setting("weekly_email_day"),
    options=day_options,
    format_func=lambda k: WEEKDAY_OPTIONS[k],
    index=day_options.index(day_default) if day_default in day_options else 0,
    key=WIDGET_WEEKLY_DAY,
  )
  email_time = st.text_input(
    translate_user_setting("weekly_email_time"),
    value=user.get("weekly_email_time", "09:00"),
    key=WIDGET_WEEKLY_TIME,
  )

  if st.button("週次メール設定を保存", key="save_weekly_email"):
    set_weekly_email_enabled(user["user_id"], weekly_enabled)
    update_user_profile(
      user["user_id"],
      {"weekly_email_day": day_key, "weekly_email_time": email_time},
    )
    update_watch_profile(
      user["user_id"],
      watch["watch_profile_id"],
      {
        "weekly_email_enabled": weekly_enabled,
        "weekly_email_day": day_key,
        "weekly_email_time": email_time,
      },
    )
    refreshed = dict(st.session_state.get(STATE_CURRENT_USER) or user)
    refreshed["weekly_email_enabled"] = weekly_enabled
    refreshed["weekly_email_day"] = day_key
    refreshed["weekly_email_time"] = email_time
    st.session_state[STATE_CURRENT_USER] = refreshed
    st.session_state[STATE_WEEKLY_EMAIL_ENABLED] = weekly_enabled
    st.markdown(render_ok_box(translate_weekly_email_status(weekly_enabled)), unsafe_allow_html=True)

  if developer_mode and is_show_developer_mode_enabled() and current_run_id:
    st.caption(f"現在表示中の run_id: {current_run_id}")
    if st.button("この run_id をユーザーに保存", key="save_last_run"):
      updated = set_last_run_id(user["user_id"], current_run_id)
      st.session_state[STATE_CURRENT_USER] = updated
      update_watch_profile(
        user["user_id"],
        watch["watch_profile_id"],
        {"last_run_id": current_run_id},
      )
      st.success(f"last_run_id を {current_run_id} に保存しました。")

  if developer_mode and is_show_developer_mode_enabled():
    from tech_cartography.ui.report_tab_ui import render_cloud_run_ready_checklist

    st.divider()
    with st.expander("Cloud Run 前チェックリスト", expanded=False):
      render_cloud_run_ready_checklist(Path(__file__).resolve().parents[3])
  elif not is_show_developer_mode_enabled():
    st.divider()
    st.caption(developer_mode_hidden_notice())

  from tech_cartography.auth.basic_auth import is_login_required
  from tech_cartography.ui.api_secret_status_ui import render_api_secret_status_expander
  from tech_cartography.ui.login_ui import can_use_admin_features

  if is_login_required() and can_use_admin_features():
    st.divider()
    render_api_secret_status_expander(key="settings_api_secret_status")
    from tech_cartography.ui.live_artifact_storage_ui import render_live_artifact_storage_expander

    render_live_artifact_storage_expander(
      project_root=Path(__file__).resolve().parents[3],
      key="settings_live_artifact_storage",
    )
    from tech_cartography.ui.live_watch_expansion_ui import render_watch_profile_draft_reports_section

    render_watch_profile_draft_reports_section(
      project_root=Path(__file__).resolve().parents[3],
      key_prefix="settings_watch_profile_draft",
    )
    from tech_cartography.ui.live_beta_release_pack_ui import render_live_beta_release_pack_section

    render_live_beta_release_pack_section(
      project_root=Path(__file__).resolve().parents[3],
      key_prefix="settings_live_beta_release_pack",
      expanded=False,
    )
    from tech_cartography.ui.live_run_history_ui import render_run_history_section

    render_run_history_section(
      project_root=Path(__file__).resolve().parents[3],
      key_prefix="settings_live_run_history",
      expanded=False,
    )

  if st.button("セッションをリセット", key="reset_session"):
    preserved_user = st.session_state.get(STATE_CURRENT_USER)
    for key in list(st.session_state.keys()):
      if key != STATE_CURRENT_USER:
        del st.session_state[key]
    if preserved_user:
      st.session_state[STATE_CURRENT_USER] = preserved_user
    st.info("セッションをリセットしました（ログインは維持されます）。")
