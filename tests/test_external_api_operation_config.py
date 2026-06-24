"""Tests for external API operation config (Phase 25T)."""

from __future__ import annotations

import pytest

from tech_cartography.runtime.cloud_run_config import DISABLE_EXTERNAL_API_ENV
from tech_cartography.runtime.external_api_operation_config import (
  ENABLE_MANUAL_WEB_SIGNAL_COLLECTION_ENV,
  evaluate_manual_web_signal_collection,
  get_web_signal_collection_confirmation_text,
  get_web_signal_max_queries,
  get_web_signal_max_results_per_query,
  is_manual_web_signal_collection_enabled,
)


def test_default_manual_collection_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv(ENABLE_MANUAL_WEB_SIGNAL_COLLECTION_ENV, raising=False)
  assert is_manual_web_signal_collection_enabled() is False


def test_disable_external_api_blocks_collection(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(ENABLE_MANUAL_WEB_SIGNAL_COLLECTION_ENV, "true")
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "true")
  allowed, reason, _ = evaluate_manual_web_signal_collection(
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    confirm_text=get_web_signal_collection_confirmation_text(),
    has_active_watch_profile=True,
  )
  assert allowed is False
  assert reason == "external_api_disabled"


def test_manual_flag_off_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "false")
  monkeypatch.setenv(ENABLE_MANUAL_WEB_SIGNAL_COLLECTION_ENV, "false")
  allowed, reason, _ = evaluate_manual_web_signal_collection(
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    confirm_text=get_web_signal_collection_confirmation_text(),
    has_active_watch_profile=True,
  )
  assert allowed is False
  assert reason == "manual_collection_disabled"


def test_max_limits_are_small(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv("WEB_SIGNAL_MAX_QUERIES", raising=False)
  monkeypatch.delenv("WEB_SIGNAL_MAX_RESULTS_PER_QUERY", raising=False)
  assert get_web_signal_max_queries() <= 5
  assert get_web_signal_max_results_per_query() <= 10
