"""Tests for login view helpers."""

from tech_cartography.ui.login_view import process_login_submission


def test_invalid_email_rejected(tmp_path, monkeypatch) -> None:
  monkeypatch.chdir(tmp_path)
  user, error = process_login_submission("not-email")
  assert user is None
  assert error


def test_valid_email_creates_user(tmp_path, monkeypatch) -> None:
  monkeypatch.chdir(tmp_path)
  user, error = process_login_submission("user@example.com", display_name="Tester")
  assert error is None
  assert user is not None
  assert user["email"] == "user@example.com"
  assert user["display_name"] == "Tester"
  assert user["user_id"]


def test_same_email_login_returns_same_user_id(tmp_path, monkeypatch) -> None:
  monkeypatch.chdir(tmp_path)
  u1, _ = process_login_submission("user@example.com")
  u2, _ = process_login_submission("USER@example.com")
  assert u1["user_id"] == u2["user_id"]
