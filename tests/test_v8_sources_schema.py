"""Tests for v8 sources schema (Phase 27C)."""

from __future__ import annotations

import json

from tech_cartography.runtime.v8_sources_schema import (
  FIXED_POINT_OBSERVATION_NOTE,
  SAFETY_EXPORT_NOTICES,
  V8SourceExportPackage,
  V8SourceRecord,
  V8SourcesTable,
)


def test_v8_source_record_json_serializable() -> None:
  record = V8SourceRecord(
    source_id="case_01:patent:abc",
    case_id="case_01_pan_graphitization",
    source_type="patent",
    title="Test patent",
    publication_number="US4370169",
    candidate_information_only=False,
  )
  payload = json.dumps(record.to_dict())
  restored = V8SourceRecord.from_dict(json.loads(payload))
  assert restored.source_id == record.source_id
  assert restored.publication_number == "US4370169"


def test_v8_sources_table_to_dict() -> None:
  table = V8SourcesTable(records=[], source_count=0)
  data = table.to_dict()
  assert "records" in data
  assert data["source_count"] == 0


def test_safety_notices_cover_legal_and_candidate() -> None:
  blob = " ".join(SAFETY_EXPORT_NOTICES) + FIXED_POINT_OBSERVATION_NOTE
  assert "FTO" in blob
  assert "candidate" in blob.lower() or "候補" in blob
  assert "メール" in FIXED_POINT_OBSERVATION_NOTE
  assert "Scheduler" in FIXED_POINT_OBSERVATION_NOTE


def test_export_package_dataclass() -> None:
  pkg = V8SourceExportPackage(
    case_id="all",
    case_name="All",
    generated_at="2026-01-01T00:00:00+00:00",
    source_count=1,
    count_by_type={"patent": 1},
    count_by_evidence_role={},
    warnings=[],
    output_dir="/tmp/out",
    manifest_path="/tmp/out/manifest.json",
    sources_csv_path="/tmp/out/sources.csv",
    sources_md_path="/tmp/out/sources.md",
    sources_xlsx_path="/tmp/out/sources.xlsx",
    export_summary_path="/tmp/out/export_summary.md",
  )
  assert pkg.to_dict()["case_id"] == "all"
