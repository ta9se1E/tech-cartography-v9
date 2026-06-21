"""Streamlit basic login gate UI and production access guards (Phase 25A)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from tech_cartography.auth.basic_auth import (
  AuthUser,
  authenticate,
  is_login_required,
  users_configured,
)
from tech_cartography.ui.easy_japanese_ui import inject_easy_ui_css, render_info_box, render_warning_box
from tech_cartography.ui.login_view import get_current_user

STATE_AUTH_AUTHENTICATED = "tc_basic_auth_authenticated"
STATE_AUTH_USERNAME = "tc_basic_auth_username"
STATE_AUTH_ROLE = "tc_basic_auth_role"
STATE_AUTH_DISPLAY_NAME = "tc_basic_auth_display_name"


def get_basic_auth_session() -> dict[str, Any] | None:
  if not st.session_state.get(STATE_AUTH_AUTHENTICATED):
    return None
  return {
    "authenticated": True,
    "username": st.session_state.get(STATE_AUTH_USERNAME, ""),
    "role": st.session_state.get(STATE_AUTH_ROLE, "member"),
    "display_name": st.session_state.get(STATE_AUTH_DISPLAY_NAME, ""),
  }


def set_basic_auth_session(auth_user: AuthUser) -> None:
  st.session_state[STATE_AUTH_AUTHENTICATED] = True
  st.session_state[STATE_AUTH_USERNAME] = auth_user.username
  st.session_state[STATE_AUTH_ROLE] = auth_user.role
  st.session_state[STATE_AUTH_DISPLAY_NAME] = auth_user.display_name


def clear_basic_auth_session() -> None:
  for key in (
    STATE_AUTH_AUTHENTICATED,
    STATE_AUTH_USERNAME,
    STATE_AUTH_ROLE,
    STATE_AUTH_DISPLAY_NAME,
  ):
    if key in st.session_state:
      del st.session_state[key]


def is_basic_authenticated() -> bool:
  return bool(st.session_state.get(STATE_AUTH_AUTHENTICATED))


def get_auth_role() -> str:
  return str(st.session_state.get(STATE_AUTH_ROLE) or "member")


def has_app_session_access() -> bool:
  if is_login_required():
    return is_basic_authenticated()
  return get_current_user() is not None


def can_use_production_features() -> bool:
  from tech_cartography.auth.basic_auth import production_features_allowed

  return production_features_allowed(
    login_required=is_login_required(),
    basic_authenticated=is_basic_authenticated(),
    has_email_user=get_current_user() is not None,
  )


def can_use_admin_features() -> bool:
  from tech_cartography.auth.basic_auth import admin_features_allowed
  from tech_cartography.ui.demo_safe_ui import UI_MODE_DEVELOPER, get_ui_mode
  from tech_cartography.ui.developer_mode_visibility import is_show_developer_mode_enabled

  developer_active = is_show_developer_mode_enabled() and get_ui_mode() == UI_MODE_DEVELOPER
  return admin_features_allowed(
    login_required=is_login_required(),
    basic_authenticated=is_basic_authenticated(),
    auth_role=get_auth_role(),
    developer_mode_active=developer_active,
  )


def render_production_access_blocked(feature_label: str) -> None:
  st.warning(f"{feature_label} はログイン後に利用できます。")


def render_admin_access_blocked(feature_label: str) -> None:
  st.warning(f"{feature_label} は管理者ログイン後に利用できます。")


def build_app_user_from_basic_auth(auth: dict[str, Any]) -> dict[str, Any]:
  username = str(auth.get("username") or "user")
  display_name = str(auth.get("display_name") or username)
  synthetic_email = f"{username}@tech-cartography.local"
  return {
    "user_id": f"basic-auth:{username}",
    "email": synthetic_email,
    "display_name": display_name,
    "company_name": None,
    "username": username,
    "auth_role": auth.get("role", "member"),
    "weekly_email_enabled": False,
    "last_run_id": None,
  }


def render_basic_login_screen() -> None:
  st.markdown(inject_easy_ui_css(), unsafe_allow_html=True)
  st.markdown('<div class="tc-main-title">Tech Cartography Live Beta</div>', unsafe_allow_html=True)
  st.markdown(
    '<div class="tc-main-subtitle">職場内ベータ版 — ユーザー名とパスワードでログイン</div>',
    unsafe_allow_html=True,
  )
  st.markdown(
    render_info_box(
      "この環境は職場内ベータ向けです。"
      "ログイン後に本番実行・設定変更などの操作が利用できます。"
      "デモ閲覧専用環境では REQUIRE_LOGIN=false を使用してください。"
    ),
    unsafe_allow_html=True,
  )
  if is_login_required() and not users_configured():
    st.markdown(
      render_warning_box(
        "認証設定（TECH_CARTOGRAPHY_LOGIN_USERNAME / TECH_CARTOGRAPHY_LOGIN_PASSWORD "
        "または TECH_CARTOGRAPHY_USERS_JSON）が未設定です。管理者に連絡してください。"
      ),
      unsafe_allow_html=True,
    )

  with st.form("basic_login_form", clear_on_submit=False):
    username = st.text_input("username", placeholder="username")
    password = st.text_input("password", type="password", placeholder="password")
    submitted = st.form_submit_button("ログイン", type="primary", use_container_width=True)

  if submitted:
    auth_user = authenticate(username, password)
    if auth_user is None:
      st.markdown(render_warning_box("ユーザー名またはパスワードが違います。"), unsafe_allow_html=True)
      return
    set_basic_auth_session(auth_user)
    st.rerun()


def require_basic_login_gate() -> dict[str, Any] | None:
  session = get_basic_auth_session()
  if session:
    return session
  render_basic_login_screen()
  st.stop()
  return None


def render_basic_auth_sidebar(*, sidebar_button) -> None:
  session = get_basic_auth_session()
  if not session:
    return
  name = session.get("display_name") or session.get("username")
  role = session.get("role") or "member"
  st.caption(f"ログイン中: {name} ({role})")
  if sidebar_button("ログアウト", key="basic_logout_button"):
    clear_basic_auth_session()
    from tech_cartography.ui.login_view import logout_user

    logout_user()
    st.rerun()
