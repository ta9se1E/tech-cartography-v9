"""Tests for v8 case validation schema (Phase 27I)."""

from __future__ import annotations

import json

from tech_cartography.runtime.v8_case_validation_schema import (
  VALIDATION_STEP_IDS,
  V8CaseValidationReport,
  V8CaseValidationStepResult,
  V8ThreeCaseValidationExport,
  V8ThreeCaseValidationPack,
)


def test_validation_step_ids_complete() -> None:
  assert len(VALIDATION_STEP_IDS) == 7
  assert "export" in VALIDATION_STEP_IDS


def test_case_validation_report_json_serializable() -> None:
  step = V8CaseValidationStepResult(
    step_id="sources",
    case_id="case_01_pan_graphitization",
    step_name="Sources一覧",
    status="pass",
    summary="ok",
  )
  report = V8CaseValidationReport(
    report_id="r1",
    case_id="case_01_pan_graphitization",
    case_name="PAN",
    generated_at="2026-01-01T00:00:00Z",
    step_results=[step],
    readiness_for_demo="needs_claim_text",
  )
  payload = report.to_dict()
  text = json.dumps(payload, ensure_ascii=False)
  assert "needs_claim_text" in text
  assert json.loads(text)["case_id"] == "case_01_pan_graphitization"


def test_three_case_validation_pack_json_serializable() -> None:
  report = V8CaseValidationReport(
    report_id="r1",
    case_id="case_01_pan_graphitization",
    case_name="PAN",
    generated_at="2026-01-01T00:00:00Z",
  )
  pack = V8ThreeCaseValidationPack(
    pack_id="pack1",
    generated_at="2026-01-01T00:00:00Z",
    cases=[report],
    common_blocking_issues=["claim 本文未取得"],
    common_next_actions=["load claim text"],
    demo_readiness_summary="# Demo",
    cloud_readiness_summary="# Cloud",
  )
  payload = pack.to_dict()
  text = json.dumps(payload, ensure_ascii=False)
  assert pack.no_email_send is True
  assert pack.no_scheduler_start is True
  assert json.loads(text)["pack_id"] == "pack1"


def test_validation_export_dataclass() -> None:
  export = V8ThreeCaseValidationExport(
    export_id="e1",
    output_dir="/tmp/out",
    json_path="/tmp/out/pack.json",
    md_path="/tmp/out/pack.md",
    xlsx_path="/tmp/out/pack.xlsx",
    manifest_path="/tmp/out/manifest.json",
    demo_readiness_path="/tmp/out/demo.md",
    cloud_readiness_path="/tmp/out/cloud.md",
    case_report_paths={"case_01": "/tmp/out/case_01.md"},
    created_at="2026-01-01T00:00:00Z",
  )
  assert export.to_dict()["manifest_path"].endswith("manifest.json")
