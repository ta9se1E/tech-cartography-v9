"""v8 Sources Export Package builder (Phase 27C)."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from tech_cartography.runtime.live_artifact_paths import get_live_outputs_root
from tech_cartography.runtime.v8_sources_schema import (
  FIXED_POINT_OBSERVATION_NOTE,
  NEXT_PHASE_PLACEHOLDERS,
  SAFETY_EXPORT_NOTICES,
  V8SourceExportPackage,
  V8SourceRecord,
  V8SourcesTable,
  utc_now_iso,
)
from tech_cartography.services.v8_sources_repository import resolve_case_name

V8_EXPORT_PACKAGES_SUBDIR = "v8_export_packages"
LOCAL_V8_EXPORT_PACKAGES_SUBDIR = "local_v8_export_packages"

_SENSITIVE_RE = re.compile(
  r"(smtp_password|tavily_api_key|api[_-]?key\s*[:=]|authorization|oauth|jwt|eyJhbGci)",
  re.IGNORECASE,
)

CSV_COLUMNS: tuple[str, ...] = (
  "source_id",
  "case_id",
  "source_type",
  "title",
  "organization",
  "year",
  "url",
  "publication_number",
  "doi",
  "source_status",
  "evidence_role",
  "reliability_label",
  "verification_status",
  "candidate_information_only",
  "human_review_required",
  "notes",
)


def get_v8_export_packages_dir(project_root: Path | str | None = None) -> Path:
  root = get_live_outputs_root(project_root)
  if root.name == "outputs" or not str(root).endswith("live"):
    return root / LOCAL_V8_EXPORT_PACKAGES_SUBDIR
  return root / V8_EXPORT_PACKAGES_SUBDIR


def _assert_no_secrets(text: str) -> None:
  if _SENSITIVE_RE.search(text):
    raise ValueError("export content must not contain secret-like strings")


def records_to_csv_text(records: list[V8SourceRecord]) -> str:
  import io

  buffer = io.StringIO()
  writer = csv.DictWriter(buffer, fieldnames=list(CSV_COLUMNS))
  writer.writeheader()
  for record in records:
    row = {col: getattr(record, col) for col in CSV_COLUMNS}
    writer.writerow(row)
  text = buffer.getvalue()
  _assert_no_secrets(text)
  return text


def records_to_markdown(
  records: list[V8SourceRecord],
  *,
  case_name: str,
  table: V8SourcesTable,
) -> str:
  lines = [
    f"# v8 Sources — {case_name}",
    "",
    f"- generated_at: {utc_now_iso()}",
    f"- source_count: {table.source_count}",
    f"- count_by_type: {json.dumps(table.count_by_type, ensure_ascii=False)}",
    "",
    "## Safety notices",
  ]
  for notice in SAFETY_EXPORT_NOTICES:
    lines.append(f"- {notice}")
  lines.extend(["", "## Sources", ""])
  for record in records:
    lines.extend(
      [
        f"### {record.title or record.source_id}",
        f"- source_id: `{record.source_id}`",
        f"- case_id: {record.case_id}",
        f"- source_type: {record.source_type}",
        f"- organization: {record.organization}",
        f"- year: {record.year}",
        f"- publication_number: {record.publication_number}",
        f"- doi: {record.doi}",
        f"- url: {record.url}",
        f"- evidence_role: {record.evidence_role}",
        f"- reliability_label: {record.reliability_label}",
        f"- verification_status: {record.verification_status}",
        f"- candidate_information_only: {record.candidate_information_only}",
        f"- human_review_required: {record.human_review_required}",
        f"- notes: {record.notes}",
        "",
      ],
    )
  text = "\n".join(lines)
  _assert_no_secrets(text)
  return text


def build_export_summary_md(
  *,
  case_id: str,
  case_name: str,
  table: V8SourcesTable,
  output_dir: Path,
  excel_warning: str = "",
) -> str:
  lines = [
    "# v8 Export Summary",
    "",
    f"- case_id: {case_id}",
    f"- case_name: {case_name}",
    f"- generated_at: {utc_now_iso()}",
    f"- source_count: {table.source_count}",
    f"- count_by_type: {json.dumps(table.count_by_type, ensure_ascii=False)}",
    f"- count_by_evidence_role: {json.dumps(table.count_by_evidence_role, ensure_ascii=False)}",
    f"- excluded_or_duplicate_count: {table.excluded_or_duplicate_count}",
    "",
    "## Warnings",
  ]
  if table.warnings:
    lines.extend(f"- {w}" for w in table.warnings)
  else:
    lines.append("- (none)")
  if excel_warning:
    lines.extend(["", "## Excel", f"- {excel_warning}"])
  lines.extend(["", "## Safety", *[f"- {n}" for n in SAFETY_EXPORT_NOTICES]])
  lines.extend(["", "## Fixed-point observation", f"- {FIXED_POINT_OBSERVATION_NOTE}"])
  lines.extend(["", "## Next phases", *[f"- {p}" for p in NEXT_PHASE_PLACEHOLDERS]])
  lines.extend(["", "## Output files", f"- directory: `{output_dir}`"])
  text = "\n".join(lines)
  _assert_no_secrets(text)
  return text


def write_excel_package(
  *,
  records: list[V8SourceRecord],
  table: V8SourcesTable,
  path: Path,
) -> str:
  try:
    import pandas as pd

    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
      pd.DataFrame([record.to_dict() for record in records]).to_excel(writer, sheet_name="Sources", index=False)
      summary_rows = [
        {"metric": "source_count", "value": table.source_count},
        {"metric": "count_by_type", "value": json.dumps(table.count_by_type, ensure_ascii=False)},
        {"metric": "count_by_evidence_role", "value": json.dumps(table.count_by_evidence_role, ensure_ascii=False)},
      ]
      pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)
      warn_df = pd.DataFrame({"warning": table.warnings or ["(none)"]})
      warn_df.to_excel(writer, sheet_name="Warnings", index=False)
    return ""
  except Exception as exc:
    return f"Excel export skipped: {exc}"


def build_export_package(
  table: V8SourcesTable,
  *,
  case_id: str = "all",
  project_root: Path | str | None = None,
) -> V8SourceExportPackage:
  root = Path(project_root) if project_root else Path.cwd()
  case_name = resolve_case_name(case_id, root)
  generated_at = utc_now_iso()
  slug = generated_at.replace(":", "").replace("-", "").replace("+00:00", "Z")
  safe_case = case_id.replace("/", "_") or "all"
  output_dir = get_v8_export_packages_dir(root) / f"{safe_case}_{slug}"
  output_dir.mkdir(parents=True, exist_ok=True)

  records = table.records
  csv_path = output_dir / "sources.csv"
  md_path = output_dir / "sources.md"
  xlsx_path = output_dir / "sources.xlsx"
  summary_path = output_dir / "export_summary.md"
  manifest_path = output_dir / "export_manifest.json"

  csv_text = records_to_csv_text(records)
  csv_path.write_text(csv_text, encoding="utf-8")
  md_path.write_text(records_to_markdown(records, case_name=case_name, table=table), encoding="utf-8")
  excel_warning = write_excel_package(records=records, table=table, path=xlsx_path)

  summary_md = build_export_summary_md(
    case_id=case_id,
    case_name=case_name,
    table=table,
    output_dir=output_dir,
    excel_warning=excel_warning,
  )
  summary_path.write_text(summary_md, encoding="utf-8")

  manifest: dict[str, Any] = {
    "case_id": case_id,
    "case_name": case_name,
    "generated_at": generated_at,
    "source_count": table.source_count,
    "count_by_type": table.count_by_type,
    "count_by_evidence_role": table.count_by_evidence_role,
    "warnings": table.warnings,
    "candidate_information_only_notice": SAFETY_EXPORT_NOTICES[0],
    "human_review_required_notice": SAFETY_EXPORT_NOTICES[1],
    "no_legal_judgement_notice": SAFETY_EXPORT_NOTICES[2],
    "fixed_point_observation_note": FIXED_POINT_OBSERVATION_NOTE,
    "next_phase_placeholders": list(NEXT_PHASE_PLACEHOLDERS),
    "files": {
      "sources_csv": str(csv_path),
      "sources_md": str(md_path),
      "sources_xlsx": str(xlsx_path),
      "export_summary_md": str(summary_path),
    },
    "excel_warning": excel_warning,
  }
  manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2)
  _assert_no_secrets(manifest_text)
  manifest_path.write_text(manifest_text, encoding="utf-8")

  for record in records:
    record.artifact_path = str(output_dir)

  return V8SourceExportPackage(
    case_id=case_id,
    case_name=case_name,
    generated_at=generated_at,
    source_count=table.source_count,
    count_by_type=table.count_by_type,
    count_by_evidence_role=table.count_by_evidence_role,
    warnings=table.warnings,
    output_dir=str(output_dir),
    manifest_path=str(manifest_path),
    sources_csv_path=str(csv_path),
    sources_md_path=str(md_path),
    sources_xlsx_path=str(xlsx_path),
    export_summary_path=str(summary_path),
    excel_warning=excel_warning,
  )
