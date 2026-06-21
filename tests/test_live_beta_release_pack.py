"""Tests for live beta release pack service (Phase 25L)."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from tech_cartography.runtime.live_artifact_paths import LIVE_OUTPUTS_ROOT_ENV, get_live_release_pack_dir
from tech_cartography.services.live_beta_release_pack import (
  build_and_save_live_beta_release_pack,
  build_known_limitations_text,
  build_live_beta_release_pack,
  build_stakeholder_share_message,
  build_three_min_demo_script,
  save_live_beta_release_pack,
)
from tech_cartography.services.live_operation_status import save_operation_cycle_status


@pytest.fixture(autouse=True)
def _clear_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv("TECH_CARTOGRAPHY_LOGIN_PASSWORD", raising=False)
  monkeypatch.delenv("SMTP_PASSWORD", raising=False)
  monkeypatch.delenv("TAVILY_API_KEY", raising=False)


def test_build_from_latest_operation_status(tmp_path: Path) -> None:
  status_dir = tmp_path / "outputs" / "live_operation_status"
  status_dir.mkdir(parents=True)
  status = {
    "cycle_id": "cycle-1",
    "checked_at": "2026-06-21T12:00:00+00:00",
    "next_recommended_action": "Create digest preview",
    "step_statuses": {},
    "warnings": [],
    "safety_notice": "manual only",
  }
  save_operation_cycle_status(status, tmp_path)

  pack = build_live_beta_release_pack(tmp_path)
  assert pack["latest_operation_status"]["status"] == "ok"
  assert pack["latest_operation_status"]["next_recommended_action"] == "Create digest preview"


def test_build_without_operation_status_is_safe(tmp_path: Path) -> None:
  pack = build_live_beta_release_pack(tmp_path)
  assert pack["latest_operation_status"]["status"] == "missing"
  assert pack["release_pack_id"]
  assert pack["stakeholder_share_message"]


def test_save_under_live_outputs_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  live_root = tmp_path / "live_outputs"
  monkeypatch.setenv(LIVE_OUTPUTS_ROOT_ENV, str(live_root))
  pack, saved, error = build_and_save_live_beta_release_pack(tmp_path, release_note="beta handoff")
  assert error is None
  assert saved is not None
  assert str(get_live_release_pack_dir(tmp_path)).startswith(str(live_root))
  for key in ("json", "markdown", "text", "zip"):
    assert saved[key]
    assert Path(saved[key]).exists()


def test_generates_json_md_txt_and_zip(tmp_path: Path) -> None:
  pack = build_live_beta_release_pack(tmp_path)
  saved = save_live_beta_release_pack(pack, tmp_path)
  assert saved["json"].endswith(".json")
  assert saved["markdown"].endswith(".md")
  assert saved["text"].endswith(".txt")
  assert saved["zip"].endswith(".zip")


def test_zip_contains_required_files(tmp_path: Path) -> None:
  pack = build_live_beta_release_pack(tmp_path)
  saved = save_live_beta_release_pack(pack, tmp_path)
  with zipfile.ZipFile(saved["zip"]) as archive:
    names = set(archive.namelist())
  assert names == {
    "README.md",
    "demo_script_3min.txt",
    "stakeholder_share_message.txt",
    "known_limitations_and_scope.txt",
    "admin_operation_checklist.txt",
    "release_pack.json",
  }


def test_no_api_keys_or_smtp_in_output(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  monkeypatch.setenv("TECH_CARTOGRAPHY_LOGIN_PASSWORD", "super-secret-login-value")
  monkeypatch.setenv("SMTP_PASSWORD", "super-secret-smtp-value")
  monkeypatch.setenv("TAVILY_API_KEY", "tvly-super-secret")
  pack, saved, error = build_and_save_live_beta_release_pack(tmp_path)
  assert error is None
  blob = json.dumps(pack)
  for key, path in (saved or {}).items():
    if key == "zip":
      with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
          blob += archive.read(name).decode("utf-8")
      continue
    blob += Path(path).read_text(encoding="utf-8")
  assert "super-secret-login-value" not in blob
  assert "super-secret-smtp-value" not in blob
  assert "tvly-super-secret" not in blob
  assert "TECH_CARTOGRAPHY_LOGIN_PASSWORD" not in blob
  assert "SMTP_PASSWORD" not in blob


def test_stakeholder_message_generated() -> None:
  message = build_stakeholder_share_message(
    service_name="tech-cartography-v7-live",
    service_url="https://example.run.app",
  )
  assert "Live Beta" in message
  assert "ログイン情報は別途" in message
  assert "法的判断" in message


def test_three_min_demo_script_generated() -> None:
  script = build_three_min_demo_script()
  assert "0:00-0:30" in script
  assert "候補" in script
  assert "人間承認" in script or "人間が" in script


def test_known_limitations_include_safety_text() -> None:
  text = build_known_limitations_text()
  for token in (
    "Web Signal",
    "FTO",
    "self_only",
    "scheduler",
    "外部 API",
    "手動運用",
    "限定公開",
  ):
    assert token in text


def test_release_note_included_without_secrets(tmp_path: Path) -> None:
  pack = build_live_beta_release_pack(tmp_path, release_note="今週は digest まで確認済み")
  assert pack["release_note"] == "今週は digest まで確認済み"
