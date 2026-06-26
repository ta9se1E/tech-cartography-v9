"""Tests for v8 Gap / Next Actions schema (Phase 27G)."""

from __future__ import annotations

import json

from tech_cartography.runtime.v8_gap_next_actions_schema import (
  GAP_NEXT_ACTIONS_SAFETY_NOTICES,
  V8EvidenceGapRecord,
  V8GapNextActionsExport,
  V8GapNextActionsReport,
  V8NextVerificationAction,
)


def test_gap_record_json_serializable() -> None:
  gap = V8EvidenceGapRecord(
    gap_id="case_01:gap:abc",
    case_id="case_01_pan_graphitization",
    publication_number="US5176959",
    patent_title="",
    claim_id="c1",
    claim_no="1",
    primary_axis="process",
    gap_type="claim_text_required",
    gap_title="請求項本文が未取得",
    no_legal_judgement=True,
  )
  payload = json.dumps(gap.to_dict())
  restored = V8EvidenceGapRecord.from_dict(json.loads(payload))
  assert restored.gap_type == "claim_text_required"
  assert restored.no_legal_judgement is True


def test_action_json_serializable() -> None:
  action = V8NextVerificationAction(
    action_id="case_01:action:abc",
    case_id="case_01_pan_graphitization",
    action_rank=1,
    action_type="load_claim_text",
    action_title="claim 本文を取得",
    no_legal_judgement=True,
  )
  payload = json.dumps(action.to_dict())
  restored = V8NextVerificationAction.from_dict(json.loads(payload))
  assert restored.action_type == "load_claim_text"


def test_report_to_dict() -> None:
  report = V8GapNextActionsReport(
    report_id="r1",
    case_id="case_01_pan_graphitization",
    publication_number="all",
    generated_at="2026-01-01T00:00:00Z",
    no_legal_judgement=True,
  )
  data = report.to_dict()
  assert data["no_legal_judgement"] is True
  assert "gaps" in data


def test_safety_notices() -> None:
  blob = " ".join(GAP_NEXT_ACTIONS_SAFETY_NOTICES)
  assert "弱点" in blob or "invalidity" in blob.lower()
  assert "FTO" in blob
  assert "人間" in blob or "human" in blob.lower()


def test_export_dataclass() -> None:
  export = V8GapNextActionsExport(
    export_id="e1",
    case_id="case_01_pan_graphitization",
    publication_number="all",
    output_dir="/tmp/out",
    csv_path="/tmp/out/gap.csv",
    md_path="/tmp/out/gap.md",
    xlsx_path="/tmp/out/gap.xlsx",
    manifest_path="/tmp/out/manifest.json",
    watch_profile_proposal_path="/tmp/out/watch.md",
    digest_summary_path="/tmp/out/digest.md",
    created_at="2026-01-01T00:00:00Z",
  )
  assert export.watch_profile_proposal_path.endswith("watch.md")
