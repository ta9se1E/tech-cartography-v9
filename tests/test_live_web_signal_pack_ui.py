"""Tests for live Web Signal pack UI wiring (Phase 25E)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tech_cartography.auth.basic_auth import REQUIRE_LOGIN_ENV
from tech_cartography.runtime.cloud_run_config import default_app_mode
from tech_cartography.ui.live_web_signal_pack_ui import should_show_live_web_signal_pack_ui


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv(REQUIRE_LOGIN_ENV, raising=False)
  monkeypatch.setenv("APP_DEFAULT_MODE", "demo")


def test_analyst_input_wires_live_web_signal_pack_ui() -> None:
  text = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  assert "render_live_web_signal_pack_section" in text


def test_market_tab_wires_live_candidates_section() -> None:
  text = Path("src/tech_cartography/ui/v7_easy_app.py").read_text(encoding="utf-8")
  assert "render_live_web_signal_candidates_section" in text
  assert "Live Web Signal Candidates" in Path("src/tech_cartography/ui/live_web_signal_pack_ui.py").read_text(
    encoding="utf-8",
  )


def test_pack_ui_has_create_button_and_theme_name() -> None:
  text = Path("src/tech_cartography/ui/live_web_signal_pack_ui.py").read_text(encoding="utf-8")
  assert "Web Signal Packを作成" in text
  assert "theme_name" in text
  assert "APIキー本体は表示しません" in text
  assert "os.environ" not in text


def test_demo_mode_hides_admin_pack_ui(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("APP_DEFAULT_MODE", "demo")
  monkeypatch.delenv(REQUIRE_LOGIN_ENV, raising=False)
  assert default_app_mode() == "demo"
  assert should_show_live_web_signal_pack_ui() is False


def test_market_tab_does_not_break_demo_branch() -> None:
  text = Path("src/tech_cartography/ui/v7_easy_app.py").read_text(encoding="utf-8")
  demo_branch = text.split("if demo_mode:", 1)[1].split("web_review_artifacts = load_web_signal_review_artifacts", 1)[0]
  assert "render_live_web_signal_candidates_section" not in demo_branch


def test_docs_cover_phase25e() -> None:
  text = Path("docs/phase25e_live_tavily_web_signal_pack_integration.md").read_text(encoding="utf-8")
  assert "outputs/live_web_signals" in text
  assert "Web Signal candidate" in text
  assert "Phase 25D" in text
