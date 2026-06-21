"""Tests for watch expansion UI wiring (Phase 25I)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tech_cartography.auth.basic_auth import REQUIRE_LOGIN_ENV
from tech_cartography.runtime.cloud_run_config import default_app_mode
from tech_cartography.ui.live_watch_expansion_ui import should_show_live_watch_expansion_ui


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv(REQUIRE_LOGIN_ENV, raising=False)
  monkeypatch.setenv("APP_DEFAULT_MODE", "demo")


def test_analyst_input_wires_draft_visibility_after_expansion() -> None:
  analyst = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  expansion = Path("src/tech_cartography/ui/live_watch_expansion_ui.py").read_text(encoding="utf-8")
  assert "render_live_watch_expansion_section" in analyst
  assert "render_watch_profile_draft_reports_section" in expansion


def test_reports_and_settings_wire_draft_section() -> None:
  reports = Path("src/tech_cartography/ui/v7_easy_app.py").read_text(encoding="utf-8")
  settings = Path("src/tech_cartography/ui/user_settings_view.py").read_text(encoding="utf-8")
  assert "render_watch_profile_draft_reports_section" in reports
  assert "render_watch_profile_draft_reports_section" in settings


def test_watch_expansion_ui_is_admin_only_without_secrets() -> None:
  text = Path("src/tech_cartography/ui/live_watch_expansion_ui.py").read_text(encoding="utf-8")
  assert "Watch Expansion Proposals（承認前）" in text
  assert "監視範囲の拡張候補を作成" in text
  assert "Approved Watch Profile Draft（人間承認済み）" in text
  assert "Watch Profile Draft Storage（管理者向け）" in text
  assert "resolve_watch_profile_draft_status" in text
  assert "source file path" in text
  assert "os.environ" not in text
  assert "SMTP_PASSWORD" not in text
  assert "infringement confirmed" not in text.lower()


def test_demo_mode_hides_watch_expansion_ui(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("APP_DEFAULT_MODE", "demo")
  assert default_app_mode() == "demo"
  assert should_show_live_watch_expansion_ui() is False


def test_docs_cover_phase25i() -> None:
  text = Path("docs/phase25i_human_approved_watch_expansion_proposal.md").read_text(encoding="utf-8")
  assert "Phase 25H" in text
  assert "pending_human_review" in text
  assert "live_watch_expansion" in text
  assert "live_watch_profiles" in text
  assert "週次運用" in text
