"""Tests for Watch Profile fields in operation status (Phase 25S)."""

from __future__ import annotations

import json
from pathlib import Path

from tech_cartography.runtime.live_artifact_paths import ensure_live_artifact_dirs
from tech_cartography.runtime.watch_profile_management_config import ENABLE_WATCH_PROFILE_MANAGEMENT_ENV
from tech_cartography.services.live_operation_status import build_operation_cycle_status
from tech_cartography.services.live_watch_profile_manager import create_watch_profile_draft, promote_draft_to_active
from tech_cartography.runtime.watch_profile_management_config import get_activation_confirmation_text


def test_operation_status_includes_watch_profile_fields(tmp_path: Path, monkeypatch) -> None:
  monkeypatch.setenv(ENABLE_WATCH_PROFILE_MANAGEMENT_ENV, "true")
  ensure_live_artifact_dirs(tmp_path)
  admin_ctx = {"user_id": "admin@example.com", "role": "admin", "is_admin": True}
  create_watch_profile_draft(
    profile_input={
      "theme_name": "Hydrogen Storage",
      "search_keywords": ["MOF"],
    },
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context=admin_ctx,
  )
  status = build_operation_cycle_status(tmp_path)
  assert status["watch_profile_status"] == "draft_waiting_approval"
  assert status["latest_draft_exists"] is True
  assert status["active_watch_profile_exists"] is False
  assert "watch_profile" in status

  from tech_cartography.services.live_watch_profile_manager import get_latest_watch_profile_draft

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
  status2 = build_operation_cycle_status(tmp_path)
  assert status2["watch_profile_status"] == "active_profile_ready"
  assert status2["active_watch_profile_exists"] is True
  assert status2["active_watch_profile_theme"] == "Hydrogen Storage"
