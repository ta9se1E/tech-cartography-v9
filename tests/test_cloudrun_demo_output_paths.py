"""Tests for demo output path resolution (Phase 24.6A)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tech_cartography.runtime.demo_output_paths import (
  DEMO_OUTPUTS_ROOT_ENV,
  resolve_bundle_or_legacy,
  resolve_demo_data_dir,
  uses_demo_outputs_bundle,
)
from tech_cartography.ui.evidence_map_demo import load_demo_evidence_map_artifacts

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _clear_demo_outputs_env(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv(DEMO_OUTPUTS_ROOT_ENV, raising=False)


def test_legacy_outputs_fallback_without_env() -> None:
  path = resolve_bundle_or_legacy(
    PROJECT_ROOT,
    "evidence_map_synthesis.md",
    "outputs/evidence_map_synthesis/US-12565719-B2/evidence_map_synthesis.md",
  )
  assert path.exists()
  assert "outputs" in str(path)


def test_demo_outputs_root_priority(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DEMO_OUTPUTS_ROOT_ENV, "demo_outputs")
  assert uses_demo_outputs_bundle() is True
  path = resolve_bundle_or_legacy(
    PROJECT_ROOT,
    "evidence_map_synthesis.md",
    "outputs/evidence_map_synthesis/US-12565719-B2/evidence_map_synthesis.md",
  )
  assert path.exists()
  assert "demo_outputs/US-12565719-B2/evidence_map_synthesis.md" in str(path).replace("\\", "/")


def test_resolve_demo_data_dir_for_strategic_watch(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DEMO_OUTPUTS_ROOT_ENV, "demo_outputs")
  data_dir = resolve_demo_data_dir(
    PROJECT_ROOT,
    legacy_relative_dir="outputs/strategic_watch_briefs/US-12565719-B2",
  )
  assert (data_dir / "strategic_watch_brief.md").exists()


def test_load_demo_evidence_ready_from_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DEMO_OUTPUTS_ROOT_ENV, "demo_outputs")
  artifacts = load_demo_evidence_map_artifacts(PROJECT_ROOT)
  assert artifacts.status == "ready"
  assert artifacts.missing_artifacts == []
  assert not artifacts.selected_papers_df.empty
  assert not artifacts.claim_paper_links_df.empty
