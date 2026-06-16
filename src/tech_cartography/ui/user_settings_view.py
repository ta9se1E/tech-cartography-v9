"""User and watch profile settings tab."""

from __future__ import annotations

from typing import Any

import streamlit as st

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


def render_user_settings_tab(user: dict[str, Any], *, current_run_id: str | None = None) -> None:
  st.markdown(render_info_box(explain_watch_profile()), unsafe_allow_html=True)
  watch = get_active_watch_profile(user["user_id"])
  st.markdown(render_watch_profile_card(watch), unsafe_allow_html=True)

  with st.expander("ユーザープロファイル編集", expanded=False):
    display_name = st.text_input("表示名", value=user.get("display_name") or "", key="settings_display_name")
    company_name = st.text_input("会社名", value=user.get("company_name") or "", key="settings_company_name")
    if st.button("プロファイルを保存", key="save_user_profile"):
      updated = update_user_profile(
        user["user_id"],
        {"display_name": display_name.strip() or None, "company_name": company_name.strip() or None},
      )
      st.session_state["current_user"] = updated
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
    key="weekly_email_checkbox",
  )
  st.text_input(translate_user_setting("email_destination"), value=user.get("email", ""), disabled=True)
  st.text_input(translate_user_setting("watch_theme"), value=watch.get("theme", ""), disabled=True)
  day_key = st.selectbox(
    translate_user_setting("weekly_email_day"),
    options=list(WEEKDAY_OPTIONS.keys()),
    format_func=lambda k: WEEKDAY_OPTIONS[k],
    index=list(WEEKDAY_OPTIONS.keys()).index(str(user.get("weekly_email_day", "monday"))),
  )
  email_time = st.text_input(translate_user_setting("weekly_email_time"), value=user.get("weekly_email_time", "09:00"))

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
    refreshed = dict(st.session_state.get("current_user") or user)
    refreshed["weekly_email_enabled"] = weekly_enabled
    refreshed["weekly_email_day"] = day_key
    refreshed["weekly_email_time"] = email_time
    st.session_state["current_user"] = refreshed
    st.markdown(render_ok_box(translate_weekly_email_status(weekly_enabled)), unsafe_allow_html=True)

  if current_run_id:
    st.caption(f"現在表示中の run_id: {current_run_id}")
    if st.button("この run_id をユーザーに保存", key="save_last_run"):
      updated = set_last_run_id(user["user_id"], current_run_id)
      st.session_state["current_user"] = updated
      update_watch_profile(
        user["user_id"],
        watch["watch_profile_id"],
        {"last_run_id": current_run_id},
      )
      st.success(f"last_run_id を {current_run_id} に保存しました。")

  if st.button("セッションをリセット", key="reset_session"):
    for key in list(st.session_state.keys()):
      if key != "current_user":
        del st.session_state[key]
    st.info("セッションをリセットしました（ログインは維持されます）。")
