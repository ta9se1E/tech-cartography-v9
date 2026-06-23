"""Scheduler dry-run integration with Watch Profile (Phase 25S)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tech_cartography.runtime.live_artifact_paths import ensure_live_artifact_dirs
from tech_cartography.runtime.watch_profile_management_config import ENABLE_WATCH_PROFILE_MANAGEMENT_ENV
from tech_cartography.services.live_scheduler_dry_run import run_live_scheduler_dry_run
from tech_cartography.services.live_watch_profile_manager import (
  create_watch_profile_draft,
  get_latest_watch_profile_draft,
  promote_draft_to_active,
)
from tech_cartography.runtime.watch_profile_management_config import get_activation_confirmation_text


@pytest.fixture
def enabled_mgmt(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(ENABLE_WATCH_PROFILE_MANAGEMENT_ENV, "true")


def test_dry_run_references_active_profile(tmp_path: Path, enabled_mgmt: None) -> None:
  ensure_live_artifact_dirs(tmp_path)
  admin_ctx = {"user_id": "admin@example.com", "role": "admin", "is_admin": True}
  create_watch_profile_draft(
    profile_input={"theme_name": "Ceramics", "search_keywords": ["alumina"]},
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
  result = run_live_scheduler_dry_run(
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context=admin_ctx,
  )
  assert result["ok"] is True
  payload = result["payload"]
  assert payload.get("active_watch_profile_path")
  assert "verify_active_watch_profile" in payload.get("planned_steps", [])
  saved = json.loads(Path(result["saved_paths"]["json"]).read_text(encoding="utf-8"))
  assert saved["active_watch_profile_path"]


def test_dry_run_warns_without_active_profile(tmp_path: Path) -> None:
  ensure_live_artifact_dirs(tmp_path)
  admin_ctx = {"user_id": "admin@example.com", "role": "admin", "is_admin": True}
  result = run_live_scheduler_dry_run(
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context=admin_ctx,
  )
  assert result["ok"] is True
  assert any("active Watch Profile" in w for w in result.get("warnings") or [])
