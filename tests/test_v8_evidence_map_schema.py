"""Tests for v8 Evidence Map schema (Phase 27F)."""

from __future__ import annotations

import json

from tech_cartography.runtime.v8_evidence_map_schema import (
  EVIDENCE_MAP_SAFETY_NOTICES,
  V8EvidenceLink,
  V8EvidenceMap,
  V8EvidenceMapExport,
)


def test_v8_evidence_link_json_serializable() -> None:
  link = V8EvidenceLink(
    evidence_link_id="case_01:evidence_link:abc",
    case_id="case_01_pan_graphitization",
    publication_number="US5176959",
    patent_title="Test",
    claim_id="c1",
    claim_no="1",
    claim_text_status="not_loaded",
    primary_axis="unknown",
    support_type="claim_text_required",
    support_level="missing",
    next_verification_action="load claim text",
  )
  payload = json.dumps(link.to_dict(), ensure_ascii=False)
  restored = V8EvidenceLink.from_dict(json.loads(payload))
  assert restored.support_type == "claim_text_required"


def test_evidence_map_safety_notices() -> None:
  blob = " ".join(EVIDENCE_MAP_SAFETY_NOTICES).lower()
  assert "not proof" in blob or "証明" in blob
  assert "supporting evidence candidate" in blob
  assert "fto" in blob


def test_v8_evidence_map_export_dataclass() -> None:
  export = V8EvidenceMapExport(
    export_id="x",
    case_id="case_01_pan_graphitization",
    publication_number="all",
    output_dir="/tmp",
    csv_path="/tmp/evidence_map.csv",
    md_path="/tmp/evidence_map.md",
    xlsx_path="/tmp/evidence_map.xlsx",
    manifest_path="/tmp/evidence_map_manifest.json",
    created_at="2026-01-01T00:00:00Z",
  )
  assert export.to_dict()["case_id"] == "case_01_pan_graphitization"


def test_v8_evidence_map_roundtrip() -> None:
  emap = V8EvidenceMap(
    evidence_map_id="x",
    case_id="case_01_pan_graphitization",
    publication_number="all",
    generated_at="t",
    links=[],
    link_count=0,
  )
  data = emap.to_dict()
  assert data["case_id"] == "case_01_pan_graphitization"
