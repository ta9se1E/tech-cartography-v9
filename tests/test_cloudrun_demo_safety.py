"""Tests for Cloud Run demo safety flags (Phase 24.6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tech_cartography.delivery.email_sender import can_send_email
from tech_cartography.runtime.cloud_run_config import (
  APP_DEFAULT_MODE_ENV,
  DISABLE_EMAIL_SEND_ENV,
  DISABLE_EXTERNAL_API_ENV,
  DISABLE_SCHEDULER_ENV,
  default_app_mode,
  is_email_send_disabled,
  is_external_api_disabled,
  is_scheduler_disabled,
  missing_demo_output_paths,
)
from tech_cartography.ui.developer_mode_visibility import (
  SHOW_DEVELOPER_MODE_ENV,
  is_show_developer_mode_enabled,
)
from tech_cartography.ui.streamlit_session import default_app_session_state

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _clear_cloud_run_env(monkeypatch: pytest.MonkeyPatch) -> None:
  for key in (
    APP_DEFAULT_MODE_ENV,
    DISABLE_EXTERNAL_API_ENV,
    DISABLE_EMAIL_SEND_ENV,
    DISABLE_SCHEDULER_ENV,
    SHOW_DEVELOPER_MODE_ENV,
  ):
    monkeypatch.delenv(key, raising=False)


def test_default_app_mode_demo() -> None:
  assert default_app_mode() == "demo"


def test_app_default_mode_env_respected(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(APP_DEFAULT_MODE_ENV, "analyst")
  assert default_app_mode() == "analyst"


def test_default_session_state_demo_mode() -> None:
  state = default_app_session_state()
  assert state["ui_view_mode"] == "demo"
  assert state["demo_mode_enabled"] is True
  assert state["demo_publication_number"] == "US-12565719-B2"


def test_disable_external_api_flag(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "true")
  assert is_external_api_disabled() is True


def test_disable_email_send_blocks_can_send(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EMAIL_SEND_ENV, "true")
  monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
  monkeypatch.setenv("SMTP_PORT", "587")
  monkeypatch.setenv("SMTP_USER", "user@example.com")
  monkeypatch.setenv("SMTP_PASSWORD", "secret")
  monkeypatch.setenv("SMTP_FROM", "user@example.com")
  assert is_email_send_disabled() is True
  ready, reason = can_send_email()
  assert ready is False
  assert "DISABLE_EMAIL_SEND" in reason


def test_disable_scheduler_flag(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_SCHEDULER_ENV, "true")
  assert is_scheduler_disabled() is True


def test_developer_mode_hidden_without_env() -> None:
  assert is_show_developer_mode_enabled() is False


def test_demo_outputs_manifest_paths_exist() -> None:
  missing = missing_demo_output_paths(PROJECT_ROOT)
  assert not missing, missing


def test_theme_validation_locks_external_api(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "true")
  text = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  section = text.split("external_api_locked = is_external_api_disabled()", 1)[1].split(
    "actions_enabled = seeds_ready",
    1,
  )[0]
  assert "allow_external_api = False" in section
  assert "run_openalex = False" in section


def test_delivery_ui_scheduler_guard() -> None:
  text = Path("src/tech_cartography/ui/delivery_ui.py").read_text(encoding="utf-8")
  fn = text.split("def render_weekly_schedule_section", 1)[1].split("def ", 1)[0]
  assert "is_scheduler_disabled()" in fn
