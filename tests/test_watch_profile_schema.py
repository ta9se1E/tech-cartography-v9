"""Tests for Watch Profile schema (Phase 25S)."""

from __future__ import annotations

from tech_cartography.runtime.watch_profile_schema import (
  empty_watch_profile_template,
  normalize_watch_profile,
  validate_watch_profile_draft,
  validate_watch_profile_for_activation,
)


def test_valid_draft_passes_validation() -> None:
  profile = empty_watch_profile_template(theme_name="Carbon Fiber")
  profile["search_keywords"] = ["PAN", "CFRP"]
  ok, errors = validate_watch_profile_draft(profile)
  assert ok is True
  assert not errors


def test_activation_requires_search_conditions() -> None:
  profile = normalize_watch_profile(empty_watch_profile_template(theme_name="Theme"))
  ok, errors = validate_watch_profile_for_activation(profile)
  assert ok is False
  assert "search_conditions_required" in errors


def test_activation_passes_with_keywords() -> None:
  profile = normalize_watch_profile(empty_watch_profile_template(theme_name="Theme"))
  profile["search_keywords"] = ["battery separator"]
  ok, errors = validate_watch_profile_for_activation(profile)
  assert ok is True
  assert not errors
