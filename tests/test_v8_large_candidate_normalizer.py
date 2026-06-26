"""Tests for v8 large candidate normalizer (Phase 27J.0)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tech_cartography.services.v8_large_candidate_import import import_large_candidates
from tech_cartography.services.v8_large_candidate_normalizer import (
  dedupe_large_candidates,
  normalize_and_dedupe_large_candidates,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "v8_large_candidate_fixture.csv"
CASE_ID = "case_01_pan_graphitization"


@pytest.fixture
def imported_root(tmp_path: Path) -> Path:
  (tmp_path / "cases" / CASE_ID).mkdir(parents=True)
  import_large_candidates(case_id=CASE_ID, input_path=FIXTURE, project_root=tmp_path)
  return tmp_path


def test_dedupe_detects_duplicate_pub(imported_root: Path) -> None:
  deduped, issues = normalize_and_dedupe_large_candidates(CASE_ID, project_root=imported_root)
  assert len(deduped) < 8
  assert any(i.issue_type == "duplicate" for i in issues)


def test_quality_issues_missing_fields(imported_root: Path) -> None:
  _, issues = normalize_and_dedupe_large_candidates(CASE_ID, project_root=imported_root)
  types = {i.issue_type for i in issues}
  assert "missing_publication_number" in types or "missing_title" in types
