"""Tests for basic auth helpers (Phase 25A)."""

from __future__ import annotations

import json

import pytest

from tech_cartography.auth.basic_auth import (
  USERS_JSON_ENV,
  admin_features_allowed,
  authenticate,
  hash_password,
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


def test_empty_users_json_fails_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv(USERS_JSON_ENV, raising=False)
  assert load_user_records() == []
  assert users_configured() is False
  assert authenticate("user1", "anything") is None


def test_authenticate_success(sample_users_json: str) -> None:
  user = authenticate("user1", "correct-horse")
  assert user is not None
  assert user.username == "user1"
  assert user.role == "member"
  assert user.display_name == "User 1"


def test_authenticate_wrong_password(sample_users_json: str) -> None:
  assert authenticate("user1", "wrong-password") is None


def test_authenticate_unknown_user(sample_users_json: str) -> None:
  assert authenticate("unknown", "correct-horse") is None


def test_password_hash_not_equal_to_plaintext() -> None:
  plain = "secret-value"
  hashed = hash_password(plain)
  assert hashed != plain
  assert verify_password(plain, hashed) is True
  assert verify_password("other", hashed) is False


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
