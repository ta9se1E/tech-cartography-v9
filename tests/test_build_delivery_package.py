"""Tests for build_delivery_package CLI (Phase 24.0)."""

from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

from tech_cartography.delivery.store import build_delivery_package, dry_run_delivery_package

from tests.test_digest_diff import _write_snapshot_fixture

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_ROOT / "scripts" / "build_delivery_package.py"


def test_dry_run_no_output(tmp_path: Path) -> None:
  out = tmp_path / "outputs" / "delivery"
  result = dry_run_delivery_package("US-12565719-B2", tmp_path, out)
  assert result["planned_files"]
  assert not out.exists()


def test_build_package_creates_files(tmp_path: Path) -> None:
  _write_snapshot_fixture(tmp_path)
  out = tmp_path / "outputs" / "delivery"
  result = build_delivery_package(
    "US-12565719-B2",
    project_root=tmp_path,
    output_dir=out,
    include_zip=True,
  )
  assert (out / "overview_page.md").exists()
  assert (out / "intelligence_report_US-12565719-B2.md").exists()
  assert (out / "weekly_digest_preview_US-12565719-B2.md").exists()
  assert (out / "latest_snapshot.json").exists()
  assert result.is_initial_digest


def test_zip_bundle_created(tmp_path: Path) -> None:
  _write_snapshot_fixture(tmp_path)
  out = tmp_path / "outputs" / "delivery"
  build_delivery_package("US-12565719-B2", tmp_path, out, include_zip=True)
  zip_path = out / "tech_cartography_report_bundle_US-12565719-B2.zip"
  assert zip_path.exists()
  with zipfile.ZipFile(zip_path) as zf:
    names = zf.namelist()
    assert any("intelligence_report" in n for n in names)


def test_cli_dry_run_subprocess() -> None:
  proc = subprocess.run(
    [sys.executable, str(SCRIPT), "--publication-number", "US-12565719-B2", "--dry-run"],
    cwd=PROJECT_ROOT,
    capture_output=True,
    text=True,
    check=False,
  )
  assert proc.returncode == 0
  payload = json.loads(proc.stdout)
  assert payload["publication_number"] == "US-12565719-B2"
  assert "planned_files" in payload


def test_build_email_draft_creates_outbox_files(tmp_path: Path) -> None:
  _write_snapshot_fixture(tmp_path)
  out = tmp_path / "outputs" / "delivery"
  result = build_delivery_package(
    "US-12565719-B2",
    project_root=tmp_path,
    output_dir=out,
    include_zip=False,
    build_email_draft=True,
    email_to="reviewer@example.com",
    send_email=False,
  )
  assert result.email_draft is not None
  assert result.email_draft.status == "draft_saved"
  outbox = out / "email_outbox"
  assert (outbox / "email_draft_US-12565719-B2.json").exists()
  assert (outbox / "email_draft_US-12565719-B2.md").exists()
  assert "下書き保存済み" in (outbox / "email_draft_US-12565719-B2.md").read_text(encoding="utf-8")


def test_cli_email_draft_status_label_subprocess() -> None:
  proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "--publication-number",
      "US-12565719-B2",
      "--output-dir",
      "outputs/delivery",
      "--no-include-zip",
      "--build-email-draft",
      "--email-to",
      "reviewer@example.com",
    ],
    cwd=PROJECT_ROOT,
    capture_output=True,
    text=True,
    check=False,
  )
  assert proc.returncode == 0
  payload = json.loads(proc.stdout)
  assert payload["email_draft"]["status_label"] == "下書き保存済み"
  assert "メール草稿" in payload["email_draft"]["message"]


def test_send_email_without_smtp_blocked(tmp_path: Path, monkeypatch) -> None:
  for key in ("TC_SMTP_HOST", "TC_SMTP_PORT", "TC_SMTP_USER", "TC_SMTP_PASSWORD", "TC_SMTP_FROM"):
    monkeypatch.delenv(key, raising=False)
  _write_snapshot_fixture(tmp_path)
  out = tmp_path / "outputs" / "delivery"
  result = build_delivery_package(
    "US-12565719-B2",
    project_root=tmp_path,
    output_dir=out,
    include_zip=False,
    build_email_draft=True,
    email_to="reviewer@example.com",
    send_email=True,
  )
  assert result.email_draft is not None
  assert result.email_draft.status == "blocked_missing_adapter"
