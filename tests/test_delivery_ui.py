"""Tests for delivery UI loader (Phase 24.0)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.delivery.store import build_delivery_package
from tech_cartography.ui.delivery_ui import load_delivery_artifacts


def test_missing_delivery_loader(tmp_path: Path) -> None:
  artifacts = load_delivery_artifacts(tmp_path)
  assert artifacts.status == "missing"
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
  assert "Preview only" in (artifacts.weekly_digest_md or "")


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
