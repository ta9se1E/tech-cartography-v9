"""PatentScout AI entry point — v8 user-flow UI (default) or v7 via APP_UI_VERSION."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
  sys.path.insert(0, str(_SRC))

import streamlit as st

from tech_cartography.auth.basic_auth import is_login_required
from tech_cartography.ui.demo_safe_ui import render_app_sidebar
from tech_cartography.ui.easy_japanese_ui import inject_easy_ui_css
from tech_cartography.ui.login_ui import (
  build_app_user_from_auth_session,
  require_auth_login_gate,
)
from tech_cartography.ui.login_view import require_login
from tech_cartography.ui.streamlit_session import (
  STATE_CURRENT_USER,
  STATE_DISPLAY_MODE,
  STATE_PIPELINE_ROOT,
  STATE_SELECTED_RUN_ID,
  DISPLAY_MODE_OPTIONS,
  apply_pending_widget_state_updates,
  init_app_session_state,
)

APP_UI_VERSION_ENV = "APP_UI_VERSION"
DEFAULT_UI_VERSION = "v8"


def resolve_app_ui_version() -> str:
  value = str(os.environ.get(APP_UI_VERSION_ENV, DEFAULT_UI_VERSION) or DEFAULT_UI_VERSION).strip().lower()
  if value in {"v7", "v8"}:
    return value
  return DEFAULT_UI_VERSION


_ui_version = resolve_app_ui_version()
_page_title = "Tech Cartography v8" if _ui_version == "v8" else "Tech Cartography v7"

st.set_page_config(page_title=_page_title, layout="wide", initial_sidebar_state="expanded")
st.markdown(inject_easy_ui_css(), unsafe_allow_html=True)

if is_login_required():
  auth_session = require_auth_login_gate()
  user = build_app_user_from_auth_session(auth_session or {})
  st.session_state[STATE_CURRENT_USER] = user
else:
  user = require_login()
  if not user:
    raise SystemExit(0)

init_app_session_state(user)
apply_pending_widget_state_updates()


def _sidebar_button(label: str, **kwargs: Any) -> bool:
  try:
    return st.button(label, width="stretch", **kwargs)
  except TypeError:
    return st.button(label, use_container_width=True, **kwargs)


if _ui_version == "v8":
  from tech_cartography.ui.v8_user_flow_app import DEFAULT_PIPELINE_ROOT, PROJECT_ROOT, render_v8_user_flow_app

  with st.sidebar:
    render_app_sidebar(user, project_root=PROJECT_ROOT, sidebar_button=_sidebar_button)
    st.caption(f"UI: {_ui_version} (APP_UI_VERSION=v7 で v7 UI)")

  render_v8_user_flow_app(
    user,
    pipeline_root=st.session_state.get(STATE_PIPELINE_ROOT, str(DEFAULT_PIPELINE_ROOT)),
    run_id=st.session_state.get(STATE_SELECTED_RUN_ID, ""),
    display_mode=st.session_state.get(STATE_DISPLAY_MODE, DISPLAY_MODE_OPTIONS[0]),
  )
else:
  from tech_cartography.ui.v7_easy_app import DEFAULT_PIPELINE_ROOT, PROJECT_ROOT, render_tabbed_easy_app

  with st.sidebar:
    render_app_sidebar(user, project_root=PROJECT_ROOT, sidebar_button=_sidebar_button)
    st.caption(f"UI: {_ui_version}")

  render_tabbed_easy_app(
    user,
    pipeline_root=st.session_state.get(STATE_PIPELINE_ROOT, str(DEFAULT_PIPELINE_ROOT)),
    run_id=st.session_state.get(STATE_SELECTED_RUN_ID, ""),
    display_mode=st.session_state.get(STATE_DISPLAY_MODE, DISPLAY_MODE_OPTIONS[0]),
  )
