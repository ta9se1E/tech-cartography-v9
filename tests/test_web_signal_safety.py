"""Safety guards for web signal collector (Phase 25T)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tech_cartography.services.live_web_signal_collector import _assert_safe_serialized

COLLECTOR_PATH = Path(__file__).resolve().parents[1] / "src/tech_cartography/services/live_web_signal_collector.py"
CLOUDBUILD = Path(__file__).resolve().parents[1] / "cloudbuild.yaml"
DEPLOY = Path(__file__).resolve().parents[1] / "scripts/deploy_live_safe.sh"

FORBIDDEN_IN_COLLECTOR = ("smtplib", "send_email", "cloudscheduler", "scheduler.start")


def test_collector_source_has_no_email_or_scheduler() -> None:
  text = COLLECTOR_PATH.read_text(encoding="utf-8").lower()
  for token in FORBIDDEN_IN_COLLECTOR:
    assert token not in text


def test_serialized_artifact_guard_allows_safe_metadata() -> None:
  _assert_safe_serialized('{"skipped_reason":"missing_tavily_key","confidence_label":"candidate"}')


def test_serialized_artifact_guard_blocks_leaked_key_values() -> None:
  with pytest.raises(ValueError):
    _assert_safe_serialized('{"detail":"api_key=super-leaked-value"}')


def test_deploy_defaults_keep_collection_disabled() -> None:
  assert "ENABLE_MANUAL_WEB_SIGNAL_COLLECTION=false" in CLOUDBUILD.read_text(encoding="utf-8")
  assert "DISABLE_EXTERNAL_API=true" in CLOUDBUILD.read_text(encoding="utf-8")
  assert "ENABLE_MANUAL_WEB_SIGNAL_COLLECTION=false" in DEPLOY.read_text(encoding="utf-8")
