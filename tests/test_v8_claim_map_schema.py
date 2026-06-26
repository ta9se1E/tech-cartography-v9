"""Tests for v8 Claim Map schema (Phase 27E)."""

from __future__ import annotations

import json

from tech_cartography.runtime.v8_claim_map_schema import (
  CLAIM_MAP_SAFETY_NOTICES,
  V8ClaimMap,
  V8ClaimRecord,
  V8ClaimMapExport,
)


def test_v8_claim_record_json_serializable() -> None:
  record = V8ClaimRecord(
    claim_id="case_01:claim:abc",
    case_id="case_01_pan_graphitization",
    publication_number="US5176959",
    patent_title="Test",
    claim_no="1",
    claim_text="claim text not loaded",
    claim_text_status="not_loaded",
    evidence_needed=["claim_text_loading_required"],
    next_evidence_check="load claim text",
  )
  payload = json.dumps(record.to_dict(), ensure_ascii=False)
  restored = V8ClaimRecord.from_dict(json.loads(payload))
  assert restored.claim_text_status == "not_loaded"


def test_claim_map_safety_notices() -> None:
  blob = " ".join(CLAIM_MAP_SAFETY_NOTICES).lower()
  assert "fto" in blob
  assert "権利範囲" in blob or "legal" in blob
  assert "claim text not loaded" in blob


def test_v8_claim_map_export_dataclass() -> None:
  export = V8ClaimMapExport(
    case_id="case_01_pan_graphitization",
    publication_number="US5176959",
    generated_at="2026-01-01T00:00:00Z",
    output_dir="/tmp",
    csv_path="/tmp/claim_map.csv",
    md_path="/tmp/claim_map.md",
    xlsx_path="/tmp/claim_map.xlsx",
    manifest_path="/tmp/claim_map_manifest.json",
  )
  assert export.to_dict()["publication_number"] == "US5176959"


def test_v8_claim_map_roundtrip() -> None:
  claim_map = V8ClaimMap(
    claim_map_id="x",
    case_id="case_01_pan_graphitization",
    publication_number="all",
    generated_at="t",
    records=[],
    claim_count=0,
  )
  data = claim_map.to_dict()
  assert data["case_id"] == "case_01_pan_graphitization"
