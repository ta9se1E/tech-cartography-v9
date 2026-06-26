"""Tests for v8 large candidate schema (Phase 27J.0)."""

from __future__ import annotations

import json

from tech_cartography.runtime.v8_large_candidate_schema import (
  V8LargeCandidateImportResult,
  V8LargeCandidateRecord,
  V8LargeCandidateShortlistPack,
)


def test_large_candidate_record_json_serializable() -> None:
  rec = V8LargeCandidateRecord(
    candidate_id="c1",
    case_id="case_01_pan_graphitization",
    publication_number="US5176959",
    title="test",
  )
  payload = rec.to_dict()
  assert json.loads(json.dumps(payload))["publication_number"] == "US5176959"


def test_import_result_flags() -> None:
  result = V8LargeCandidateImportResult(
    import_id="i1",
    case_id="case_01_pan_graphitization",
    input_path="/tmp/in.csv",
    imported_at="2026-01-01T00:00:00Z",
    no_external_api=True,
    no_bigquery_execution=True,
  )
  assert result.no_email_send is True
