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
