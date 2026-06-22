"""Tests for IAP cutover status UI wiring (Phase 25O)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tech_cartography.auth.basic_auth import REQUIRE_LOGIN_ENV
from tech_cartography.runtime.cloud_run_config import default_app_mode
from tech_cartography.ui.iap_cutover_status_ui import should_show_iap_cutover_status_ui


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv(REQUIRE_LOGIN_ENV, raising=False)
  monkeypatch.setenv("APP_DEFAULT_MODE", "demo")


def test_settings_tab_wires_iap_cutover_status_ui() -> None:
  text = Path("src/tech_cartography/ui/user_settings_view.py").read_text(encoding="utf-8")
  assert "render_iap_cutover_status_expander" in text


def test_iap_cutover_status_ui_has_no_secrets() -> None:
  text = Path("src/tech_cartography/ui/iap_cutover_status_ui.py").read_text(encoding="utf-8")
  assert "IAP Cutover Status（管理者向け）" in text
  assert "cutover checklist" in text
  assert "SMTP_PASSWORD" not in text
  assert "TECH_CARTOGRAPHY_LOGIN_PASSWORD" not in text
  assert "TECH_CARTOGRAPHY_USERS_JSON" not in text
  assert "password_hash" not in text


def test_demo_mode_hides_iap_cutover_status_ui(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("APP_DEFAULT_MODE", "demo")
  assert default_app_mode() == "demo"
  assert should_show_iap_cutover_status_ui() is False


def test_docs_cover_phase25o() -> None:
  text = Path("docs/phase25o_cloud_run_iap_cutover_runbook.md").read_text(encoding="utf-8")
  assert "check_iap_cutover_ready.py" in text
  assert "hybrid" in text
