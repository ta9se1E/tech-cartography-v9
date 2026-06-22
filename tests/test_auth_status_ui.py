"""Tests for auth status UI wiring (Phase 25N)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tech_cartography.auth.basic_auth import REQUIRE_LOGIN_ENV
from tech_cartography.runtime.cloud_run_config import default_app_mode
from tech_cartography.ui.auth_status_ui import should_show_auth_status_ui


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv(REQUIRE_LOGIN_ENV, raising=False)
  monkeypatch.setenv("APP_DEFAULT_MODE", "demo")


def test_settings_tab_wires_auth_status_ui() -> None:
  text = Path("src/tech_cartography/ui/user_settings_view.py").read_text(encoding="utf-8")
  assert "render_auth_status_expander" in text


def test_input_tab_wires_auth_status_ui() -> None:
  text = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  assert "render_auth_status_expander" in text


def test_auth_status_ui_has_no_secrets() -> None:
  text = Path("src/tech_cartography/ui/auth_status_ui.py").read_text(encoding="utf-8")
  assert "Authentication Status（管理者向け）" in text
  assert "AUTH_PROVIDER_MODE" in text
  assert "SMTP_PASSWORD" not in text
  assert "TECH_CARTOGRAPHY_LOGIN_PASSWORD" not in text
  assert "TECH_CARTOGRAPHY_USERS_JSON" not in text
  assert "password_hash" not in text


def test_demo_mode_hides_auth_status_ui(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("APP_DEFAULT_MODE", "demo")
  assert default_app_mode() == "demo"
  assert should_show_auth_status_ui() is False


def test_docs_cover_phase25n() -> None:
  text = Path("docs/phase25n_google_iap_ready_auth_bridge.md").read_text(encoding="utf-8")
  assert "AUTH_PROVIDER_MODE" in text
  assert "google_iap" in text
