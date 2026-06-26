"""v8 Claim Map export (Phase 27E)."""

from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from typing import Any

from tech_cartography.runtime.live_artifact_paths import get_live_outputs_root
from tech_cartography.runtime.v8_claim_map_schema import (
  CLAIM_MAP_NEXT_PHASES,
  CLAIM_MAP_SAFETY_NOTICES,
  V8ClaimMap,
  V8ClaimMapExport,
  V8ClaimRecord,
)

V8_CLAIM_MAPS_SUBDIR = "v8_claim_maps"
LOCAL_V8_CLAIM_MAPS_SUBDIR = "local_v8_claim_maps"

_SENSITIVE_RE = re.compile(
  r"(smtp_password|tavily_api_key|api[_-]?key\s*[:=]|authorization|oauth|jwt|eyJhbGci)",
  re.IGNORECASE,
)

CSV_COLUMNS: tuple[str, ...] = (
  "claim_id",
  "case_id",
  "publication_number",
  "patent_title",
  "claim_no",
  "claim_text_status",
  "primary_axis",
  "technical_axis_labels",
  "material_terms",
  "process_terms",
  "property_terms",
  "structure_terms",
  "application_terms",
  "evidence_needed",
  "evidence_priority",
  "why_this_claim_matters",
  "next_evidence_check",
  "human_review_required",
  "caution_flags",
)


def get_v8_claim_maps_dir(project_root: Path | str | None = None) -> Path:
  root = get_live_outputs_root(project_root)
  if root.name == "outputs" or not str(root).endswith("live"):
    return root / LOCAL_V8_CLAIM_MAPS_SUBDIR
  return root / V8_CLAIM_MAPS_SUBDIR


def find_latest_claim_map_dir(
  case_id: str | None = None,
  project_root: Path | str | None = None,
) -> Path | None:
  base = get_v8_claim_maps_dir(project_root)
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


def _join_list(items: list[str]) -> str:
  return "; ".join(items)


def claim_map_to_csv_text(records: list[V8ClaimRecord]) -> str:
  buffer = io.StringIO()
  writer = csv.DictWriter(buffer, fieldnames=list(CSV_COLUMNS) + ["claim_text"])
  writer.writeheader()
  for rec in records:
    row = {col: getattr(rec, col, "") for col in CSV_COLUMNS}
    for list_col in (
      "technical_axis_labels",
      "material_terms",
      "process_terms",
      "property_terms",
      "structure_terms",
      "application_terms",
      "evidence_needed",
      "caution_flags",
    ):
      row[list_col] = _join_list(getattr(rec, list_col, []))
    row["claim_text"] = rec.claim_text
    writer.writerow(row)
  text = buffer.getvalue()
  _assert_no_secrets(text)
  return text


def claim_map_to_markdown(claim_map: V8ClaimMap) -> str:
  lines = [
    f"# Claim Map — {claim_map.case_id}",
    "",
    f"- publication_number: {claim_map.publication_number}",
    f"- generated_at: {claim_map.generated_at}",
    f"- claim_count: {claim_map.claim_count}",
    f"- loaded_claim_count: {claim_map.loaded_claim_count}",
    f"- not_loaded_claim_count: {claim_map.not_loaded_claim_count}",
    "",
    "## Safety",
  ]
  for notice in CLAIM_MAP_SAFETY_NOTICES:
    lines.append(f"- {notice}")
  lines.extend([
    "",
    "## Summary",
    f"- count_by_axis: {json.dumps(claim_map.count_by_axis, ensure_ascii=False)}",
    f"- count_by_evidence_needed: {json.dumps(claim_map.count_by_evidence_needed, ensure_ascii=False)}",
    "",
    "## Claim Map",
    "",
    "| claim_no | publication_number | status | primary_axis | evidence_needed |",
    "| --- | --- | --- | --- | --- |",
  ])
  for rec in claim_map.records:
    lines.append(
      f"| {rec.claim_no} | {rec.publication_number} | {rec.claim_text_status} | "
      f"{rec.primary_axis} | {_join_list(rec.evidence_needed)} |",
    )
  lines.append("")
  for rec in claim_map.records:
    lines.extend([
      f"### Claim {rec.claim_no} — {rec.publication_number}",
      f"- claim_text_status: {rec.claim_text_status}",
      f"- technical_axis_labels: {_join_list(rec.technical_axis_labels)}",
      f"- material_terms: {_join_list(rec.material_terms)}",
      f"- process_terms: {_join_list(rec.process_terms)}",
      f"- property_terms: {_join_list(rec.property_terms)}",
      f"- next_evidence_check: {rec.next_evidence_check}",
      f"- caution_flags: {_join_list(rec.caution_flags)}",
      "",
    ])
  lines.extend(["## Next phases", *[f"- {p}" for p in CLAIM_MAP_NEXT_PHASES]])
  if claim_map.warnings:
    lines.extend(["", "## Warnings", *[f"- {w}" for w in claim_map.warnings]])
  text = "\n".join(lines)
  _assert_no_secrets(text)
  return text


