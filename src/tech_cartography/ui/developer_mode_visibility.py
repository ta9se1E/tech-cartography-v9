"""Developer mode visibility for Cloud Run submission (Phase 24.5E)."""

from __future__ import annotations

import os

SHOW_DEVELOPER_MODE_ENV = "SHOW_DEVELOPER_MODE"

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def is_show_developer_mode_enabled() -> bool:
  """Return True only when SHOW_DEVELOPER_MODE is explicitly truthy."""
  value = os.environ.get(SHOW_DEVELOPER_MODE_ENV, "").strip().lower()
  return value in _TRUTHY


def developer_mode_hidden_notice() -> str:
  return "開発者向け情報は提出用画面では非表示です。"
