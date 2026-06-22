"""PatentScout AI v7 entry point — login-first tabbed Easy Japanese UI."""

from __future__ import annotations

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
from tech_cartography.ui.v7_easy_app import DEFAULT_PIPELINE_ROOT, PROJECT_ROOT, render_tabbed_easy_app

st.set_page_config(page_title="Tech Cartography v7", layout="wide", initial_sidebar_state="expanded")
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


with st.sidebar:
  render_app_sidebar(user, project_root=PROJECT_ROOT, sidebar_button=_sidebar_button)

render_tabbed_easy_app(
  user,
  pipeline_root=st.session_state.get(STATE_PIPELINE_ROOT, str(DEFAULT_PIPELINE_ROOT)),
  run_id=st.session_state.get(STATE_SELECTED_RUN_ID, ""),
  display_mode=st.session_state.get(STATE_DISPLAY_MODE, DISPLAY_MODE_OPTIONS[0]),
)
