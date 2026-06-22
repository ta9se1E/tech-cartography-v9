"""Tests for optional multi-user basic login (Phase 25M)."""

from __future__ import annotations

import json

import pytest

from tech_cartography.auth.basic_auth import (
  ENABLE_MULTI_USER_LOGIN_ENV,
  USERS_JSON_ENV,
  authenticate,
  hash_password_pbkdf2,
  is_multi_user_login_enabled,
  verify_password_pbkdf2,
)


def test_pbkdf2_hash_and_verify() -> None:
  hashed = hash_password_pbkdf2("correct-horse-battery")
  assert hashed.startswith("pbkdf2_sha256$")
  assert verify_password_pbkdf2("correct-horse-battery", hashed)
  assert not verify_password_pbkdf2("wrong", hashed)


def test_multi_user_disabled_uses_simple_login_when_configured(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  monkeypatch.delenv(ENABLE_MULTI_USER_LOGIN_ENV, raising=False)
  monkeypatch.setenv("TECH_CARTOGRAPHY_LOGIN_USERNAME", "admin")
  monkeypatch.setenv("TECH_CARTOGRAPHY_LOGIN_PASSWORD", "test-password")
  assert is_multi_user_login_enabled() is False
  user = authenticate("admin", "test-password")
  assert user is not None
  assert user.role == "admin"


def test_multi_user_json_login(monkeypatch: pytest.MonkeyPatch) -> None:
  password_hash = hash_password_pbkdf2("member-pass")
  payload = json.dumps(
    [
      {
        "username": "member01",
        "display_name": "Member 01",
        "role": "member",
        "password_hash": password_hash,
      },
    ],
  )
  monkeypatch.setenv(ENABLE_MULTI_USER_LOGIN_ENV, "true")
  monkeypatch.setenv(USERS_JSON_ENV, payload)
  monkeypatch.delenv("TECH_CARTOGRAPHY_LOGIN_USERNAME", raising=False)
  monkeypatch.delenv("TECH_CARTOGRAPHY_LOGIN_PASSWORD", raising=False)
  user = authenticate("member01", "member-pass")
  assert user is not None
  assert user.role == "member"
  assert authenticate("member01", "wrong") is None
