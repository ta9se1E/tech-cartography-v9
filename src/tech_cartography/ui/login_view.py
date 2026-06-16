"""Local email-based login screen (development only, no password)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from tech_cartography.ui.easy_japanese_ui import (
  inject_easy_ui_css,
  render_info_box,
  render_login_notice,
  render_warning_box,
)
from tech_cartography.ui.japanese_labels import explain_login_mode
from tech_cartography.users.user_profile import validate_email
from tech_cartography.users.user_store import get_or_create_user
from tech_cartography.users.watch_profile_store import ensure_default_watch_profile

from tech_cartography.ui.streamlit_session import STATE_CURRENT_USER

SESSION_USER_KEY = STATE_CURRENT_USER


def process_login_submission(
  email: str,
  display_name: str | None = None,
  company_name: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
  """Pure login handler for tests. Returns (user_dict, error_message)."""
  if not validate_email(email):
    return None, "メールアドレスの形式が正しくありません。"
  user = get_or_create_user(email, display_name=display_name, company_name=company_name)
  ensure_default_watch_profile(user["user_id"])
  return user, None


def get_current_user() -> dict[str, Any] | None:
  user = st.session_state.get(SESSION_USER_KEY)
  return dict(user) if isinstance(user, dict) else None


def logout_user() -> None:
  if SESSION_USER_KEY in st.session_state:
    del st.session_state[SESSION_USER_KEY]


def render_logged_in_header(user: dict[str, Any]) -> None:
  name = user.get("display_name") or user.get("email", "")
  st.markdown(
    f'<div style="font-size:1rem;color:#475569;">'
    f"ログイン中: <b>{name}</b> / {user.get('email', '')}"
    f"</div>",
    unsafe_allow_html=True,
  )


def render_login_screen() -> dict[str, Any] | None:
  st.markdown(inject_easy_ui_css(), unsafe_allow_html=True)
  st.markdown('<div class="tc-main-title">Tech Cartography v7</div>', unsafe_allow_html=True)
  st.markdown('<div class="tc-main-subtitle">かんたん技術地図 — メールアドレスでログイン</div>', unsafe_allow_html=True)
  st.markdown(render_login_notice(), unsafe_allow_html=True)
  st.markdown(render_info_box(explain_login_mode()), unsafe_allow_html=True)

  with st.form("login_form", clear_on_submit=False):
    email = st.text_input("メールアドレス", placeholder="example@company.co.jp")
    display_name = st.text_input("表示名（任意）", placeholder="山田 太郎")
    company_name = st.text_input("会社名（任意）", placeholder="株式会社サンプル")
    submitted = st.form_submit_button("ログイン", type="primary", use_container_width=True)

  if submitted:
    user, error = process_login_submission(email, display_name=display_name, company_name=company_name)
    if error:
      st.markdown(render_warning_box(error), unsafe_allow_html=True)
      return None
    st.session_state[SESSION_USER_KEY] = user
    st.rerun()

  return None


def require_login() -> dict[str, Any] | None:
  user = get_current_user()
  if user:
    return user
  render_login_screen()
  st.stop()
  return None
