"""Tests for watch profile store."""

from __future__ import annotations

from tech_cartography.users.watch_profile_store import (
  CARBON_FIBER_THEME,
  create_default_carbon_fiber_watch_profile,
  ensure_default_watch_profile,
  get_active_watch_profile,
  load_watch_profiles,
  save_watch_profiles,
  update_watch_profile,
)


def test_default_carbon_fiber_watch_profile() -> None:
  profile = create_default_carbon_fiber_watch_profile("user123")
  assert profile["theme"] == CARBON_FIBER_THEME
  assert "PAN" in profile["keywords"]
  assert "Toray" in profile["companies"]
  assert "CN" in profile["countries"]
  assert profile["weekly_email_enabled"] is False


def test_save_and_load_profiles(tmp_path) -> None:
  store = str(tmp_path / "profiles")
  user_id = "abc123"
  profile = create_default_carbon_fiber_watch_profile(user_id)
  save_watch_profiles(user_id, [profile], store_dir=store)
  loaded = load_watch_profiles(user_id, store_dir=store)
  assert len(loaded) == 1
  assert loaded[0]["theme"] == CARBON_FIBER_THEME


def test_get_active_watch_profile_creates_default(tmp_path) -> None:
  store = str(tmp_path / "profiles")
  active = get_active_watch_profile("user999", store_dir=store)
  assert active["is_active"] is True
  assert active["theme"] == CARBON_FIBER_THEME


def test_update_watch_profile_weekly_email(tmp_path) -> None:
  store = str(tmp_path / "profiles")
  profiles = ensure_default_watch_profile("user1", store_dir=store)
  pid = profiles[0]["watch_profile_id"]
  updated = update_watch_profile("user1", pid, {"weekly_email_enabled": True}, store_dir=store)
  assert updated["weekly_email_enabled"] is True
