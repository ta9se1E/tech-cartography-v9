"""PatentScout AI v7 entry point — login-first tabbed Easy Japanese UI."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
  sys.path.insert(0, str(_SRC))

import streamlit as st

from tech_cartography.orchestration.latest_outputs import read_latest_run_pointer
from tech_cartography.ui.easy_japanese_ui import inject_easy_ui_css, render_warning_box
from tech_cartography.ui.login_view import logout_user, render_logged_in_header, require_login
from tech_cartography.ui.streamlit_session import (
  DISPLAY_MODE_OPTIONS,
  STATE_CURRENT_USER,
  STATE_DISPLAY_MODE,
  STATE_MANIFEST_PATH,
  STATE_PENDING_SELECTED_RUN_ID,
  STATE_PIPELINE_ROOT,
  STATE_SELECTED_RUN_ID,
  WIDGET_DISPLAY_MODE,
  WIDGET_PIPELINE_ROOT,
  WIDGET_SELECTED_RUN_ID,
  apply_pending_widget_state_updates,
  init_app_session_state,
  sync_internal_from_widget_values,
)
from tech_cartography.ui.v7_easy_app import DEFAULT_PIPELINE_ROOT, render_tabbed_easy_app
from tech_cartography.users.user_store import set_last_run_id

st.set_page_config(page_title="Tech Cartography v7", layout="wide", initial_sidebar_state="expanded")
st.markdown(inject_easy_ui_css(), unsafe_allow_html=True)

user = require_login()
if not user:
  raise SystemExit(0)

init_app_session_state(user)
apply_pending_widget_state_updates()

with st.sidebar:
  st.header("ユーザー")
  render_logged_in_header(user)
  if user.get("company_name"):
    st.caption(f"会社: {user['company_name']}")
  if st.button("ログアウト", use_container_width=True, key="logout_button"):
    logout_user()
    st.rerun()

  st.divider()
  st.header("実行結果")

  pipeline_root_input = st.text_input(
    "実行結果フォルダ",
    value=st.session_state.get(STATE_PIPELINE_ROOT, str(DEFAULT_PIPELINE_ROOT)),
    key=WIDGET_PIPELINE_ROOT,
  )

  default_run = user.get("last_run_id") or st.session_state.get(STATE_SELECTED_RUN_ID, "")
  run_id_input = st.text_input(
    "run_id",
    value=st.session_state.get(STATE_SELECTED_RUN_ID, default_run),
    key=WIDGET_SELECTED_RUN_ID,
  )

  if st.button("latest_run を読み込む", use_container_width=True, key="load_latest_run_button"):
    pointer = read_latest_run_pointer(pipeline_root_input)
    if pointer and pointer.get("run_id"):
      run_id = str(pointer["run_id"])
      st.session_state[STATE_PENDING_SELECTED_RUN_ID] = run_id
      st.session_state[STATE_MANIFEST_PATH] = pointer.get("manifest_path", "")
      updated_user = set_last_run_id(user["user_id"], run_id)
      st.session_state[STATE_CURRENT_USER] = updated_user
      st.success(f"最新 run: {run_id}")
      st.rerun()
    else:
      st.warning("latest_run.json が見つかりません。")

  current_mode = st.session_state.get(STATE_DISPLAY_MODE, DISPLAY_MODE_OPTIONS[0])
  mode_index = DISPLAY_MODE_OPTIONS.index(current_mode) if current_mode in DISPLAY_MODE_OPTIONS else 0
  display_mode_input = st.radio(
    "表示モード",
    list(DISPLAY_MODE_OPTIONS),
    index=mode_index,
    key=WIDGET_DISPLAY_MODE,
  )

  internal_updates = sync_internal_from_widget_values(
    pipeline_root=pipeline_root_input,
    selected_run_id=run_id_input,
    display_mode=display_mode_input,
  )
  for key, value in internal_updates.items():
    st.session_state[key] = value

  st.markdown(
    render_warning_box(
      "BigQuery・OpenAlex・全文取得は有料/外部実行の可能性があります。"
      "この画面からは自動実行しません。"
    ),
    unsafe_allow_html=True,
  )

render_tabbed_easy_app(
  user,
  pipeline_root=st.session_state.get(STATE_PIPELINE_ROOT, str(DEFAULT_PIPELINE_ROOT)),
  run_id=st.session_state.get(STATE_SELECTED_RUN_ID, ""),
  display_mode=st.session_state.get(STATE_DISPLAY_MODE, DISPLAY_MODE_OPTIONS[0]),
)
