"""Tests for user profile helpers."""

from tech_cartography.users.user_profile import (
  UserProfile,
  build_user_id,
  create_user_profile,
  normalize_email,
  user_profile_from_dict,
  user_profile_to_dict,
  validate_email,
)


def test_normalize_email() -> None:
  assert normalize_email("  User@Example.COM ") == "user@example.com"


def test_validate_email() -> None:
  assert validate_email("user@example.com")
  assert not validate_email("not-an-email")
  assert not validate_email("")


def test_build_user_id_is_short_hash() -> None:
  uid = build_user_id("user@example.com")
  assert len(uid) == 16
  assert uid == build_user_id("USER@example.com")
  assert "@" not in uid


def test_user_profile_roundtrip() -> None:
  profile = create_user_profile("test@example.com", display_name="Tester", company_name="ACME")
  data = user_profile_to_dict(profile)
  restored = user_profile_from_dict(data)
  assert restored.email == "test@example.com"
  assert restored.display_name == "Tester"
  assert restored.weekly_email_enabled is False


def test_weekly_email_enabled_default_false() -> None:
  profile = create_user_profile("a@b.co")
  assert profile.weekly_email_enabled is False
