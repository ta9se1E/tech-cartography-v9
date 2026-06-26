"""v8 Gap / Next Actions export (Phase 27G)."""

from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from typing import Any

from tech_cartography.runtime.live_artifact_paths import get_live_outputs_root
from tech_cartography.runtime.v8_gap_next_actions_schema import (
  GAP_NEXT_ACTIONS_SAFETY_NOTICES,
  GAP_NEXT_PHASES,
  V8EvidenceGapRecord,
  V8GapNextActionsExport,
  V8GapNextActionsReport,
  V8NextVerificationAction,
)

V8_GAP_NEXT_ACTIONS_SUBDIR = "v8_gap_next_actions"
LOCAL_V8_GAP_NEXT_ACTIONS_SUBDIR = "local_v8_gap_next_actions"

_SENSITIVE_RE = re.compile(
  r"(smtp_password|tavily_api_key|api[_-]?key\s*[:=]|authorization|oauth|jwt|eyJhbGci)",
  re.IGNORECASE,
)

GAP_CSV_COLUMNS: tuple[str, ...] = (
  "gap_id",
  "case_id",
  "publication_number",
  "claim_no",
  "gap_type",
  "gap_title",
  "gap_description",
  "why_it_matters",
  "severity_label",
  "urgency_label",
  "confidence_label",
  "related_source_titles",
  "human_review_required",
)

ACTION_CSV_COLUMNS: tuple[str, ...] = (
  "action_id",
  "case_id",
  "action_rank",
  "action_type",
  "action_title",
  "action_description",
  "target_publication_number",
  "target_claim_no",
  "expected_output",
  "estimated_effort_label",
  "priority_reason",
  "owner_suggestion",
  "watch_profile_update_hint",
  "scheduler_followup_hint",
  "email_digest_hint",
)


def get_v8_gap_next_actions_dir(project_root: Path | str | None = None) -> Path:
  root = get_live_outputs_root(project_root)
  if root.name == "outputs" or not str(root).endswith("live"):
    return root / LOCAL_V8_GAP_NEXT_ACTIONS_SUBDIR
  return root / V8_GAP_NEXT_ACTIONS_SUBDIR


