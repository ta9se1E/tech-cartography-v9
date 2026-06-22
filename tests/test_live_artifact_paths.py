"""Tests for live artifact path resolution (Phase 25H)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tech_cartography.runtime.live_artifact_paths import (
  LIVE_OUTPUTS_ROOT_ENV,
  describe_live_artifact_storage,
  ensure_live_artifact_dirs,
  get_live_digest_preview_dir,
  get_live_email_send_dir,
  get_live_outputs_root,
  get_live_web_signals_dir,
  using_live_outputs_root_env,
)
from tech_cartography.services.live_digest_preview import save_live_digest_preview
from tech_cartography.services.live_email_sender import save_live_email_send_log
from tech_cartography.services.live_web_signal_pack import save_live_web_signal_pack


@pytest.fixture(autouse=True)
def _clear_live_outputs_root(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv(LIVE_OUTPUTS_ROOT_ENV, raising=False)


def test_fallback_uses_project_outputs(tmp_path: Path) -> None:
  root = get_live_outputs_root(tmp_path)
  assert root == tmp_path / "outputs"
  assert get_live_web_signals_dir(tmp_path) == tmp_path / "outputs" / "live_web_signals"
  assert get_live_digest_preview_dir(tmp_path) == tmp_path / "outputs" / "live_digest_preview"
  assert get_live_email_send_dir(tmp_path) == tmp_path / "outputs" / "live_email_send"
  assert using_live_outputs_root_env() is False


def test_live_outputs_root_env_overrides_project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  custom = tmp_path / "mounted" / "outputs"
  monkeypatch.setenv(LIVE_OUTPUTS_ROOT_ENV, str(custom))
  assert get_live_outputs_root(tmp_path) == custom.resolve()
  assert get_live_web_signals_dir(tmp_path) == custom.resolve() / "live_web_signals"


def test_path_traversal_in_env_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(LIVE_OUTPUTS_ROOT_ENV, "../escape")
  with pytest.raises(ValueError, match="path traversal"):
    get_live_outputs_root(tmp_path)


def test_ensure_live_artifact_dirs_creates_writable_dirs(tmp_path: Path) -> None:
  ok, message = ensure_live_artifact_dirs(tmp_path)
  assert ok is True
  assert message is None
  for directory in (
    get_live_web_signals_dir(tmp_path),
    get_live_digest_preview_dir(tmp_path),
    get_live_email_send_dir(tmp_path),
  ):
    assert directory.is_dir()


def test_describe_live_artifact_storage_has_no_secrets(tmp_path: Path) -> None:
  os.environ["TAVILY_API_KEY"] = "super-secret-key-value"
  os.environ["SMTP_PASSWORD"] = "smtp-secret-password"
  try:
    status = describe_live_artifact_storage(tmp_path)
    serialized = json.dumps(status)
    assert "super-secret-key-value" not in serialized
    assert "smtp-secret-password" not in serialized
    assert "SMTP_PASSWORD" not in serialized
    assert "TAVILY_API_KEY" not in serialized
    assert status["live_outputs_root_env"] == "(unset — local outputs fallback)"
  finally:
    os.environ.pop("TAVILY_API_KEY", None)
    os.environ.pop("SMTP_PASSWORD", None)


def test_services_save_under_live_outputs_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  live_root = tmp_path / "live_root"
  monkeypatch.setenv(LIVE_OUTPUTS_ROOT_ENV, str(live_root))

  pack = {
    "theme_name": "Test",
    "query": "q",
    "fetched_at": "2026-06-18T00:00:00+00:00",
    "candidates": [],
    "next_actions": [],
  }
  pack_paths = save_live_web_signal_pack(pack, tmp_path / "project")
  assert str(live_root / "live_web_signals") in pack_paths["json"]

  preview = {
    "created_at": "2026-06-18T00:00:01+00:00",
    "markdown_body": "md",
    "plain_text_body": "txt",
    "subject": "subject",
  }
  preview_paths = save_live_digest_preview(preview, tmp_path / "project")
  assert str(live_root / "live_digest_preview") in preview_paths["json"]

  send_result = {
    "sent_at": "2026-06-18T00:00:02+00:00",
    "recipient_masked": "m***@example.com",
    "result_status": "sent",
    "preview_source_path": preview_paths["json"],
    "provider": "smtp",
    "send_mode": "self_only",
    "safety_notice": "safe",
  }
  send_paths = save_live_email_send_log(send_result, subject="subject", output_root=tmp_path / "project")
  assert str(live_root / "live_email_send") in send_paths["json"]


def test_save_fails_safely_when_not_writable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  live_root = tmp_path / "live_root"
  live_root.mkdir()
  monkeypatch.setenv(LIVE_OUTPUTS_ROOT_ENV, str(live_root))

  def deny_write(directory: Path) -> tuple[bool, str | None]:
    return False, f"{directory} is not writable (PermissionError)"

  monkeypatch.setattr(
    "tech_cartography.services.live_web_signal_pack.check_directory_writable",
    deny_write,
  )
  with pytest.raises(ValueError, match="not writable"):
    save_live_web_signal_pack(
      {
        "theme_name": "Test",
        "query": "q",
        "fetched_at": "2026-06-18T00:00:00+00:00",
        "candidates": [],
        "next_actions": [],
      },
      tmp_path,
    )
