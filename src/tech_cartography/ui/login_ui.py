"""Streamlit login gate UI and production access guards (Phase 25A, 25N)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from tech_cartography.auth.basic_auth import (
  AuthUser,
  authenticate,
  is_login_required,
  users_configured,
)
from tech_cartography.runtime.auth_provider_config import get_auth_provider_mode
from tech_cartography.runtime.iap_identity import (
  get_request_headers_safe,
  resolve_iap_identity_from_headers,
)
from tech_cartography.ui.easy_japanese_ui import inject_easy_ui_css, render_info_box, render_warning_box
from tech_cartography.ui.login_view import get_current_user

STATE_AUTH_AUTHENTICATED = "tc_basic_auth_authenticated"
STATE_AUTH_USERNAME = "tc_basic_auth_username"
STATE_AUTH_ROLE = "tc_basic_auth_role"
STATE_AUTH_DISPLAY_NAME = "tc_basic_auth_display_name"

STATE_IAP_AUTHENTICATED = "tc_iap_auth_authenticated"
STATE_IAP_USER_EMAIL = "tc_iap_user_email"
STATE_IAP_USER_ID = "tc_iap_user_id"
STATE_IAP_ROLE = "tc_iap_role"
STATE_IAP_DISPLAY_NAME = "tc_iap_display_name"
STATE_IAP_IDENTITY_STATUS = "tc_iap_identity_status"


def get_basic_auth_session() -> dict[str, Any] | None:
  if not st.session_state.get(STATE_AUTH_AUTHENTICATED):
    return None
  return {
    "authenticated": True,
    "auth_provider": "streamlit_basic",
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


def get_iap_auth_session() -> dict[str, Any] | None:
  if not st.session_state.get(STATE_IAP_AUTHENTICATED):
    return None
  email = str(st.session_state.get(STATE_IAP_USER_EMAIL) or "")
  return {
    "authenticated": True,
    "auth_provider": "google_iap",
    "email": email,
    "user_id": str(st.session_state.get(STATE_IAP_USER_ID) or email),
    "role": st.session_state.get(STATE_IAP_ROLE, "member"),
    "display_name": st.session_state.get(STATE_IAP_DISPLAY_NAME, email),
    "is_admin": str(st.session_state.get(STATE_IAP_ROLE) or "member") == "admin",
  }


def set_iap_auth_session(identity: dict[str, Any]) -> None:
  st.session_state[STATE_IAP_AUTHENTICATED] = True
  st.session_state[STATE_IAP_USER_EMAIL] = identity.get("email")
  st.session_state[STATE_IAP_USER_ID] = identity.get("user_id")
  st.session_state[STATE_IAP_ROLE] = identity.get("role")
  st.session_state[STATE_IAP_DISPLAY_NAME] = identity.get("display_name")


def clear_iap_auth_session() -> None:
  for key in (
    STATE_IAP_AUTHENTICATED,
    STATE_IAP_USER_EMAIL,
    STATE_IAP_USER_ID,
    STATE_IAP_ROLE,
    STATE_IAP_DISPLAY_NAME,
  ):
    if key in st.session_state:
      del st.session_state[key]


def get_last_iap_identity_status() -> dict[str, Any] | None:
  status = st.session_state.get(STATE_IAP_IDENTITY_STATUS)
  return status if isinstance(status, dict) else None


def set_last_iap_identity_status(status: dict[str, Any]) -> None:
  safe = {
    "status": status.get("status"),
    "email": status.get("email"),
    "user_id": status.get("user_id"),
    "display_name": status.get("display_name"),
    "role": status.get("role"),
    "is_admin": status.get("is_admin"),
    "auth_provider": status.get("auth_provider"),
    "message": status.get("message"),
    "role_mapping_status": status.get("role_mapping_status"),
    "warnings": status.get("warnings") or [],
    "jwt_verification": {
      "status": (status.get("jwt_verification") or {}).get("status"),
      "verified": (status.get("jwt_verification") or {}).get("verified"),
      "message": (status.get("jwt_verification") or {}).get("message"),
      "production_caution": (status.get("jwt_verification") or {}).get("production_caution"),
    },
  }
  st.session_state[STATE_IAP_IDENTITY_STATUS] = safe


def is_basic_authenticated() -> bool:
  return bool(st.session_state.get(STATE_AUTH_AUTHENTICATED))


def is_iap_authenticated() -> bool:
  return bool(st.session_state.get(STATE_IAP_AUTHENTICATED))


def is_app_authenticated() -> bool:
  return is_iap_authenticated() or is_basic_authenticated()


def get_active_auth_session() -> dict[str, Any] | None:
  if is_iap_authenticated():
    return get_iap_auth_session()
  if is_basic_authenticated():
    return get_basic_auth_session()
  return None


def get_auth_role() -> str:
  if is_iap_authenticated():
    return str(st.session_state.get(STATE_IAP_ROLE) or "member")
  return str(st.session_state.get(STATE_AUTH_ROLE) or "member")


def has_app_session_access() -> bool:
  if is_login_required():
    return is_app_authenticated()
  return get_current_user() is not None


def can_use_production_features() -> bool:
  from tech_cartography.auth.basic_auth import production_features_allowed

  return production_features_allowed(
    login_required=is_login_required(),
    basic_authenticated=is_app_authenticated(),
    has_email_user=get_current_user() is not None,
  )


def can_use_admin_features() -> bool:
  from tech_cartography.auth.basic_auth import admin_features_allowed
  from tech_cartography.ui.demo_safe_ui import UI_MODE_DEVELOPER, get_ui_mode
  from tech_cartography.ui.developer_mode_visibility import is_show_developer_mode_enabled

  developer_active = is_show_developer_mode_enabled() and get_ui_mode() == UI_MODE_DEVELOPER
  return admin_features_allowed(
    login_required=is_login_required(),
    basic_authenticated=is_app_authenticated(),
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
    "auth_provider": "streamlit_basic",
    "weekly_email_enabled": False,
    "last_run_id": None,
  }


def build_app_user_from_iap_auth(auth: dict[str, Any]) -> dict[str, Any]:
  email = str(auth.get("email") or auth.get("user_id") or "iap-user")
  display_name = str(auth.get("display_name") or email)
  role = str(auth.get("role") or "member")
  return {
    "user_id": email,
    "email": email,
    "display_name": display_name,
    "company_name": None,
    "username": email,
    "auth_role": role,
    "auth_provider": "google_iap",
    "weekly_email_enabled": False,
    "last_run_id": None,
  }


def build_app_user_from_auth_session(auth: dict[str, Any]) -> dict[str, Any]:
  if str(auth.get("auth_provider") or "") == "google_iap":
    return build_app_user_from_iap_auth(auth)
  return build_app_user_from_basic_auth(auth)


def render_basic_login_screen(*, hybrid_fallback: bool = False) -> None:
  st.markdown(inject_easy_ui_css(), unsafe_allow_html=True)
  st.markdown('<div class="tc-main-title">Tech Cartography Live Beta</div>', unsafe_allow_html=True)
  subtitle = "職場内ベータ版 — ユーザー名とパスワードでログイン"
  if hybrid_fallback:
    subtitle = "IAP ヘッダー未検出 — Basic Login にフォールバック"
  st.markdown(f'<div class="tc-main-subtitle">{subtitle}</div>', unsafe_allow_html=True)
  st.markdown(
    render_info_box(
      "この環境は職場内ベータ向けです。"
      "ログイン後に本番実行・設定変更などの操作が利用できます。"
      "デモ閲覧専用環境では REQUIRE_LOGIN=false を使用してください。"
    ),
    unsafe_allow_html=True,
  )
  if hybrid_fallback:
    st.markdown(
      render_warning_box(
        "AUTH_PROVIDER_MODE=hybrid ですが IAP identity が見つかりません。"
        " ローカル開発では Basic Login を利用できます。"
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
    submitted = st.form_submit_button("ログイン", type="primary", width="stretch")

  if submitted:
    auth_user = authenticate(username, password)
    if auth_user is None:
      st.markdown(render_warning_box("ユーザー名またはパスワードが違います。"), unsafe_allow_html=True)
      return
    clear_iap_auth_session()
    set_basic_auth_session(auth_user)
    st.rerun()


def render_iap_blocked_screen(message: str) -> None:
  st.markdown(inject_easy_ui_css(), unsafe_allow_html=True)
  st.markdown('<div class="tc-main-title">Tech Cartography Live Beta</div>', unsafe_allow_html=True)
  st.markdown(
    render_warning_box(
      f"IAP 認証でアクセスできません。{message}"
      " 管理者に TECH_CARTOGRAPHY_ADMIN_EMAILS / ALLOWED_EMAIL_DOMAINS を確認してください。"
    ),
    unsafe_allow_html=True,
  )


def render_iap_required_screen(message: str) -> None:
  st.markdown(inject_easy_ui_css(), unsafe_allow_html=True)
  st.markdown('<div class="tc-main-title">Tech Cartography Live Beta</div>', unsafe_allow_html=True)
  st.markdown(
    render_warning_box(
      f"IAP 認証が必要です。{message}"
      " AUTH_PROVIDER_MODE=iap では Google IAP 経由のアクセスのみ許可されます。"
    ),
    unsafe_allow_html=True,
  )


def _try_iap_login_from_headers() -> dict[str, Any] | None:
  identity = resolve_iap_identity_from_headers(get_request_headers_safe())
  set_last_iap_identity_status(identity)
  status = str(identity.get("status") or "")
  if status == "ok":
    clear_basic_auth_session()
    set_iap_auth_session(identity)
    return get_iap_auth_session()
  return identity


def require_auth_login_gate() -> dict[str, Any] | None:
  active = get_active_auth_session()
  if active:
    return active

  mode = get_auth_provider_mode()
  if mode in {"iap", "hybrid"}:
    iap_result = _try_iap_login_from_headers()
    if isinstance(iap_result, dict) and iap_result.get("authenticated"):
      return iap_result

    identity_status = get_last_iap_identity_status() or {}
    status = str(identity_status.get("status") or "")
    if status in {"access_denied", "invalid"}:
      render_iap_blocked_screen(str(identity_status.get("message") or status))
      st.stop()
      return None
    if mode == "iap":
      render_iap_required_screen(str(identity_status.get("message") or "IAP headers missing"))
      st.stop()
      return None

  session = get_basic_auth_session()
  if session:
    return session
  render_basic_login_screen(hybrid_fallback=(mode == "hybrid"))
  st.stop()
  return None


def require_basic_login_gate() -> dict[str, Any] | None:
  return require_auth_login_gate()


def render_basic_auth_sidebar(*, sidebar_button) -> None:
  session = get_active_auth_session()
  if not session:
    return
  provider = session.get("auth_provider") or "streamlit_basic"
  name = session.get("display_name") or session.get("username") or session.get("email")
  role = session.get("role") or "member"
  st.caption(f"ログイン中: {name} ({role}) [{provider}]")
  if sidebar_button("ログアウト", key="basic_logout_button"):
    clear_basic_auth_session()
    clear_iap_auth_session()
    from tech_cartography.ui.login_view import logout_user

    logout_user()
    st.rerun()