def find_latest_gap_next_actions_dir(
  case_id: str | None = None,
  project_root: Path | str | None = None,
) -> Path | None:
  base = get_v8_gap_next_actions_dir(project_root)
  if not base.is_dir():
    return None
  if case_id:
    dirs = sorted(
      (p for p in base.iterdir() if p.is_dir() and p.name.startswith(f"{case_id}_")),
      key=lambda p: p.stat().st_mtime,
      reverse=True,
    )
    return dirs[0] if dirs else None
  dirs = sorted((p for p in base.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True)
  return dirs[0] if dirs else None


def _assert_no_secrets(text: str) -> None:
  if _SENSITIVE_RE.search(text):
    raise ValueError("export content must not contain secret-like strings")


def _join(items: list[str]) -> str:
  return "; ".join(items)


def gaps_to_csv_text(gaps: list[V8EvidenceGapRecord]) -> str:
  buffer = io.StringIO()
  writer = csv.DictWriter(buffer, fieldnames=list(GAP_CSV_COLUMNS))
  writer.writeheader()
  for gap in gaps:
    writer.writerow({
      "gap_id": gap.gap_id,
      "case_id": gap.case_id,
      "publication_number": gap.publication_number,
      "claim_no": gap.claim_no,
      "gap_type": gap.gap_type,
      "gap_title": gap.gap_title,
      "gap_description": gap.gap_description,
      "why_it_matters": gap.why_it_matters,
      "severity_label": gap.severity_label,
      "urgency_label": gap.urgency_label,
      "confidence_label": gap.confidence_label,
      "related_source_titles": _join(gap.related_source_titles),
      "human_review_required": gap.human_review_required,
    })
  text = buffer.getvalue()
  _assert_no_secrets(text)
  return text


def actions_to_csv_text(actions: list[V8NextVerificationAction]) -> str:
  buffer = io.StringIO()
  writer = csv.DictWriter(buffer, fieldnames=list(ACTION_CSV_COLUMNS))
  writer.writeheader()
  for action in actions:
    writer.writerow({
      "action_id": action.action_id,
      "case_id": action.case_id,
      "action_rank": action.action_rank,
      "action_type": action.action_type,
      "action_title": action.action_title,
      "action_description": action.action_description,
      "target_publication_number": action.target_publication_number,
      "target_claim_no": action.target_claim_no,
      "expected_output": action.expected_output,
      "estimated_effort_label": action.estimated_effort_label,
      "priority_reason": action.priority_reason,
      "owner_suggestion": action.owner_suggestion,
      "watch_profile_update_hint": action.watch_profile_update_hint,
      "scheduler_followup_hint": action.scheduler_followup_hint,
      "email_digest_hint": action.email_digest_hint,
    })
  text = buffer.getvalue()
  _assert_no_secrets(text)
  return text


def gap_next_actions_to_markdown(report: V8GapNextActionsReport) -> str:
  lines = [
    f"# Gap / Next Actions — {report.case_id}",
    "",
    f"- publication_number: {report.publication_number}",
    f"- generated_at: {report.generated_at}",
    f"- gap_count: {report.gap_count}",
    f"- action_count: {report.action_count}",
    "",
    "## Safety",
  ]
  for notice in GAP_NEXT_ACTIONS_SAFETY_NOTICES:
    lines.append(f"- {notice}")
  lines.extend([
    "",
    "## Top 3 Next Actions",
  ])
  for action in report.top_3_actions:
    lines.append(
      f"{action.action_rank}. **{action.action_title}** ({action.action_type}) — "
      f"{action.target_publication_number} claim {action.target_claim_no}",
    )
    lines.append(f"   - expected_output: {action.expected_output}")
    lines.append(f"   - priority_reason: {action.priority_reason}")
  lines.extend([
    "",
    "## Gap 一覧",
    "",
    "| gap_type | gap_title | severity | urgency | claim_no |",
    "| --- | --- | --- | --- | --- |",
  ])
  for gap in report.gaps[:30]:
    lines.append(
      f"| {gap.gap_type} | {gap.gap_title} | {gap.severity_label} | "
      f"{gap.urgency_label} | {gap.claim_no} |",
    )
  lines.extend([
    "",
    f"## count_by_gap_type",
    f"```json\n{json.dumps(report.count_by_gap_type, ensure_ascii=False, indent=2)}\n```",
    "",
    f"## count_by_action_type",
    f"```json\n{json.dumps(report.count_by_action_type, ensure_ascii=False, indent=2)}\n```",
    "",
    "## Watch Profile Update Proposal",
    report.watch_profile_update_proposal,
    "",
    "## Digest Summary",
    report.digest_summary,
    "",
    "## Artifact trace",
  ])
  for path in report.source_artifact_paths:
    lines.append(f"- {path}")
  for path in report.evidence_map_artifact_paths:
    lines.append(f"- evidence_map: {path}")
  lines.extend(["", "## Next phases", *[f"- {p}" for p in GAP_NEXT_PHASES]])
  if report.warnings:
    lines.extend(["", "## Warnings", *[f"- {w}" for w in report.warnings]])
  text = "\n".join(lines)
  _assert_no_secrets(text)
  return text


def write_excel_gap_next_actions(report: V8GapNextActionsReport, path: Path) -> str:
  try:
    import pandas as pd

    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
      gap_rows = [g.to_dict() for g in report.gaps]
      for row in gap_rows:
        for col in ("technical_axis_labels", "related_source_titles", "caution_flags"):
          row[col] = _join(row.get(col) or [])
      pd.DataFrame(gap_rows or [{"gap_title": "(none)"}]).to_excel(writer, sheet_name="Gaps", index=False)

      action_rows = [a.to_dict() for a in report.next_actions]
      for row in action_rows:
        row["caution_flags"] = _join(row.get("caution_flags") or [])
      pd.DataFrame(action_rows or [{"action_title": "(none)"}]).to_excel(
        writer, sheet_name="Next Actions", index=False,
      )

      top_rows = [a.to_dict() for a in report.top_3_actions]
      pd.DataFrame(top_rows or [{"action_title": "(none)"}]).to_excel(
        writer, sheet_name="Top 3 Actions", index=False,
      )

      pd.DataFrame({"proposal": report.watch_profile_update_proposal.splitlines()}).to_excel(
        writer, sheet_name="Watch Profile Proposal", index=False,
      )
      pd.DataFrame({"digest": report.digest_summary.splitlines()}).to_excel(
        writer, sheet_name="Digest Summary", index=False,
      )
      pd.DataFrame({"warning": report.warnings or ["(none)"]}).to_excel(
        writer, sheet_name="Warnings", index=False,
      )
    return ""
  except Exception as exc:
    return f"Excel export skipped: {exc}"


def export_gap_next_actions(
  report: V8GapNextActionsReport,
  *,
  project_root: Path | str | None = None,
) -> V8GapNextActionsExport:
  root = Path(project_root) if project_root else Path.cwd()
  slug = report.generated_at.replace(":", "").replace("-", "").replace("+00:00", "Z")
  pub_slug = report.publication_number.replace("/", "_") or "all"
  output_dir = get_v8_gap_next_actions_dir(root) / f"{report.case_id}_{pub_slug}_{slug}"
  output_dir.mkdir(parents=True, exist_ok=True)

  csv_path = output_dir / "gap_next_actions.csv"
  md_path = output_dir / "gap_next_actions.md"
  xlsx_path = output_dir / "gap_next_actions.xlsx"
  manifest_path = output_dir / "gap_next_actions_manifest.json"
  watch_path = output_dir / "watch_profile_update_proposal.md"
  digest_path = output_dir / "digest_summary.md"

  combined_csv = gaps_to_csv_text(report.gaps) + "\n" + actions_to_csv_text(report.next_actions)
  csv_path.write_text(combined_csv, encoding="utf-8")
  md_path.write_text(gap_next_actions_to_markdown(report), encoding="utf-8")
  watch_path.write_text(report.watch_profile_update_proposal, encoding="utf-8")
  digest_path.write_text(report.digest_summary, encoding="utf-8")
  excel_warning = write_excel_gap_next_actions(report, xlsx_path)

  manifest: dict[str, Any] = {
    "export_id": report.report_id,
    "case_id": report.case_id,
    "publication_number": report.publication_number,
    "generated_at": report.generated_at,
    "gap_count": report.gap_count,
    "action_count": report.action_count,
    "count_by_gap_type": report.count_by_gap_type,
    "count_by_action_type": report.count_by_action_type,
    "count_by_urgency": report.count_by_urgency,
    "source_artifact_paths": report.source_artifact_paths,
    "evidence_map_artifact_paths": report.evidence_map_artifact_paths,
    "safety_notices": list(GAP_NEXT_ACTIONS_SAFETY_NOTICES),
    "next_phase_connections": list(GAP_NEXT_PHASES),
    "files": {
      "gap_next_actions_csv": str(csv_path),
      "gap_next_actions_md": str(md_path),
      "gap_next_actions_xlsx": str(xlsx_path),
      "watch_profile_update_proposal_md": str(watch_path),
      "digest_summary_md": str(digest_path),
    },
    "excel_warning": excel_warning,
  }
  manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2)
  _assert_no_secrets(manifest_text)
  manifest_path.write_text(manifest_text, encoding="utf-8")

  return V8GapNextActionsExport(
    export_id=report.report_id,
    case_id=report.case_id,
    publication_number=report.publication_number,
    output_dir=str(output_dir),
    csv_path=str(csv_path),
    md_path=str(md_path),
    xlsx_path=str(xlsx_path),
    manifest_path=str(manifest_path),
    watch_profile_proposal_path=str(watch_path),
    digest_summary_path=str(digest_path),
    created_at=report.generated_at,
    excel_warning=excel_warning,
  )
