"""Runtime smoke tests for v7_easy_app entrypoints (Phase 25R.1)."""

from __future__ import annotations


def test_v7_easy_app_imports() -> None:
  import tech_cartography.ui.v7_easy_app as app

  assert hasattr(app, "render_analyst_input_execution_section")


def test_auth_status_expander_signature_accepts_optional_root() -> None:
  import inspect

  from tech_cartography.ui.auth_status_ui import render_auth_status_expander

  sig = inspect.signature(render_auth_status_expander)
  param = sig.parameters["project_root"]
  assert param.default is not inspect.Parameter.empty or param.annotation != inspect.Parameter.empty
