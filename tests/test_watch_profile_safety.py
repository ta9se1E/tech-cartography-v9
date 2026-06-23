"""Safety guards for Watch Profile manager (Phase 25S)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tech_cartography.runtime.live_artifact_paths import ensure_live_artifact_dirs
from tech_cartography.runtime.watch_profile_management_config import ENABLE_WATCH_PROFILE_MANAGEMENT_ENV
from tech_cartography.services.live_digest_preview import build_save_payload
from tech_cartography.services.live_watch_profile_manager import create_watch_profile_draft
from tech_cartography.services.live_watch_profile_manager import (
  get_active_watch_profile,
  promote_draft_to_active,
  get_latest_watch_profile_draft,
)
from tech_cartography.runtime.watch_profile_management_config import get_activation_confirmation_text

MANAGER_PATH = Path(__file__).resolve().parents[1] / "src/tech_cartography/services/live_watch_profile_manager.py"
CLOUDBUILD = Path(__file__).resolve().parents[1] / "cloudbuild.yaml"
DEPLOY = Path(__file__).resolve().parents[1] / "scripts/deploy_live_safe.sh"

FORBIDDEN_IN_MANAGER = ("requests.", "smtplib", "send_email", "cloudscheduler", "scheduler.start")
SECRET_TOKENS = ("SMTP_PASSWORD", "jwt", "oauth", "api_key")


@pytest.fixture
def enabled_mgmt(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(ENABLE_WATCH_PROFILE_MANAGEMENT_ENV, "true")


def test_manager_source_has_no_external_calls() -> None:
  text = MANAGER_PATH.read_text(encoding="utf-8").lower()
  for token in FORBIDDEN_IN_MANAGER:
    assert token not in text


def test_artifacts_exclude_secrets(tmp_path: Path, enabled_mgmt: None) -> None:
  ensure_live_artifact_dirs(tmp_path)
  admin_ctx = {"user_id": "admin@example.com", "role": "admin", "is_admin": True}
  result = create_watch_profile_draft(
    profile_input={
      "theme_name": "Safe Theme",
      "search_keywords": ["polymer"],
      "notes": "no sensitive tokens here",
    },
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context=admin_ctx,
  )
  raw = Path(result["saved_paths"]["json"]).read_text(encoding="utf-8")
  for token in SECRET_TOKENS:
    assert token.lower() not in raw.lower()


def test_digest_preview_payload_includes_active_profile_reference(tmp_path: Path, enabled_mgmt: None) -> None:
  ensure_live_artifact_dirs(tmp_path)
  admin_ctx = {"user_id": "admin@example.com", "role": "admin", "is_admin": True}
  create_watch_profile_draft(
    profile_input={"theme_name": "Ref Theme", "search_keywords": ["test"]},
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
  active, active_path = get_active_watch_profile(tmp_path)
  payload = build_save_payload({"theme_name": "Ref Theme"}, output_root=tmp_path)
  assert payload.get("active_watch_profile_path") == active_path
  assert payload.get("active_watch_profile_id") == active.get("profile_id")


def test_deploy_defaults_disable_watch_profile_management() -> None:
  cloudbuild = CLOUDBUILD.read_text(encoding="utf-8")
  deploy = DEPLOY.read_text(encoding="utf-8")
  assert "ENABLE_WATCH_PROFILE_MANAGEMENT=false" in cloudbuild
  assert "ENABLE_WATCH_PROFILE_MANAGEMENT=false" in deploy
