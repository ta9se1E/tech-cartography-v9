"""v8 Demo Readiness export (Phase 27M)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from tech_cartography.runtime.live_artifact_paths import get_live_outputs_root
from tech_cartography.runtime.v8_demo_readiness_schema import (
  DEMO_READINESS_NEXT_PHASES,
  DEMO_READINESS_SAFETY_NOTICES,
  V8DemoReadinessExport,
  V8DemoReadinessReport,
)

V8_DEMO_READINESS_SUBDIR = "v8_demo_readiness"
LOCAL_V8_DEMO_READINESS_SUBDIR = "local_v8_demo_readiness"

_SENSITIVE_RE = re.compile(
  r"(smtp_password|tavily_api_key|api[_-]?key\s*[:=]|authorization|oauth|jwt|eyJhbGci)",
  re.IGNORECASE,
)


def get_demo_readiness_dir(project_root: Path | str | None = None) -> Path:
  root = get_live_outputs_root(project_root)
  if root.name == "outputs" or not str(root).endswith("live"):
    return root / LOCAL_V8_DEMO_READINESS_SUBDIR
  return root / V8_DEMO_READINESS_SUBDIR


def find_latest_demo_readiness_dir(project_root: Path | str | None = None) -> Path | None:
  base = get_demo_readiness_dir(project_root)
  if not base.is_dir():
    return None
  dirs = sorted((p for p in base.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True)
  return dirs[0] if dirs else None


def _assert_no_secrets(text: str) -> None:
  if _SENSITIVE_RE.search(text):
    raise ValueError("export content must not contain secret-like strings")


def operator_checklist_md(report: V8DemoReadinessReport) -> str:
  lines = [
    "# Demo Operator Checklist",
    "",
    f"- overall_status: {report.overall_status}",
    "",
    "## Checklist",
    *[f"- [ ] {item}" for item in report.demo_operator_checklist],
    "",
    "## Case Summary",
  ]
  for case in report.cases:
    lines.append(f"- **{case.case_id}**: {case.overall_status} — next: {case.current_recommended_step}")
    if case.evidence_link_count is None:
      lines.append("  - evidence_link_count: artifact missing (not true zero)")
    if case.gap_count is None:
      lines.append("  - gap_count: artifact missing (not true zero)")
  lines.extend(["", "## Safety", *[f"- {n}" for n in DEMO_READINESS_SAFETY_NOTICES]])
  text = "\n".join(lines)
  _assert_no_secrets(text)
  return text


def cloud_preparation_checklist_md(report: V8DemoReadinessReport) -> str:
  lines = [
    "# Cloud Preparation Checklist",
    "",
    f"- no_cloud_build: {report.no_cloud_build}",
    f"- no_cloud_run_deploy: {report.no_cloud_run_deploy}",
    "",
    "## Checklist",
    *[f"- [ ] {item}" for item in report.cloud_preparation_checklist],
    "",
    "## Next Phases",
    *[f"- {p}" for p in DEMO_READINESS_NEXT_PHASES],
  ]
  text = "\n".join(lines)
  _assert_no_secrets(text)
  return text


def report_to_markdown(report: V8DemoReadinessReport) -> str:
  lines = [
    "# Demo Readiness Report",
    "",
    f"- report_id: {report.report_id}",
    f"- generated_at: {report.generated_at}",
    f"- overall_status: {report.overall_status}",
    f"- ready: {report.ready_case_count} / warning: {report.warning_case_count} / not_ready: {report.not_ready_case_count}",
    "",
    "## Common Next Actions",
    *[f"- {a}" for a in report.common_next_actions],
    "",
  ]
  for case in report.cases:
    lines.extend([
      f"## {case.case_id} — {case.case_name}",
      f"- overall_status: {case.overall_status}",
      f"- current_recommended_step: {case.current_recommended_step}",
      f"- completed: {case.completed_step_count}/{case.total_step_count}",
      f"- large_candidate_count: {case.large_candidate_count if case.large_candidate_count is not None else 'artifact missing'}",
      f"- top5_count: {case.top5_count if case.top5_count is not None else 'artifact missing'}",
      f"- manual_claim_count: {case.manual_claim_count if case.manual_claim_count is not None else '—'}",
      f"- evidence_link_count: {case.evidence_link_count if case.evidence_link_count is not None else 'artifact missing (not true zero)'}",
      f"- gap_count: {case.gap_count if case.gap_count is not None else 'artifact missing (not true zero)'}",
      "",
      "### Next 3 Actions",
      *[f"- {a}" for a in case.next_3_user_actions],
      "",
      "### Step Status",
    ])
    for step in case.step_statuses:
      lines.append(f"- **{step.display_label}** [{step.status}]: {step.summary}")
    lines.append("")

  lines.extend([
    "## Missing Artifact Summary",
  ])
  for case in report.cases:
    missing = [s.display_label for s in case.step_statuses if s.status == "not_generated"]
    if missing:
      lines.append(f"- {case.case_id}: {', '.join(missing)}")

  lines.extend([
    "",
    "## Safety",
    *[f"- {n}" for n in DEMO_READINESS_SAFETY_NOTICES],
  ])
  text = "\n".join(lines)
  _assert_no_secrets(text)
  return text


def export_demo_readiness(
  report: V8DemoReadinessReport,
  *,
  project_root: Path | str | None = None,
) -> V8DemoReadinessExport:
  root = Path(project_root) if project_root else Path.cwd()
  slug = report.generated_at.replace(":", "").replace("-", "").replace("+00:00", "Z")
  output_dir = get_demo_readiness_dir(root) / f"readiness_{slug}"
  output_dir.mkdir(parents=True, exist_ok=True)

  json_path = output_dir / "demo_readiness_report.json"
  md_path = output_dir / "demo_readiness_report.md"
  manifest_path = output_dir / "demo_readiness_manifest.json"
  operator_path = output_dir / "demo_operator_checklist.md"
  cloud_path = output_dir / "cloud_preparation_checklist.md"

  json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
  md_path.write_text(report_to_markdown(report), encoding="utf-8")
  operator_path.write_text(operator_checklist_md(report), encoding="utf-8")
  cloud_path.write_text(cloud_preparation_checklist_md(report), encoding="utf-8")

  manifest = {
    "export_id": report.report_id,
    "overall_status": report.overall_status,
    "ready_case_count": report.ready_case_count,
    "common_next_actions": report.common_next_actions,
    "no_cloud_build": report.no_cloud_build,
    "no_cloud_run_deploy": report.no_cloud_run_deploy,
    "files": {
      "demo_readiness_report_json": str(json_path),
      "demo_readiness_report_md": str(md_path),
      "demo_operator_checklist_md": str(operator_path),
      "cloud_preparation_checklist_md": str(cloud_path),
    },
  }
  manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2)
  _assert_no_secrets(manifest_text)
  manifest_path.write_text(manifest_text, encoding="utf-8")

  return V8DemoReadinessExport(
    export_id=report.report_id,
    output_dir=str(output_dir),
    json_path=str(json_path),
    md_path=str(md_path),
    manifest_path=str(manifest_path),
    operator_checklist_path=str(operator_path),
    cloud_checklist_path=str(cloud_path),
    created_at=report.generated_at,
  )
