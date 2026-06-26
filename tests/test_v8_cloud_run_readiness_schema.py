"""Tests for v8 Cloud Run readiness schema (Phase 27N)."""

from __future__ import annotations

import json

from tech_cartography.runtime.v8_cloud_run_readiness_schema import (
  V8CloudRunArtifactPolicy,
  V8CloudRunCheckResult,
  V8CloudRunReadinessExport,
  V8CloudRunReadinessReport,
)


def test_cloud_run_readiness_report_json_serializable() -> None:
  report = V8CloudRunReadinessReport(
    report_id="test",
    generated_at="2026-01-01T00:00:00+00:00",
    artifact_policy=V8CloudRunArtifactPolicy(
      local_output_root="outputs/local_*",
      cloud_output_root="/tmp/tech_cartography_outputs",
    ),
    check_results=[
      V8CloudRunCheckResult(
        check_id="demo",
        check_name="Demo",
        status="warning",
        summary="demo_data not_ready",
      ),
    ],
  )
  blob = json.dumps(report.to_dict())
  parsed = json.loads(blob)
  assert parsed["no_cloud_build_executed"] is True
  assert parsed["no_cloud_run_deploy_executed"] is True
  assert parsed["no_email_send"] is True
  assert parsed["no_scheduler_start"] is True


def test_export_dataclass_serializable() -> None:
  export = V8CloudRunReadinessExport(
    export_id="e1",
    output_dir="/tmp/out",
    json_path="/tmp/out/a.json",
    md_path="/tmp/out/a.md",
    manifest_path="/tmp/out/m.json",
    deploy_checklist_path="/tmp/out/d.md",
    demo_data_checklist_path="/tmp/out/demo.md",
    operator_checklist_path="/tmp/out/op.md",
    env_var_template_path="/tmp/out/env.md",
    artifact_policy_path="/tmp/out/policy.md",
    created_at="2026-01-01T00:00:00+00:00",
  )
  json.dumps(export.to_dict())
