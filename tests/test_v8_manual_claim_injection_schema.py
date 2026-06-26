"""Tests for v8 manual claim injection schema (Phase 27J)."""

from __future__ import annotations

import json

from tech_cartography.runtime.v8_manual_claim_injection_schema import (
  V8ManualClaimInjectionRequest,
  V8ManualClaimInjectionResult,
  V8ManualClaimRefreshExport,
  V8ManualClaimRefreshReport,
)


def test_injection_request_json_serializable() -> None:
  req = V8ManualClaimInjectionRequest(
    request_id="r1",
    case_id="case_01_pan_graphitization",
    publication_number="US5176959",
    claim_text="sample",
  )
  payload = req.to_dict()
  assert json.loads(json.dumps(payload))["no_legal_judgement"] is True


def test_injection_result_json_serializable() -> None:
  result = V8ManualClaimInjectionResult(
    result_id="res1",
    case_id="case_01_pan_graphitization",
    publication_number="US5176959",
    claim_no="1",
    claim_text_status="manual_input",
    claim_text_length=100,
    saved_to_claims_input_csv=True,
    updated_claims_input_path="/tmp/claims_input.csv",
  )
  assert result.to_dict()["claim_text_status"] == "manual_input"


def test_refresh_report_json_serializable() -> None:
  report = V8ManualClaimRefreshReport(
    report_id="rep1",
    case_id="case_01_pan_graphitization",
    publication_number="US5176959",
    generated_at="2026-01-01T00:00:00Z",
    validation_readiness_after="partial_claim_loaded",
    no_email_send=True,
    no_scheduler_start=True,
  )
  payload = report.to_dict()
  assert payload["no_email_send"] is True
  assert json.loads(json.dumps(payload))["validation_readiness_after"] == "partial_claim_loaded"
