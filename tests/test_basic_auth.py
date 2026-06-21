"""Tests for basic auth helpers (Phase 25A)."""

from __future__ import annotations

import json

import pytest

from tech_cartography.auth.basic_auth import (
  SIMPLE_LOGIN_PASSWORD_ENV,
  SIMPLE_LOGIN_USERNAME_ENV,
  USERS_JSON_ENV,
  admin_features_allowed,
  authenticate,
  authenticate_bcrypt_json,
  authenticate_simple,
  hash_password,
  is_simple_login_configured,
  load_user_records,
  production_features_allowed,
  users_configured,
  verify_password,
)


@pytest.fixture
def sample_users_json(monkeypatch: pytest.MonkeyPatch) -> str:
  password_hash = hash_password("correct-horse")
  payload = [
    {
      "username": "user1",
      "password_hash": password_hash,
      "role": "member",
      "display_name": "User 1",
    },
    {
      "username": "admin",
      "password_hash": password_hash,
      "role": "admin",
      "display_name": "Admin",
    },
  ]
  raw = json.dumps(payload)
  monkeypatch.setenv(USERS_JSON_ENV, raw)
  return raw


@pytest.fixture
def simple_login_env(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(SIMPLE_LOGIN_USERNAME_ENV, "admin")
  monkeypatch.setenv(SIMPLE_LOGIN_PASSWORD_ENV, "test-password")


def test_empty_users_json_fails_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv(USERS_JSON_ENV, raising=False)
  monkeypatch.delenv(SIMPLE_LOGIN_USERNAME_ENV, raising=False)
  monkeypatch.delenv(SIMPLE_LOGIN_PASSWORD_ENV, raising=False)
  assert load_user_records() == []
  assert users_configured() is False
  assert authenticate("user1", "anything") is None


def test_simple_login_success(simple_login_env: None) -> None:
  assert is_simple_login_configured() is True
  user = authenticate("admin", "test-password")
  assert user is not None
  assert user.username == "admin"
  assert user.role == "admin"
  assert user.display_name == "admin"


def test_simple_login_wrong_password(simple_login_env: None) -> None:
  assert authenticate("admin", "wrong-password") is None


def test_simple_login_wrong_username(simple_login_env: None) -> None:
  assert authenticate("other", "test-password") is None


def test_simple_login_takes_priority_over_bcrypt(
  simple_login_env: None,
  sample_users_json: str,
) -> None:
  user = authenticate("admin", "test-password")
  assert user is not None
  assert user.role == "admin"
  assert authenticate("admin", "correct-horse") is None


def test_bcrypt_fallback_when_simple_password_missing(
  monkeypatch: pytest.MonkeyPatch,
  sample_users_json: str,
) -> None:
  monkeypatch.setenv(SIMPLE_LOGIN_USERNAME_ENV, "admin")
  monkeypatch.delenv(SIMPLE_LOGIN_PASSWORD_ENV, raising=False)
  assert is_simple_login_configured() is False
  user = authenticate("user1", "correct-horse")
  assert user is not None
  assert user.role == "member"


def test_authenticate_success(sample_users_json: str) -> None:
  user = authenticate_bcrypt_json("user1", "correct-horse")
  assert user is not None
  assert user.username == "user1"
  assert user.role == "member"
  assert user.display_name == "User 1"


def test_authenticate_wrong_password(sample_users_json: str) -> None:
  assert authenticate_bcrypt_json("user1", "wrong-password") is None


def test_authenticate_unknown_user(sample_users_json: str) -> None:
  assert authenticate_bcrypt_json("unknown", "correct-horse") is None


def test_password_hash_not_equal_to_plaintext() -> None:
  plain = "secret-value"
  hashed = hash_password(plain)
  assert hashed != plain
  assert verify_password(plain, hashed) is True
  assert verify_password("other", hashed) is False


def test_auth_user_session_does_not_include_password(simple_login_env: None) -> None:
  user = authenticate_simple("admin", "test-password")
  assert user is not None
  session = user.to_session_dict()
  assert "password" not in session
  assert "test-password" not in str(session.values())


def test_production_features_allowed_matrix() -> None:
  assert production_features_allowed(
    login_required=True,
    basic_authenticated=True,
    has_email_user=False,
  )
  assert not production_features_allowed(
    login_required=True,
    basic_authenticated=False,
    has_email_user=True,
  )
  assert production_features_allowed(
    login_required=False,
    basic_authenticated=False,
    has_email_user=True,
  )


def test_admin_features_allowed_matrix() -> None:
  assert admin_features_allowed(
    login_required=True,
    basic_authenticated=True,
    auth_role="admin",
    developer_mode_active=False,
  )
  assert not admin_features_allowed(
    login_required=True,
    basic_authenticated=True,
    auth_role="member",
    developer_mode_active=False,
  )
