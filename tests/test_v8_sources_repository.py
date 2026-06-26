"""Tests for v8 sources repository and loader (Phase 27C)."""

from __future__ import annotations

from tech_cartography.services.v8_sources_loader import build_source_id, csv_row_to_source_record, dedupe_key
from tech_cartography.services.v8_sources_repository import load_sources_table
from tech_cartography.services.v8_sources_table import list_case_ids, project_root_from_here


def test_load_three_case_source_tables() -> None:
  root = project_root_from_here()
  case_ids = list_case_ids(root)
  assert len(case_ids) == 3
  table = load_sources_table(project_root=root)
  assert table.source_count >= 15
  assert table.count_by_type.get("patent", 0) >= 15


def test_each_case_has_five_patents() -> None:
  root = project_root_from_here()
  for case_id in list_case_ids(root):
    table = load_sources_table(case_id, project_root=root)
    assert table.count_by_type.get("patent", 0) >= 5, case_id


def test_web_and_company_get_candidate_flag() -> None:
  root = project_root_from_here()
  table = load_sources_table(project_root=root)
  web_rows = [r for r in table.records if r.source_type in {"web", "company"}]
  assert web_rows
  assert all(r.candidate_information_only for r in web_rows)


def test_duplicate_removal() -> None:
  root = project_root_from_here()
  table = load_sources_table(project_root=root, dedupe=True)
  keys = [dedupe_key(r) for r in table.records]
  assert len(keys) == len(set(keys))


def test_build_source_id_stable() -> None:
  a = build_source_id(
    case_id="case_01",
    source_type="patent",
    publication_number="US4370169",
    doi="",
    url="",
    title="x",
  )
  b = build_source_id(
    case_id="case_01",
    source_type="patent",
    publication_number="US4370169",
    doi="",
    url="",
    title="y",
  )
  assert a == b


def test_url_missing_sets_human_review_for_patent_row() -> None:
  root = project_root_from_here()
  record = csv_row_to_source_record(
    {
      "type": "patent",
      "title": "No URL patent",
      "organization": "Test",
      "year": "2000",
      "url": "",
      "publication_number": "",
      "source_status": "manual_review_required",
      "evidence_role": "unknown",
      "case_id": "case_01_pan_graphitization",
      "notes": "manual review required",
    },
    project_root=root,
  )
  assert record.human_review_required is True
  assert record.verification_status == "needs_human_review"
