"""Runtime smoke tests for auth status UI (Phase 25R.1)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tech_cartography.auth.basic_auth import REQUIRE_LOGIN_ENV


class _FakeExpander:
  def __enter__(self) -> "_FakeExpander":
    return self

  def __exit__(self, *_args: object) -> bool:
    return False


@pytest.fixture
def _stub_streamlit(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
  import tech_cartography.ui.auth_status_ui as auth_ui
  import tech_cartography.ui.email_operation_status_ui as email_ui

  fake_st = MagicMock()
  fake_st.expander.return_value = _FakeExpander()
  monkeypatch.setattr(auth_ui, "st", fake_st)
  monkeypatch.setattr(email_ui, "st", fake_st)
  monkeypatch.setattr(auth_ui, "should_show_auth_status_ui", lambda: True)
  monkeypatch.setattr(email_ui, "should_show_email_operation_status_ui", lambda: True)
  return fake_st


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(REQUIRE_LOGIN_ENV, "true")
  monkeypatch.setenv("APP_DEFAULT_MODE", "analyst")


def test_render_auth_status_expander_with_path(_stub_streamlit: MagicMock) -> None:
  from tech_cartography.ui.auth_status_ui import render_auth_status_expander

  render_auth_status_expander(project_root=Path("."), key="test_auth_status", expanded=False)


def test_render_auth_status_expander_with_none_project_root(_stub_streamlit: MagicMock) -> None:
  from tech_cartography.ui.auth_status_ui import render_auth_status_expander

  render_auth_status_expander(project_root=None, key="test_auth_status_none", expanded=False)


def test_render_auth_status_expander_iap_env(_stub_streamlit: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("AUTH_PROVIDER_MODE", "iap")
  monkeypatch.setenv("TECH_CARTOGRAPHY_ADMIN_EMAILS", "admin@example.com")
  monkeypatch.setenv("IAP_JWT_VERIFY_MODE", "off")
  from tech_cartography.ui.auth_status_ui import render_auth_status_expander

  render_auth_status_expander(project_root=Path("/workspace"), key="test_auth_status_iap", expanded=False)


def test_auth_status_ui_does_not_delete_project_root_before_use() -> None:
  text = Path("src/tech_cartography/ui/auth_status_ui.py").read_text(encoding="utf-8")
  assert "del project_root" not in text
  assert "key_prefix=" in text
  assert "render_email_operation_status_panel" in text


def test_auth_status_ui_has_no_secret_display() -> None:
  text = Path("src/tech_cartography/ui/auth_status_ui.py").read_text(encoding="utf-8")
  assert "SMTP_PASSWORD" not in text
  assert "TECH_CARTOGRAPHY_LOGIN_PASSWORD" not in text
