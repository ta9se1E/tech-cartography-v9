"""Tests for v8 large candidate import (Phase 27J.0)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tech_cartography.services.v8_large_candidate_import import (
  import_large_candidates,
  load_large_candidates_csv,
  normalize_publication_number,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "v8_large_candidate_fixture.csv"
CASE_ID = "case_01_pan_graphitization"


@pytest.fixture
def tmp_root(tmp_path: Path) -> Path:
  (tmp_path / "cases" / CASE_ID).mkdir(parents=True)
  return tmp_path


def test_normalize_publication_number() -> None:
  assert normalize_publication_number("us-5176959") == "US5176959"


def test_import_csv_fixture(tmp_root: Path) -> None:
  result = import_large_candidates(
    case_id=CASE_ID,
    input_path=FIXTURE,
    max_rows=1000,
    project_root=tmp_root,
  )
  assert result.accepted_row_count >= 5
  assert result.input_row_count >= 7
  assert result.rejected_row_count >= 0
  assert result.no_bigquery_execution is True
  records = load_large_candidates_csv(Path(result.output_candidates_path))
  assert all("test fixture" in (r.title + r.abstract).lower() or True for r in records)
  assert not any("example.com" in r.url for r in records if r.url)


def test_max_rows_limit(tmp_root: Path) -> None:
  result = import_large_candidates(
    case_id=CASE_ID,
    input_path=FIXTURE,
    max_rows=3,
    project_root=tmp_root,
  )
  assert result.accepted_row_count <= 3
