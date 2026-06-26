"""Tests for v8 demo readiness schema (Phase 27M)."""

from __future__ import annotations

import json

from tech_cartography.runtime.v8_demo_readiness_schema import (
  V8CaseDemoReadiness,
  V8DemoReadinessReport,
  V8DemoStepStatus,
)


def test_demo_readiness_report_json_serializable() -> None:
  report = V8DemoReadinessReport(
    report_id="demo:readiness:abc",
    generated_at="2026-06-27T00:00:00Z",
    cases=[
      V8CaseDemoReadiness(
        case_id="case_01_pan_graphitization",
        case_name="Case 1",
        generated_at="2026-06-27T00:00:00Z",
        overall_status="not_ready",
        step_statuses=[
          V8DemoStepStatus(
            step_id="s1",
            case_id="case_01_pan_graphitization",
            step_name="evidence_map",
            status="not_generated",
            display_label="Evidence Map",
            summary="artifact missing",
            key_counts={"evidence_link_count": "artifact_missing"},
          ),
        ],
        evidence_link_count=None,
        gap_count=None,
      ),
    ],
    overall_status="not_ready",
    no_cloud_build=True,
    no_cloud_run_deploy=True,
  )
  payload = json.dumps(report.to_dict())
  restored = json.loads(payload)
  assert restored["no_cloud_build"] is True
  assert restored["cases"][0]["evidence_link_count"] is None
