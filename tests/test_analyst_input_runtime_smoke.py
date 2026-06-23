"""Runtime smoke tests for analyst input section (Phase 25R.1)."""

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


def test_analyst_input_wires_auth_status_with_project_root() -> None:
  text = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  assert "render_auth_status_expander(project_root=_project_root()" in text


def test_project_root_resolves_under_workspace() -> None:
  from tech_cartography.ui.theme_validation_ui import _project_root

  root = _project_root()
  assert root.is_dir()
  assert (root / "src" / "tech_cartography").is_dir()


def test_auth_status_via_theme_project_root(_stub_streamlit: MagicMock) -> None:
  from tech_cartography.ui.auth_status_ui import render_auth_status_expander
  from tech_cartography.ui.theme_validation_ui import _project_root

  render_auth_status_expander(
    project_root=_project_root(),
    key="runtime_smoke_analyst_auth_status",
    expanded=False,
  )