def write_excel_claim_map(claim_map: V8ClaimMap, path: Path) -> str:
  try:
    import pandas as pd

    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
      rows = []
      for rec in claim_map.records:
        row = rec.to_dict()
        for list_col in (
          "technical_axis_labels",
          "material_terms",
          "process_terms",
          "property_terms",
          "structure_terms",
          "application_terms",
          "condition_terms",
          "evidence_needed",
          "caution_flags",
        ):
          row[list_col] = _join_list(row.get(list_col) or [])
        rows.append(row)
      pd.DataFrame(rows).to_excel(writer, sheet_name="Claim Map", index=False)
      summary = {
        "metric": [
          "claim_count",
          "loaded_claim_count",
          "not_loaded_claim_count",
        ],
        "value": [
          claim_map.claim_count,
          claim_map.loaded_claim_count,
          claim_map.not_loaded_claim_count,
        ],
      }
      pd.DataFrame(summary).to_excel(writer, sheet_name="Summary", index=False)
      pd.DataFrame({"warning": claim_map.warnings or ["(none)"]}).to_excel(
        writer, sheet_name="Warnings", index=False,
      )
    return ""
  except Exception as exc:
    return f"Excel export skipped: {exc}"


def export_claim_map(
  claim_map: V8ClaimMap,
  *,
  project_root: Path | str | None = None,
) -> V8ClaimMapExport:
  root = Path(project_root) if project_root else Path.cwd()
  slug = claim_map.generated_at.replace(":", "").replace("-", "").replace("+00:00", "Z")
  pub_slug = claim_map.publication_number.replace("/", "_") or "all"
  output_dir = get_v8_claim_maps_dir(root) / f"{claim_map.case_id}_{pub_slug}_{slug}"
  output_dir.mkdir(parents=True, exist_ok=True)

  csv_path = output_dir / "claim_map.csv"
  md_path = output_dir / "claim_map.md"
  xlsx_path = output_dir / "claim_map.xlsx"
  manifest_path = output_dir / "claim_map_manifest.json"

  csv_path.write_text(claim_map_to_csv_text(claim_map.records), encoding="utf-8")
  md_path.write_text(claim_map_to_markdown(claim_map), encoding="utf-8")
  excel_warning = write_excel_claim_map(claim_map, xlsx_path)

  manifest: dict[str, Any] = {
    "case_id": claim_map.case_id,
    "publication_number": claim_map.publication_number,
    "generated_at": claim_map.generated_at,
    "claim_count": claim_map.claim_count,
    "loaded_claim_count": claim_map.loaded_claim_count,
    "not_loaded_claim_count": claim_map.not_loaded_claim_count,
    "count_by_axis": claim_map.count_by_axis,
    "count_by_evidence_needed": claim_map.count_by_evidence_needed,
    "warnings": claim_map.warnings,
    "safety_notices": list(CLAIM_MAP_SAFETY_NOTICES),
    "next_phase_connections": list(CLAIM_MAP_NEXT_PHASES),
    "files": {
      "claim_map_csv": str(csv_path),
      "claim_map_md": str(md_path),
      "claim_map_xlsx": str(xlsx_path),
    },
    "excel_warning": excel_warning,
  }
  manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2)
  _assert_no_secrets(manifest_text)
  manifest_path.write_text(manifest_text, encoding="utf-8")

  return V8ClaimMapExport(
    case_id=claim_map.case_id,
    publication_number=claim_map.publication_number,
    generated_at=claim_map.generated_at,
    output_dir=str(output_dir),
    csv_path=str(csv_path),
    md_path=str(md_path),
    xlsx_path=str(xlsx_path),
    manifest_path=str(manifest_path),
    excel_warning=excel_warning,
  )
