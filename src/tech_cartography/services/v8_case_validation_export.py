"""v8 Three Case Validation export (Phase 27I)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tech_cartography.runtime.live_artifact_paths import get_live_outputs_root
from tech_cartography.runtime.v8_case_validation_schema import (
  VALIDATION_NEXT_PHASES,
  VALIDATION_SAFETY_NOTICES,
  V8CaseValidationReport,
  V8ThreeCaseValidationExport,
  V8ThreeCaseValidationPack,
)

V8_CASE_VALIDATION_SUBDIR = "v8_case_validation_packs"
LOCAL_V8_CASE_VALIDATION_SUBDIR = "local_v8_case_validation_packs"

_SENSITIVE_RE = re.compile(
  r"(smtp_password|tavily_api_key|api[_-]?key\s*[:=]|authorization|oauth|jwt|eyJhbGci)",
  re.IGNORECASE,
)


def get_v8_case_validation_dir(project_root: Path | str | None = None) -> Path:
  root = get_live_outputs_root(project_root)
  if root.name == "outputs" or not str(root).endswith("live"):
    return root / LOCAL_V8_CASE_VALIDATION_SUBDIR
  return root / V8_CASE_VALIDATION_SUBDIR


def find_latest_validation_pack_dir(project_root: Path | str | None = None) -> Path | None:
  base = get_v8_case_validation_dir(project_root)
  if not base.is_dir():
    return None
  dirs = sorted((p for p in base.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True)
  return dirs[0] if dirs else None


def _assert_no_secrets(text: str) -> None:
  if _SENSITIVE_RE.search(text):
    raise ValueError("export content must not contain secret-like strings")


def case_report_to_markdown(report: V8CaseValidationReport) -> str:
  lines = [
    f"# Case Validation — {report.case_id}",
    "",
    f"- case_name: {report.case_name}",
    f"- generated_at: {report.generated_at}",
    f"- overall_status: {report.overall_status}",
    f"- readiness_for_demo: {report.readiness_for_demo}",
    "",
    "## Step Results",
    "",
    "| step | status | summary |",
    "| --- | --- | --- |",
  ]
  for step in report.step_results:
    lines.append(f"| {step.step_name} | {step.status} | {step.summary[:80]} |")
  lines.extend([
    "",
    "## Top Findings",
    *[f"- {f}" for f in report.top_findings],
    "",
    "## Known Limitations",
    *[f"- {l}" for l in report.known_limitations],
    "",
    "## Next Human Actions",
    *[f"- {a}" for a in report.next_human_actions],
    "",
    "## Artifact Trace",
    *[f"- {t}" for t in report.artifact_trace[:20]],
    "",
    "## Safety",
  ])
  for notice in VALIDATION_SAFETY_NOTICES:
    lines.append(f"- {notice}")
  text = "\n".join(lines)
  _assert_no_secrets(text)
  return text


def pack_to_markdown(pack: V8ThreeCaseValidationPack) -> str:
  lines = [
    "# Three Case Validation Pack",
    "",
    f"- pack_id: {pack.pack_id}",
    f"- generated_at: {pack.generated_at}",
    f"- overall_status: {pack.overall_status}",
    f"- no_email_send: {pack.no_email_send}",
    f"- no_scheduler_start: {pack.no_scheduler_start}",
    "",
    "## 3案件サマリー",
    "",
    "| case_id | readiness_for_demo | overall_status | gaps |",
    "| --- | --- | --- | --- |",
  ]
  for report in pack.cases:
    lines.append(
      f"| {report.case_id} | {report.readiness_for_demo} | {report.overall_status} | {report.gap_count} |",
    )
  lines.extend([
    "",
    "## Common Blocking Issues",
    *[f"- {b}" for b in pack.common_blocking_issues],
    "",
    "## Common Next Actions",
    *[f"- {a}" for a in pack.common_next_actions],
    "",
    pack.demo_readiness_summary,
    "",
    pack.cloud_readiness_summary,
    "",
    "## Safety Notices",
    *[f"- {n}" for n in VALIDATION_SAFETY_NOTICES],
    "",
    "## Next Phases",
    *[f"- {p}" for p in VALIDATION_NEXT_PHASES],
  ])
  text = "\n".join(lines)
  _assert_no_secrets(text)
  return text


def write_excel_validation_pack(pack: V8ThreeCaseValidationPack, path: Path) -> str:
  try:
    import pandas as pd

    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
      pd.DataFrame([{
        "pack_id": pack.pack_id,
        "overall_status": pack.overall_status,
        "total_cases": pack.total_cases,
        "ready_case_count": pack.ready_case_count,
        "warning_case_count": pack.warning_case_count,
        "fail_case_count": pack.fail_case_count,
      }]).to_excel(writer, sheet_name="Pack Summary", index=False)

      case_rows = [{
        "case_id": r.case_id,
        "case_name": r.case_name,
        "overall_status": r.overall_status,
        "readiness_for_demo": r.readiness_for_demo,
        "gap_count": r.gap_count,
        "claim_map_count": r.claim_map_count,
      } for r in pack.cases]
      pd.DataFrame(case_rows).to_excel(writer, sheet_name="Case Reports", index=False)

      step_rows = []
      for report in pack.cases:
        for step in report.step_results:
          step_rows.append({
            "case_id": report.case_id,
            "step_id": step.step_id,
            "status": step.status,
            "summary": step.summary,
          })
      pd.DataFrame(step_rows).to_excel(writer, sheet_name="Step Results", index=False)

      blocking_rows = [{"issue": b} for b in pack.common_blocking_issues]
      pd.DataFrame(blocking_rows).to_excel(writer, sheet_name="Blocking Issues", index=False)

      action_rows = [{"action": a} for a in pack.common_next_actions]
      pd.DataFrame(action_rows).to_excel(writer, sheet_name="Next Actions", index=False)

      trace_rows = []
      for report in pack.cases:
        for t in report.artifact_trace:
          trace_rows.append({"case_id": report.case_id, "trace": t})
      pd.DataFrame(trace_rows or [{"trace": "(none)"}]).to_excel(writer, sheet_name="Artifact Trace", index=False)

      pd.DataFrame({"warning": list(VALIDATION_SAFETY_NOTICES)}).to_excel(writer, sheet_name="Warnings", index=False)
    return ""
  except Exception as exc:
    return f"Excel export skipped: {exc}"


def export_validation_pack(
  pack: V8ThreeCaseValidationPack,
  *,
  project_root: Path | str | None = None,
) -> V8ThreeCaseValidationExport:
  root = Path(project_root) if project_root else Path.cwd()
  slug = pack.generated_at.replace(":", "").replace("-", "").replace("+00:00", "Z")
  output_dir = get_v8_case_validation_dir(root) / f"three_case_pack_{slug}"
  output_dir.mkdir(parents=True, exist_ok=True)

  json_path = output_dir / "three_case_validation_pack.json"
  md_path = output_dir / "three_case_validation_pack.md"
  xlsx_path = output_dir / "three_case_validation_pack.xlsx"
  manifest_path = output_dir / "three_case_validation_manifest.json"
  demo_path = output_dir / "demo_readiness_summary.md"
  cloud_path = output_dir / "cloud_readiness_summary.md"

  case_report_paths: dict[str, str] = {}
  for report in pack.cases:
    case_md = output_dir / f"{report.case_id}_validation_report.md"
    case_md.write_text(case_report_to_markdown(report), encoding="utf-8")
    case_report_paths[report.case_id] = str(case_md)

  json_path.write_text(json.dumps(pack.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
  md_path.write_text(pack_to_markdown(pack), encoding="utf-8")
  demo_path.write_text(pack.demo_readiness_summary, encoding="utf-8")
  cloud_path.write_text(pack.cloud_readiness_summary, encoding="utf-8")
  excel_warning = write_excel_validation_pack(pack, xlsx_path)

  manifest: dict[str, Any] = {
    "export_id": pack.pack_id,
    "generated_at": pack.generated_at,
    "overall_status": pack.overall_status,
    "readiness_by_case": {r.case_id: r.readiness_for_demo for r in pack.cases},
    "common_blocking_issues": pack.common_blocking_issues,
    "common_next_actions": pack.common_next_actions,
    "safety_notices": list(VALIDATION_SAFETY_NOTICES),
    "next_phase_connections": list(VALIDATION_NEXT_PHASES),
    "files": {
      "three_case_validation_pack_json": str(json_path),
      "three_case_validation_pack_md": str(md_path),
      "three_case_validation_pack_xlsx": str(xlsx_path),
      "demo_readiness_summary_md": str(demo_path),
      "cloud_readiness_summary_md": str(cloud_path),
      **{f"{cid}_report_md": p for cid, p in case_report_paths.items()},
    },
    "excel_warning": excel_warning,
  }
  manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2)
  _assert_no_secrets(manifest_text)
  manifest_path.write_text(manifest_text, encoding="utf-8")

  pack.artifact_paths = [str(output_dir), str(manifest_path)]

  return V8ThreeCaseValidationExport(
    export_id=pack.pack_id,
    output_dir=str(output_dir),
    json_path=str(json_path),
    md_path=str(md_path),
    xlsx_path=str(xlsx_path),
    manifest_path=str(manifest_path),
    demo_readiness_path=str(demo_path),
    cloud_readiness_path=str(cloud_path),
    case_report_paths=case_report_paths,
    created_at=pack.generated_at,
    excel_warning=excel_warning,
  )
