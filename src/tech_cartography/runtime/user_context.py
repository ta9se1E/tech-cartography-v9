"""User run context — shared actor identity for Live actions (Phase 25M)."""

from __future__ import annotations

from typing import Any

AUTH_PROVIDER_STREAMLIT_BASIC = "streamlit_basic"
AUTH_PROVIDER_EMAIL_SESSION = "email_session"
AUTH_PROVIDER_NONE = "none"

FALLBACK_USER_CONTEXT: dict[str, Any] = {
  "user_id": "anonymous",
  "display_name": "anonymous",
  "role": "member",
  "auth_provider": AUTH_PROVIDER_NONE,
  "is_admin": False,
}


def build_user_context_from_basic_auth(session: dict[str, Any]) -> dict[str, Any]:
  username = str(session.get("username") or "user").strip() or "user"
  role = str(session.get("role") or "member").strip().lower()
  display_name = str(session.get("display_name") or username).strip() or username
  return {
    "user_id": username,
    "display_name": display_name,
    "role": role,
    "auth_provider": AUTH_PROVIDER_STREAMLIT_BASIC,
    "is_admin": role == "admin",
  }


def build_user_context_from_app_user(user: dict[str, Any]) -> dict[str, Any]:
  user_id = str(user.get("user_id") or user.get("email") or "user").strip() or "user"
  display_name = str(user.get("display_name") or user_id).strip() or user_id
  auth_role = str(user.get("auth_role") or "member").strip().lower()
  return {
    "user_id": user_id,
    "display_name": display_name,
    "role": auth_role if auth_role in {"admin", "member"} else "member",
    "auth_provider": AUTH_PROVIDER_EMAIL_SESSION,
    "is_admin": auth_role == "admin",
  }


def normalize_user_context(user_context: dict[str, Any] | None) -> dict[str, Any]:
  if not user_context:
    return dict(FALLBACK_USER_CONTEXT)
  role = str(user_context.get("role") or "member").strip().lower()
  user_id = str(user_context.get("user_id") or "anonymous").strip() or "anonymous"
  display_name = str(user_context.get("display_name") or user_id).strip() or user_id
  auth_provider = str(user_context.get("auth_provider") or AUTH_PROVIDER_NONE).strip() or AUTH_PROVIDER_NONE
  return {
    "user_id": user_id,
    "display_name": display_name,
    "role": role if role in {"admin", "member"} else "member",
    "auth_provider": auth_provider,
    "is_admin": bool(user_context.get("is_admin")) or role == "admin",
  }


def resolve_user_context() -> dict[str, Any]:
  """Resolve current user from Streamlit session when available."""
  try:
    import streamlit as st  # noqa: F401 — optional runtime dependency
  except ImportError:
    return dict(FALLBACK_USER_CONTEXT)

  try:
    from tech_cartography.auth.basic_auth import is_login_required
    from tech_cartography.ui.login_ui import get_basic_auth_session, is_basic_authenticated

    if is_login_required() and is_basic_authenticated():
      session = get_basic_auth_session()
      if session:
        return build_user_context_from_basic_auth(session)

    from tech_cartography.ui.login_view import get_current_user

    user = get_current_user()
    if user:
      return build_user_context_from_app_user(user)
  except Exception:
    return dict(FALLBACK_USER_CONTEXT)

  return dict(FALLBACK_USER_CONTEXT)


def user_context_as_dict(user_context: dict[str, Any]) -> dict[str, Any]:
  """Return a copy safe to embed in artifacts (no secrets)."""
  normalized = normalize_user_context(user_context)
  return {
    "user_id": normalized["user_id"],
    "display_name": normalized["display_name"],
    "role": normalized["role"],
    "auth_provider": normalized["auth_provider"],
    "is_admin": normalized["is_admin"],
  }
