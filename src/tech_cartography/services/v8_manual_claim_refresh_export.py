"""v8 Manual Claim Refresh export (Phase 27K)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from tech_cartography.runtime.live_artifact_paths import get_live_outputs_root
from tech_cartography.runtime.v8_manual_claim_injection_schema import (
  MANUAL_CLAIM_SAFETY_NOTICES,
  REFRESH_NEXT_PHASES,
  V8ManualClaimRefreshExport,
  V8ManualClaimRefreshReport,
)

V8_MANUAL_CLAIM_REFRESH_SUBDIR = "v8_manual_claim_refresh"
LOCAL_V8_MANUAL_CLAIM_REFRESH_SUBDIR = "local_v8_manual_claim_refresh"

_SENSITIVE_RE = re.compile(
  r"(smtp_password|tavily_api_key|api[_-]?key\s*[:=]|authorization|oauth|jwt|eyJhbGci)",
  re.IGNORECASE,
)


def get_manual_claim_refresh_dir(project_root: Path | str | None = None) -> Path:
  root = get_live_outputs_root(project_root)
  if root.name == "outputs" or not str(root).endswith("live"):
    return root / LOCAL_V8_MANUAL_CLAIM_REFRESH_SUBDIR
  return root / V8_MANUAL_CLAIM_REFRESH_SUBDIR


def find_latest_manual_claim_refresh_dir(project_root: Path | str | None = None) -> Path | None:
  base = get_manual_claim_refresh_dir(project_root)
  if not base.is_dir():
    return None
  dirs = sorted((p for p in base.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True)
  return dirs[0] if dirs else None


def _assert_no_secrets(text: str) -> None:
  if _SENSITIVE_RE.search(text):
    raise ValueError("export content must not contain secret-like strings")


def report_to_markdown(report: V8ManualClaimRefreshReport) -> str:
  inj = report.claim_injection_result
  lines = [
    "# Manual Claim Refresh Report",
    "",
    f"- report_id: {report.report_id}",
    f"- case_id: {report.case_id}",
    f"- publication_number: {report.publication_number}",
    f"- generated_at: {report.generated_at}",
    "",
  ]
  if inj:
    lines.extend([
      "## Claim Injection",
      f"- claim_no: {inj.claim_no}",
      f"- claim_text_status: {inj.claim_text_status}",
      f"- claim_text_length: {inj.claim_text_length}",
      f"- saved_to_claims_input_csv: {inj.saved_to_claims_input_csv}",
      f"- updated_claims_input_path: {inj.updated_claims_input_path}",
      f"- backup_path: {inj.backup_path or '（なし）'}",
      "",
    ])
  lines.extend([
    "## Summaries",
    f"- Claim Map: {report.claim_map_summary}",
    f"- Evidence Map: {report.evidence_map_summary}",
    f"- Gap / Next Actions: {report.gap_next_actions_summary}",
    f"- Fixed Point Observation: {report.fixed_point_observation_summary}",
    "",
    "## Validation Readiness",
    f"- before: {report.validation_readiness_before}",
    f"- after: {report.validation_readiness_after}",
    f"- claim_text_required_count: {report.claim_text_required_count_before} → {report.claim_text_required_count_after}",
    "",
    "## Remaining Blocking Issues",
    *[f"- {b}" for b in report.remaining_blocking_issues],
    "",
    "## Next Human Actions",
    *[f"- {a}" for a in report.next_human_actions],
    "",
    "## Artifact Trace",
    *[f"- {p}" for p in report.artifact_paths],
    "",
    "## Safety",
    *[f"- {n}" for n in MANUAL_CLAIM_SAFETY_NOTICES],
    "",
    "## Next Phases",
    *[f"- {p}" for p in REFRESH_NEXT_PHASES],
  ])
  text = "\n".join(lines)
  _assert_no_secrets(text)
  return text


def artifact_trace_markdown(report: V8ManualClaimRefreshReport) -> str:
  lines = [
    "# Refreshed Artifact Trace",
    "",
    f"- case_id: {report.case_id}",
    f"- publication_number: {report.publication_number}",
    "",
  ]
  for path in report.artifact_paths:
    lines.append(f"- {path}")
  text = "\n".join(lines)
  _assert_no_secrets(text)
  return text


def export_manual_claim_refresh(
  report: V8ManualClaimRefreshReport,
  *,
  project_root: Path | str | None = None,
) -> V8ManualClaimRefreshExport:
  root = Path(project_root) if project_root else Path.cwd()
  slug = report.generated_at.replace(":", "").replace("-", "").replace("+00:00", "Z")
  output_dir = get_manual_claim_refresh_dir(root) / f"refresh_{report.case_id}_{slug}"
  output_dir.mkdir(parents=True, exist_ok=True)

  json_path = output_dir / "manual_claim_refresh_report.json"
  md_path = output_dir / "manual_claim_refresh_report.md"
  manifest_path = output_dir / "manual_claim_refresh_manifest.json"
  trace_path = output_dir / "refreshed_artifact_trace.md"

  json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
  md_path.write_text(report_to_markdown(report), encoding="utf-8")
  trace_path.write_text(artifact_trace_markdown(report), encoding="utf-8")

  manifest = {
    "export_id": report.report_id,
    "case_id": report.case_id,
    "publication_number": report.publication_number,
    "claim_text_status": (
      report.claim_injection_result.claim_text_status if report.claim_injection_result else "loaded"
    ),
    "validation_readiness_before": report.validation_readiness_before,
    "validation_readiness_after": report.validation_readiness_after,
    "claim_text_required_count_before": report.claim_text_required_count_before,
    "claim_text_required_count_after": report.claim_text_required_count_after,
    "remaining_blocking_issues": report.remaining_blocking_issues,
    "next_human_actions": report.next_human_actions,
    "safety_notices": list(MANUAL_CLAIM_SAFETY_NOTICES),
    "files": {
      "manual_claim_refresh_report_json": str(json_path),
      "manual_claim_refresh_report_md": str(md_path),
      "refreshed_artifact_trace_md": str(trace_path),
    },
  }
  manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2)
  _assert_no_secrets(manifest_text)
  manifest_path.write_text(manifest_text, encoding="utf-8")

  return V8ManualClaimRefreshExport(
    export_id=report.report_id,
    output_dir=str(output_dir),
    json_path=str(json_path),
    md_path=str(md_path),
    manifest_path=str(manifest_path),
    artifact_trace_path=str(trace_path),
    created_at=report.generated_at,
  )
