"""Tests for v8 patent shortlist schema (Phase 27D)."""

from __future__ import annotations

import json

from tech_cartography.runtime.v8_patent_shortlist_schema import (
  SHORTLIST_SAFETY_NOTICES,
  V8PatentCandidate,
  V8PatentShortlist,
  V8PatentShortlistExport,
)


def test_v8_patent_candidate_json_serializable() -> None:
  candidate = V8PatentCandidate(
    candidate_id="case_01:patent_candidate:abc",
    case_id="case_01_pan_graphitization",
    rank=1,
    publication_number="US1234567",
    title="Test patent",
    total_score=0.75,
    score_breakdown={"theme_fit_score": 0.8},
    why_read="heuristic draft",
    next_verification_action="verify claims",
  )
  payload = json.dumps(candidate.to_dict(), ensure_ascii=False)
  restored = V8PatentCandidate.from_dict(json.loads(payload))
  assert restored.publication_number == "US1234567"
  assert restored.total_score == 0.75


def test_shortlist_safety_notices_cover_legal_disclaimer() -> None:
  blob = " ".join(SHORTLIST_SAFETY_NOTICES).lower()
  assert "fto" in blob
  assert "侵害" in blob
  assert "有効性" in blob
  assert "読む優先度" in blob or "heuristic" in blob


def test_v8_patent_shortlist_export_dataclass() -> None:
  export = V8PatentShortlistExport(
    case_id="case_01_pan_graphitization",
    case_name="Case 1",
    generated_at="2026-01-01T00:00:00Z",
    top_n=5,
    output_dir="/tmp/out",
    csv_path="/tmp/out/patent_shortlist.csv",
    md_path="/tmp/out/patent_shortlist.md",
    xlsx_path="/tmp/out/patent_shortlist.xlsx",
    manifest_path="/tmp/out/patent_shortlist_manifest.json",
  )
  data = export.to_dict()
  assert data["top_n"] == 5


def test_v8_patent_shortlist_roundtrip() -> None:
  shortlist = V8PatentShortlist(
    case_id="case_01_pan_graphitization",
    case_name="Case 1",
    top_n=3,
    count=1,
    patent_candidates=[
      V8PatentCandidate(
        candidate_id="x",
        case_id="case_01_pan_graphitization",
        rank=1,
        publication_number="JP1",
        title="t",
      ),
    ],
  )
  restored = V8PatentShortlist(
    case_id=shortlist.to_dict()["case_id"],
    case_name=shortlist.to_dict()["case_name"],
    top_n=shortlist.to_dict()["top_n"],
    count=shortlist.to_dict()["count"],
    patent_candidates=[V8PatentCandidate.from_dict(c) for c in shortlist.to_dict()["patent_candidates"]],
    generated_at=shortlist.to_dict()["generated_at"],
  )
  assert restored.count == 1
