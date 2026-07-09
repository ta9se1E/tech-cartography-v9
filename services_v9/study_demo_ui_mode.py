"""UI mode resolution for Study Demo progressive disclosure."""

from __future__ import annotations

import os
from typing import Mapping

UI_MODE_SIMPLE = "simple"
UI_MODE_ADVANCED = "advanced"
UI_MODE_ENV = "V9_UI_MODE"


def resolve_ui_mode(environ: Mapping[str, str] | None = None) -> str:
  env = environ if environ is not None else os.environ
  from services_v9.study_demo_access import is_public_demo

  if is_public_demo(env):
    return UI_MODE_SIMPLE
  value = str(env.get(UI_MODE_ENV, UI_MODE_SIMPLE) or UI_MODE_SIMPLE).strip().lower()
  if value == UI_MODE_ADVANCED:
    return UI_MODE_ADVANCED
  return UI_MODE_SIMPLE


def is_simple_mode(environ: Mapping[str, str] | None = None) -> bool:
  return resolve_ui_mode(environ) == UI_MODE_SIMPLE


def is_advanced_mode(environ: Mapping[str, str] | None = None) -> bool:
  return resolve_ui_mode(environ) == UI_MODE_ADVANCED


def should_show_technical_ids(environ: Mapping[str, str] | None = None) -> bool:
  return is_advanced_mode(environ)


def should_show_legacy_tools(environ: Mapping[str, str] | None = None) -> bool:
  return is_advanced_mode(environ)


def should_show_full_signal_details(environ: Mapping[str, str] | None = None) -> bool:
  return is_advanced_mode(environ)


def is_study_demo_simple_ui(environ: Mapping[str, str] | None = None) -> bool:
  from services_v9.study_demo_config import is_study_demo_mode

  return is_study_demo_mode(environ) and is_simple_mode(environ)


__all__ = [
  "UI_MODE_ADVANCED",
  "UI_MODE_ENV",
  "UI_MODE_SIMPLE",
  "is_advanced_mode",
  "is_simple_mode",
  "is_study_demo_simple_ui",
  "resolve_ui_mode",
  "should_show_full_signal_details",
  "should_show_legacy_tools",
  "should_show_technical_ids",
]
