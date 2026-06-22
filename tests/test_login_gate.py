"""Tests for Streamlit login gate wiring (Phase 25A)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tech_cartography.auth.basic_auth import REQUIRE_LOGIN_ENV, is_login_required
from tech_cartography.ui.login_ui import (
  STATE_AUTH_AUTHENTICATED,
  STATE_AUTH_DISPLAY_NAME,
  STATE_AUTH_ROLE,
  STATE_AUTH_USERNAME,
  build_app_user_from_basic_auth,
)

APP_PY = Path("app.py")


@pytest.fixture(autouse=True)
def _clear_require_login(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv(REQUIRE_LOGIN_ENV, raising=False)


def test_is_login_required_default_false() -> None:
  assert is_login_required() is False


def test_is_login_required_true(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(REQUIRE_LOGIN_ENV, "true")
  assert is_login_required() is True


def test_app_entry_has_auth_login_gate_branch() -> None:
  text = APP_PY.read_text(encoding="utf-8")
  assert "is_login_required()" in text
  assert "require_auth_login_gate" in text
  assert "build_app_user_from_auth_session" in text
  assert "require_login()" in text


def test_demo_mode_uses_email_login_when_gate_disabled() -> None:
  text = APP_PY.read_text(encoding="utf-8")
  branch = text.split("if is_login_required():", 1)[1].split("init_app_session_state", 1)[0]
  assert "require_login()" in branch.split("else:", 1)[1]


def test_auth_session_keys_defined() -> None:
  assert STATE_AUTH_AUTHENTICATED == "tc_basic_auth_authenticated"
  assert STATE_AUTH_USERNAME == "tc_basic_auth_username"
  assert STATE_AUTH_ROLE == "tc_basic_auth_role"
  assert STATE_AUTH_DISPLAY_NAME == "tc_basic_auth_display_name"


def test_build_app_user_from_basic_auth_preserves_role() -> None:
  user = build_app_user_from_basic_auth(
    {
      "username": "admin",
      "role": "admin",
      "display_name": "Admin User",
    },
  )
  assert user["username"] == "admin"
  assert user["auth_role"] == "admin"
  assert user["display_name"] == "Admin User"


def test_env_example_documents_login_gate() -> None:
  text = Path(".env.example").read_text(encoding="utf-8")
  assert "REQUIRE_LOGIN=false" in text
  assert "REQUIRE_LOGIN=true" in text
  assert "TECH_CARTOGRAPHY_LOGIN_USERNAME=admin" in text
  assert "TECH_CARTOGRAPHY_LOGIN_PASSWORD=" in text
  assert "TECH_CARTOGRAPHY_USERS_JSON" in text


def test_login_ui_uses_simple_login_error_message() -> None:
  text = Path("src/tech_cartography/ui/login_ui.py").read_text(encoding="utf-8")
  assert "Tech Cartography Live Beta" in text
  assert "ユーザー名またはパスワードが違います" in text
  assert "TECH_CARTOGRAPHY_LOGIN_PASSWORD" not in text.split("render_warning_box", 1)[0]
