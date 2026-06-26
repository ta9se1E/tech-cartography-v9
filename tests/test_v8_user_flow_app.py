"""Tests for v8_user_flow_app (Phase 27B)."""

from __future__ import annotations

from tech_cartography.ui import v8_user_flow_app
from tech_cartography.ui.v8_tab_config import V8_TAB_IDS


def test_v8_user_flow_app_imports() -> None:
  assert callable(v8_user_flow_app.render_v8_user_flow_app)
  assert v8_user_flow_app.PROJECT_ROOT.exists()


def test_v8_user_flow_app_has_all_tab_renderers() -> None:
  renderers = v8_user_flow_app._TAB_RENDERERS
  assert set(renderers) == set(V8_TAB_IDS)


def test_app_py_defaults_to_v8() -> None:
  app_text = (v8_user_flow_app.PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
  assert "APP_UI_VERSION" in app_text
  assert "render_v8_user_flow_app" in app_text
  assert 'DEFAULT_UI_VERSION = "v8"' in app_text
