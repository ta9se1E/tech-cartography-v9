"""Tests for JSON user store."""

from __future__ import annotations

from tech_cartography.users.user_store import (
  get_or_create_user,
  get_user_by_email,
  set_last_run_id,
  set_weekly_email_enabled,
  update_user_profile,
)


def test_get_or_create_user(tmp_path) -> None:
  store = str(tmp_path / "store")
  user = get_or_create_user("user@example.com", display_name="U1", store_dir=store)
  assert user["email"] == "user@example.com"
  assert user["display_name"] == "U1"
  assert user["user_id"]


def test_same_email_returns_same_user(tmp_path) -> None:
  store = str(tmp_path / "store")
  u1 = get_or_create_user("user@example.com", store_dir=store)
  u2 = get_or_create_user("USER@example.com", store_dir=store)
  assert u1["user_id"] == u2["user_id"]


def test_update_user_profile(tmp_path) -> None:
  store = str(tmp_path / "store")
  user = get_or_create_user("user@example.com", store_dir=store)
  updated = update_user_profile(user["user_id"], {"company_name": "Toray Lab"}, store_dir=store)
  assert updated["company_name"] == "Toray Lab"


def test_set_last_run_id(tmp_path) -> None:
  store = str(tmp_path / "store")
  user = get_or_create_user("user@example.com", store_dir=store)
  updated = set_last_run_id(user["user_id"], "20260616_163006", store_dir=store)
  assert updated["last_run_id"] == "20260616_163006"
  by_email = get_user_by_email("user@example.com", store_dir=store)
  assert by_email["last_run_id"] == "20260616_163006"


def test_set_weekly_email_enabled(tmp_path) -> None:
  store = str(tmp_path / "store")
  user = get_or_create_user("user@example.com", store_dir=store)
  updated = set_weekly_email_enabled(user["user_id"], True, store_dir=store)
  assert updated["weekly_email_enabled"] is True
