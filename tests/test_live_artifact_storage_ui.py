"""Tests for live artifact storage UI wiring (Phase 25H)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tech_cartography.auth.basic_auth import REQUIRE_LOGIN_ENV
from tech_cartography.runtime.cloud_run_config import default_app_mode
from tech_cartography.runtime.live_artifact_paths import describe_live_artifact_storage
from tech_cartography.ui.live_artifact_storage_ui import should_show_live_artifact_storage_ui


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv(REQUIRE_LOGIN_ENV, raising=False)
  monkeypatch.setenv("APP_DEFAULT_MODE", "demo")


def test_settings_and_analyst_tabs_wire_storage_ui() -> None:
  settings = Path("src/tech_cartography/ui/user_settings_view.py").read_text(encoding="utf-8")
  analyst = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  assert "render_live_artifact_storage_expander" in settings
  assert "render_live_artifact_storage_expander" in analyst


def test_storage_ui_is_admin_only_and_has_no_secrets() -> None:
  text = Path("src/tech_cartography/ui/live_artifact_storage_ui.py").read_text(encoding="utf-8")
  assert "Live Artifact Storage（管理者向け）" in text
  assert "describe_live_artifact_storage" in text
  assert "Secret 値は表示しません" in text
  assert "os.environ" not in text
  assert "SMTP_PASSWORD" not in text


def test_demo_mode_hides_storage_ui(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("APP_DEFAULT_MODE", "demo")
  assert default_app_mode() == "demo"
  assert should_show_live_artifact_storage_ui() is False


def test_describe_storage_exposes_counts_not_credentials(tmp_path: Path) -> None:
  status = describe_live_artifact_storage(tmp_path)
  serialized = json.dumps(status)
  assert "artifact_counts" in status
  assert "API_KEY" not in serialized
  assert "PASSWORD" not in serialized


def test_docs_cover_phase25h() -> None:
  text = Path("docs/phase25h_live_artifact_persistence_cloud_storage.md").read_text(encoding="utf-8")
  assert "LIVE_OUTPUTS_ROOT" in text
  assert "Cloud Storage" in text
  assert "tech-cartography-v7-live" in text
  assert "Watch Expansion Proposal" in text
  assert "demo service" in text.lower() or "demo service" in text
