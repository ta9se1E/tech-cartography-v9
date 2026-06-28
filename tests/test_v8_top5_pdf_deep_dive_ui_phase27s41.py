"""Smoke tests for Phase27S.4.1 Top5 PDF deep dive UI."""

from __future__ import annotations

import importlib
from unittest.mock import patch

import pytest


def test_deep_dive_ui_importable() -> None:
  mod = importlib.import_module("tech_cartography.ui.v8_top5_pdf_deep_dive_ui")
  assert hasattr(mod, "render_top5_pdf_deep_dive_section")
  assert callable(mod.render_top5_pdf_deep_dive_section)


def test_deep_dive_ui_import_with_gemini_off() -> None:
  with patch(
    "tech_cartography.services.v8_llm_provider_gemini.is_gemini_example_facts_enabled",
    return_value=False,
  ):
    mod = importlib.import_module("tech_cartography.ui.v8_top5_pdf_deep_dive_ui")
    assert mod is not None
