"""Tests for Live Watch Profile manager (Phase 25S)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tech_cartography.runtime.live_artifact_paths import ensure_live_artifact_dirs
from tech_cartography.runtime.watch_profile_management_config import (
  ENABLE_WATCH_PROFILE_MANAGEMENT_ENV,
  get_activation_confirmation_text,
  get_archive_confirmation_text,
  get_rollback_confirmation_text,
)
from tech_cartography.services.live_run_history import list_run_history_entries
from tech_cartography.services.live_watch_profile_manager import (
  ACTION_ACTIVATE,
  ACTION_DRAFT_SAVE,
  archive_active_watch_profile,
  create_watch_profile_draft,
  get_active_watch_profile,
  get_latest_watch_profile_draft,
  promote_draft_to_active,
  rollback_to_previous_watch_profile,
)


@pytest.fixture
def enabled_mgmt(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(ENABLE_WATCH_PROFILE_MANAGEMENT_ENV, "true")


@pytest.fixture
def admin_ctx() -> dict:
  return {"user_id": "admin@example.com", "role": "admin", "is_admin": True}


def _draft_input() -> dict:
  return {
    "theme_name": "Solid State Battery",
    "search_keywords": ["solid electrolyte"],
    "search_queries": ["solid state battery separator"],
  }


def test_draft_save_creates_json_and_md(tmp_path: Path, enabled_mgmt: None, admin_ctx: dict) -> None:
  ensure_live_artifact_dirs(tmp_path)
  result = create_watch_profile_draft(
    profile_input=_draft_input(),
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context=admin_ctx,
  )
  assert result["ok"] is True
  paths = result["saved_paths"]
  assert Path(paths["json"]).is_file()
  assert Path(paths["markdown"]).is_file()


def test_activate_requires_confirmation(tmp_path: Path, enabled_mgmt: None, admin_ctx: dict) -> None:
  ensure_live_artifact_dirs(tmp_path)
  draft = create_watch_profile_draft(
    profile_input=_draft_input(),
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context=admin_ctx,
  )
  _, draft_path = get_latest_watch_profile_draft(tmp_path)
  assert draft_path
  bad = promote_draft_to_active(
    draft_path=draft_path,
    confirm_text="WRONG",
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context=admin_ctx,
  )
  assert bad["ok"] is False
  active, _ = get_active_watch_profile(tmp_path)
  assert active is None


def test_activate_archives_previous_active(tmp_path: Path, enabled_mgmt: None, admin_ctx: dict) -> None:
  ensure_live_artifact_dirs(tmp_path)
  first = create_watch_profile_draft(
    profile_input=_draft_input(),
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context=admin_ctx,
  )
  _, first_path = get_latest_watch_profile_draft(tmp_path)
  promote_draft_to_active(
    draft_path=first_path,
    confirm_text=get_activation_confirmation_text(),
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context=admin_ctx,
  )
  second = create_watch_profile_draft(
    profile_input={**_draft_input(), "theme_name": "Solid State Battery v2"},
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context=admin_ctx,
  )
  _, second_path = get_latest_watch_profile_draft(tmp_path)
  promote_draft_to_active(
    draft_path=second_path,
    confirm_text=get_activation_confirmation_text(),
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context=admin_ctx,
  )
  archive_dir = tmp_path / "outputs" / "live_watch_profiles" / "archive"
  archives = list(archive_dir.glob("watch_profile_archive_*.json"))
  assert archives
  active, active_path = get_active_watch_profile(tmp_path)
  assert active is not None
  assert active_path
  assert active.get("theme_name") == "Solid State Battery v2"


def test_member_cannot_activate(tmp_path: Path, enabled_mgmt: None) -> None:
  ensure_live_artifact_dirs(tmp_path)
  admin_ctx = {"user_id": "admin@example.com", "role": "admin", "is_admin": True}
  create_watch_profile_draft(
    profile_input=_draft_input(),
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context=admin_ctx,
  )
  _, draft_path = get_latest_watch_profile_draft(tmp_path)
  result = promote_draft_to_active(
    draft_path=draft_path,
    confirm_text=get_activation_confirmation_text(),
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="member",
    user_context={"user_id": "member@example.com", "role": "member"},
  )
  assert result["ok"] is False


def test_run_history_records_actions(tmp_path: Path, enabled_mgmt: None, admin_ctx: dict) -> None:
  ensure_live_artifact_dirs(tmp_path)
  create_watch_profile_draft(
    profile_input=_draft_input(),
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context=admin_ctx,
  )
  entries = list_run_history_entries(tmp_path, viewer_user_context=admin_ctx)
  action_types = {e.get("action_type") for e in entries}
  assert ACTION_DRAFT_SAVE in action_types


def test_rollback_requires_confirmation(tmp_path: Path, enabled_mgmt: None, admin_ctx: dict) -> None:
  ensure_live_artifact_dirs(tmp_path)
  create_watch_profile_draft(
    profile_input=_draft_input(),
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context=admin_ctx,
  )
  _, draft_path = get_latest_watch_profile_draft(tmp_path)
  promote_draft_to_active(
    draft_path=draft_path,
    confirm_text=get_activation_confirmation_text(),
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context=admin_ctx,
  )
  result = rollback_to_previous_watch_profile(
    confirm_text="WRONG",
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context=admin_ctx,
  )
  assert result["ok"] is False
