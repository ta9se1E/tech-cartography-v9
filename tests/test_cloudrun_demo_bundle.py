"""Tests for Cloud Run demo_outputs bundle (Phase 24.6A)."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from tech_cartography.runtime.demo_output_paths import (  # noqa: E402
  BUNDLE_COPY_SOURCES,
  DEMO_PUBLICATION_NUMBER,
  REQUIRED_BUNDLE_FILES,
  demo_bundle_dir,
  missing_bundle_files,
  relative_upload_path,
)


def test_demo_outputs_bundle_dir_exists() -> None:
  bundle_dir = demo_bundle_dir(PROJECT_ROOT)
  assert bundle_dir.exists()
  assert bundle_dir.name == DEMO_PUBLICATION_NUMBER


def test_required_bundle_files_exist() -> None:
  missing = missing_bundle_files(PROJECT_ROOT)
  assert not missing, missing


def test_required_bundle_files_are_defined() -> None:
  assert len(REQUIRED_BUNDLE_FILES) >= 11
  assert "evidence_map_synthesis.md" in REQUIRED_BUNDLE_FILES
  assert "selected_evidence_papers.csv" in REQUIRED_BUNDLE_FILES
  assert "claim_paper_candidate_links.csv" in REQUIRED_BUNDLE_FILES


def test_bundle_copy_sources_cover_required_files() -> None:
  copied_names = {bundle_name for _, bundle_name in BUNDLE_COPY_SOURCES}
  for required in REQUIRED_BUNDLE_FILES:
    assert required in copied_names, required


def test_relative_upload_paths_use_demo_outputs_prefix() -> None:
  path = relative_upload_path("evidence_map_synthesis.md")
  assert path.startswith("demo_outputs/US-12565719-B2/")


from tests.cloudrun_ignore_paths import cloudrun_ignore_text


def test_gcloudignore_does_not_exclude_demo_outputs() -> None:
  text = cloudrun_ignore_text("gcloudignore")
  assert "demo_outputs/" not in text
  assert "outputs/" in text
