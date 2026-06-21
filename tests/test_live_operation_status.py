"""Tests for live operation status service (Phase 25K)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tech_cartography.runtime.cloud_run_config import DISABLE_EXTERNAL_API_ENV
from tech_cartography.runtime.live_artifact_paths import LIVE_OUTPUTS_ROOT_ENV
from tech_cartography.services.live_operation_status import (
  STEP_ORDER,
  build_and_save_operation_cycle_status,
  build_operation_cycle_status,
  save_operation_cycle_status,
)


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv(DISABLE_EXTERNAL_API_ENV, raising=False)
  monkeypatch.delenv("TAVILY_API_KEY", raising=False)


def test_empty_artifacts_all_steps_missing_or_ready(tmp_path: Path) -> None:
  status = build_operation_cycle_status(tmp_path)
  for step in STEP_ORDER:
    assert step in status["step_statuses"]
  assert status["step_statuses"]["web_signal_pack"]["status"] == "missing"
  assert status["step_statuses"]["next_cycle_web_signal_pack"]["status"] == "missing"
  assert status["next_recommended_action"]


def test_web_signal_pack_done(tmp_path: Path) -> None:
  pack_dir = tmp_path / "outputs" / "live_web_signals"
  pack_dir.mkdir(parents=True)
  pack_path = pack_dir / "live_web_signal_pack_20260621T120000.json"
  pack_path.write_text(
    json.dumps({"fetched_at": "2026-06-21T12:00:00+00:00", "candidates": []}),
    encoding="utf-8",
  )
  status = build_operation_cycle_status(tmp_path)
  assert status["step_statuses"]["web_signal_pack"]["status"] == "done"
  assert status["step_statuses"]["digest_preview"]["status"] == "ready"


def test_digest_preview_done(tmp_path: Path) -> None:
  digest_dir = tmp_path / "outputs" / "live_digest_preview"
  digest_dir.mkdir(parents=True)
  (digest_dir / "live_digest_preview_20260621T120000.json").write_text(
    json.dumps({"created_at": "2026-06-21T12:00:00+00:00"}),
    encoding="utf-8",
  )
  status = build_operation_cycle_status(tmp_path)
  assert status["step_statuses"]["digest_preview"]["status"] == "done"


def test_email_log_done(tmp_path: Path) -> None:
  email_dir = tmp_path / "outputs" / "live_email_send"
  email_dir.mkdir(parents=True)
  (email_dir / "live_email_send_20260621T120000.json").write_text(
    json.dumps({"sent_at": "2026-06-21T12:00:00+00:00", "recipient_masked": "a***@example.com"}),
    encoding="utf-8",
  )
  status = build_operation_cycle_status(tmp_path)
  assert status["step_statuses"]["self_only_email"]["status"] == "done"


def test_watch_profile_draft_done(tmp_path: Path) -> None:
  profiles_dir = tmp_path / "outputs" / "live_watch_profiles"
  profiles_dir.mkdir(parents=True)
  (profiles_dir / "watch_profile_draft_20260621T150932+0000.json").write_text(
    json.dumps(
      {
        "theme_name": "Theme",
        "approved_keywords": ["PAN"],
        "approved_by": "admin",
        "approved_at": "2026-06-21T15:09:32+00:00",
      },
    ),
    encoding="utf-8",
  )
  status = build_operation_cycle_status(tmp_path)
  assert status["step_statuses"]["watch_profile_draft"]["status"] == "done"


def test_next_cycle_plan_done_pack_missing_ready(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "true")
  plan_dir = tmp_path / "outputs" / "live_next_cycle_search"
  plan_dir.mkdir(parents=True)
  (plan_dir / "next_cycle_search_plan_20260621T120000.json").write_text(
    json.dumps({"created_at": "2026-06-21T12:00:00+00:00", "query_candidates": []}),
    encoding="utf-8",
  )
  status = build_operation_cycle_status(tmp_path)
  assert status["step_statuses"]["next_cycle_search_plan"]["status"] == "done"
  assert status["step_statuses"]["next_cycle_web_signal_pack"]["status"] == "ready"
  assert "外部API" in status["step_statuses"]["next_cycle_web_signal_pack"]["next_action"]


def test_status_save_under_live_outputs_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  live_root = tmp_path / "live_root"
  monkeypatch.setenv(LIVE_OUTPUTS_ROOT_ENV, str(live_root))
  status, saved, error = build_and_save_operation_cycle_status(tmp_path / "project")
  assert error is None
  assert saved is not None
  assert str(live_root / "live_operation_status") in saved["json"]
  serialized = json.dumps(status)
  assert "SMTP_PASSWORD" not in serialized
  assert "API_KEY" not in serialized


def test_save_operation_status_excludes_secrets(tmp_path: Path) -> None:
  status = build_operation_cycle_status(tmp_path)
  saved = save_operation_cycle_status(status, tmp_path)
  payload = json.loads(Path(saved["json"]).read_text(encoding="utf-8"))
  serialized = json.dumps(payload)
  assert "smtp_password" not in serialized.lower()
