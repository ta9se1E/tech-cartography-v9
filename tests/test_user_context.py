"""Tests for user context (Phase 25M)."""

from __future__ import annotations

from tech_cartography.runtime.user_context import (
  build_user_context_from_basic_auth,
  normalize_user_context,
  user_context_as_dict,
)


def test_build_user_context_from_basic_auth_has_no_password() -> None:
  ctx = build_user_context_from_basic_auth(
    {"username": "admin", "role": "admin", "display_name": "Admin User"},
  )
  assert ctx["user_id"] == "admin"
  assert ctx["is_admin"] is True
  assert ctx["auth_provider"] == "streamlit_basic"
  serialized = str(ctx)
  assert "password" not in serialized.lower()


def test_normalize_fallback() -> None:
  ctx = normalize_user_context(None)
  assert ctx["user_id"] == "anonymous"
  assert ctx["is_admin"] is False


def test_user_context_as_dict_safe_copy() -> None:
  raw = {"user_id": "u1", "display_name": "U1", "role": "member", "auth_provider": "streamlit_basic"}
  copied = user_context_as_dict(raw)
  assert copied["user_id"] == "u1"
  assert "password" not in copied


def test_build_user_context_from_iap_identity() -> None:
  from tech_cartography.runtime.user_context import (
    AUTH_PROVIDER_GOOGLE_IAP,
    build_user_context_from_iap_identity,
    evaluate_live_admin_access,
  )

  ctx = build_user_context_from_iap_identity(
    {
      "email": "admin@example.com",
      "user_id": "admin@example.com",
      "role": "admin",
      "display_name": "Admin",
      "is_admin": True,
    },
  )
  assert ctx["auth_provider"] == AUTH_PROVIDER_GOOGLE_IAP
  assert ctx["is_admin"] is True

  allowed, reason, _ = evaluate_live_admin_access(
    login_required=True,
    is_authenticated=False,
    auth_role="member",
    user_context=ctx,
  )
  assert allowed is True
  assert reason is None


def test_evaluate_live_admin_access_requires_login_when_anonymous() -> None:
  from tech_cartography.runtime.user_context import evaluate_live_admin_access

  allowed, reason, _ = evaluate_live_admin_access(
    login_required=True,
    is_authenticated=False,
    auth_role="member",
    user_context=None,
  )
  assert allowed is False
  assert reason == "login_required"
