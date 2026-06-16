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
from tech_cartography.ui.v7_easy_app import DEFAULT_PIPELINE_ROOT, render_tabbed_easy_app

st.set_page_config(page_title="Tech Cartography v7", layout="wide", initial_sidebar_state="expanded")
st.markdown(inject_easy_ui_css(), unsafe_allow_html=True)

user = require_login()
if not user:
  raise SystemExit(0)

with st.sidebar:
  st.header("ユーザー")
  render_logged_in_header(user)
  if user.get("company_name"):
    st.caption(f"会社: {user['company_name']}")
  if st.button("ログアウト", use_container_width=True):
    logout_user()
    st.rerun()

  st.divider()
  st.header("実行結果")
  pipeline_root = st.text_input("実行結果フォルダ", value=str(DEFAULT_PIPELINE_ROOT), key="easy_pipeline_root")
  st.session_state["easy_pipeline_root"] = pipeline_root

  default_run = user.get("last_run_id") or ""
  run_id = st.text_input("run_id", value=st.session_state.get("easy_run_id", default_run), key="easy_run_id_input")
  if run_id:
    st.session_state["easy_run_id"] = run_id

  if st.button("latest_run を読み込む", use_container_width=True):
    pointer = read_latest_run_pointer(pipeline_root)
    if pointer and pointer.get("run_id"):
      st.session_state["easy_run_id"] = pointer["run_id"]
      st.session_state["easy_manifest_path"] = pointer.get("manifest_path", "")
      st.success(f"最新 run: {pointer['run_id']}")
      st.rerun()
    else:
      st.warning("latest_run.json が見つかりません。")

  display_mode = st.radio("表示モード", ["かんたん表示", "詳細表示"], index=0, key="easy_display_mode")
  st.markdown(
    render_warning_box(
      "BigQuery・OpenAlex・全文取得は有料/外部実行の可能性があります。"
      "この画面からは自動実行しません。"
    ),
    unsafe_allow_html=True,
  )

render_tabbed_easy_app(
  user,
  pipeline_root=pipeline_root,
  run_id=st.session_state.get("easy_run_id", ""),
  display_mode=display_mode,
)
