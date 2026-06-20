"""Tests for delivery UI loader (Phase 24.0)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.delivery.store import build_delivery_package
from tech_cartography.delivery.japanese_copy import ja_ui_send_disabled_notice
from tech_cartography.ui.delivery_ui import (
  collect_download_keys_for_artifacts,
  load_delivery_artifacts,
  make_download_key,
  normalize_key_part,
)


def test_missing_delivery_loader(tmp_path: Path) -> None:
  artifacts = load_delivery_artifacts(tmp_path)
  assert artifacts.status == "missing"
  assert artifacts.publication_number == "unknown"
  assert len(artifacts.tab_overviews) == 7


def test_loader_reads_package(tmp_path: Path) -> None:
  from tests.test_digest_diff import _write_snapshot_fixture

  _write_snapshot_fixture(tmp_path)
  build_delivery_package(
    "US-12565719-B2",
    project_root=tmp_path,
    output_dir=tmp_path / "outputs" / "delivery",
    include_zip=True,
  )
  artifacts = load_delivery_artifacts(tmp_path, publication_number="US-12565719-B2")
  assert artifacts.status in {"ready", "partial"}
  assert artifacts.intelligence_report_md
  assert artifacts.weekly_digest_md
  assert "プレビューのみ" in (artifacts.weekly_digest_md or "")


def test_loader_missing_zip_graceful(tmp_path: Path) -> None:
  from tests.test_digest_diff import _write_snapshot_fixture

  _write_snapshot_fixture(tmp_path)
  build_delivery_package(
    "US-12565719-B2",
    project_root=tmp_path,
    output_dir=tmp_path / "outputs" / "delivery",
    include_zip=False,
  )
  artifacts = load_delivery_artifacts(tmp_path, publication_number="US-12565719-B2")
  assert artifacts.report_zip_path is None


def test_normalize_key_part_none() -> None:
  assert normalize_key_part(None) == "none"


def test_normalize_key_part_slashes_and_spaces() -> None:
  assert normalize_key_part("US-12565719-B2") == "US-12565719-B2"
  assert "/" not in normalize_key_part("a/b\\c.d: e")
  assert " " not in normalize_key_part("hello world")


def test_make_download_key_same_prefix_different_path() -> None:
  path_a = Path("/tmp/intelligence_report_US-12565719-B2.md")
  path_b = Path("/tmp/weekly_digest_preview_US-12565719-B2.md")
  key_a = make_download_key("dl_report", "US-12565719-B2", path_a)
  key_b = make_download_key("dl_report", "US-12565719-B2", path_b)
  assert key_a != key_b


def test_make_download_key_publication_number_safe() -> None:
  key = make_download_key("prefix", "US-12565719-B2", Path("file.md"))
  assert "US-12565719-B2" in key
  assert "prefix" in key


def test_make_download_key_none_publication() -> None:
  key = make_download_key("prefix", None, Path("file.md"))
  assert "unknown" in key


def test_collect_download_keys_all_unique(tmp_path: Path) -> None:
  from tests.test_digest_diff import _write_snapshot_fixture

  _write_snapshot_fixture(tmp_path)
  build_delivery_package(
    "US-12565719-B2",
    project_root=tmp_path,
    output_dir=tmp_path / "outputs" / "delivery",
    include_zip=True,
    build_email_draft=True,
    email_to="reviewer@example.com",
  )
  artifacts = load_delivery_artifacts(tmp_path, publication_number="US-12565719-B2")
  keys_reports = collect_download_keys_for_artifacts(artifacts, key_prefix="reports_delivery")
  keys_start = collect_download_keys_for_artifacts(artifacts, key_prefix="start_delivery")
  assert len(keys_reports) == len(set(keys_reports))
  assert len(keys_start) == len(set(keys_start))
  assert keys_reports != keys_start


def test_collect_download_keys_no_duplicates_within_prefix() -> None:
  artifacts = load_delivery_artifacts(Path("/nonexistent"), publication_number="US-TEST")
  keys = collect_download_keys_for_artifacts(artifacts, key_prefix="reports_delivery")
  assert len(keys) == len(set(keys))
  assert len(keys) == 8


def test_loader_reads_email_draft(tmp_path: Path) -> None:
  from tests.test_digest_diff import _write_snapshot_fixture

  _write_snapshot_fixture(tmp_path)
  build_delivery_package(
    "US-12565719-B2",
    project_root=tmp_path,
    output_dir=tmp_path / "outputs" / "delivery",
    include_zip=False,
    build_email_draft=True,
    email_to="reviewer@example.com",
  )
  artifacts = load_delivery_artifacts(tmp_path, publication_number="US-12565719-B2")
  assert artifacts.email_draft is not None
  assert artifacts.email_draft_md
  assert artifacts.email_draft.status == "draft_saved"


def test_loader_scheduler_missing_without_crash(tmp_path: Path) -> None:
  artifacts = load_delivery_artifacts(tmp_path, publication_number="US-12565719-B2")
  assert artifacts.scheduler_readme_md is None
  assert artifacts.wrapper_script_path is None


def test_loader_send_log_without_crash(tmp_path: Path) -> None:
  from tech_cartography.delivery.send_log import EmailSendLog, save_send_log

  ddir = tmp_path / "outputs" / "delivery"
  save_send_log(
    EmailSendLog(
      log_id="log-1",
      created_at="2026-06-20T00:00:00+00:00",
      publication_number="US-12565719-B2",
      subject="Test",
      to_count=1,
      cc_count=0,
      status="dry_run",
      message="dry-run",
    ),
    ddir,
  )
  artifacts = load_delivery_artifacts(tmp_path, publication_number="US-12565719-B2")
  assert artifacts.send_log is not None
  assert artifacts.send_log.status == "dry_run"


def test_ui_japanese_send_disabled_notice() -> None:
  notice = ja_ui_send_disabled_notice()
  assert "メール下書きプレビュー" not in notice
  assert "UIからのメール送信は無効" in notice
  assert "--send-email" in notice
