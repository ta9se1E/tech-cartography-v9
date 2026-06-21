"""Tests for live beta release pack UI wiring (Phase 25L)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tech_cartography.auth.basic_auth import REQUIRE_LOGIN_ENV
from tech_cartography.runtime.cloud_run_config import default_app_mode
from tech_cartography.ui.live_beta_release_pack_ui import should_show_live_beta_release_pack_ui


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv(REQUIRE_LOGIN_ENV, raising=False)
  monkeypatch.setenv("APP_DEFAULT_MODE", "demo")


def test_reports_tab_wires_release_pack_ui() -> None:
  text = Path("src/tech_cartography/ui/v7_easy_app.py").read_text(encoding="utf-8")
  assert "render_live_beta_release_pack_section" in text


def test_settings_tab_wires_release_pack_ui() -> None:
  text = Path("src/tech_cartography/ui/user_settings_view.py").read_text(encoding="utf-8")
  assert "render_live_beta_release_pack_section" in text


def test_release_pack_ui_is_admin_only_without_secrets() -> None:
  text = Path("src/tech_cartography/ui/live_beta_release_pack_ui.py").read_text(encoding="utf-8")
  assert "Live Beta Release Pack（共有用）" in text
  assert "共有パックを作成" in text
  assert "Live Operation Console" in text
  assert "os.environ" not in text
  assert "SMTP_PASSWORD" not in text
  assert "TECH_CARTOGRAPHY_LOGIN_PASSWORD" not in text


def test_demo_mode_hides_release_pack_ui(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("APP_DEFAULT_MODE", "demo")
  assert default_app_mode() == "demo"
  assert should_show_live_beta_release_pack_ui() is False


def test_artifact_storage_shows_release_pack_count() -> None:
  text = Path("src/tech_cartography/ui/live_artifact_storage_ui.py").read_text(encoding="utf-8")
  assert "live_release_packs" in text
  assert "release_pack_dir" in text


def test_docs_cover_phase25l() -> None:
  text = Path("docs/phase25l_live_beta_release_pack.md").read_text(encoding="utf-8")
  assert "Phase 25K" in text
  assert "secret" in text.lower() or "機密" in text
  assert "live_release_pack" in text
