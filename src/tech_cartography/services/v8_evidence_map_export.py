"""v8 Evidence Map export (Phase 27F)."""

from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from typing import Any

from tech_cartography.runtime.live_artifact_paths import get_live_outputs_root
from tech_cartography.runtime.v8_evidence_map_schema import (
  EVIDENCE_MAP_NEXT_PHASES,
  EVIDENCE_MAP_SAFETY_NOTICES,
  V8EvidenceLink,
  V8EvidenceMap,
  V8EvidenceMapExport,
)

V8_EVIDENCE_MAPS_SUBDIR = "v8_evidence_maps"
LOCAL_V8_EVIDENCE_MAPS_SUBDIR = "local_v8_evidence_maps"

_SENSITIVE_RE = re.compile(
  r"(smtp_password|tavily_api_key|api[_-]?key\s*[:=]|authorization|oauth|jwt|eyJhbGci)",
  re.IGNORECASE,
)

CSV_COLUMNS: tuple[str, ...] = (
  "evidence_link_id",
  "case_id",
  "publication_number",
  "claim_no",
  "claim_text_status",
  "primary_axis",
  "source_type",
  "source_title",
  "evidence_role",
  "support_type",
  "support_level",
  "match_reason",
  "matched_terms",
  "evidence_gap",
  "next_verification_action",
  "human_review_required",
  "caution_flags",
)


def get_v8_evidence_maps_dir(project_root: Path | str | None = None) -> Path:
  root = get_live_outputs_root(project_root)
  if root.name == "outputs" or not str(root).endswith("live"):
    return root / LOCAL_V8_EVIDENCE_MAPS_SUBDIR
  return root / V8_EVIDENCE_MAPS_SUBDIR


def find_latest_evidence_map_dir(
  case_id: str | None = None,
  project_root: Path | str | None = None,
) -> Path | None:
  base = get_v8_evidence_maps_dir(project_root)
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


def evidence_map_to_csv_text(links: list[V8EvidenceLink]) -> str:
  buffer = io.StringIO()
  writer = csv.DictWriter(buffer, fieldnames=list(CSV_COLUMNS))
  writer.writeheader()
  for link in links:
    writer.writerow({
      "evidence_link_id": link.evidence_link_id,
      "case_id": link.case_id,
      "publication_number": link.publication_number,
      "claim_no": link.claim_no,
      "claim_text_status": link.claim_text_status,
      "primary_axis": link.primary_axis,
      "source_type": link.source_type,
      "source_title": link.source_title,
      "evidence_role": link.evidence_role,
      "support_type": link.support_type,
      "support_level": link.support_level,
      "match_reason": link.match_reason,
      "matched_terms": _join(link.matched_terms),
      "evidence_gap": link.evidence_gap,
      "next_verification_action": link.next_verification_action,
      "human_review_required": link.human_review_required,
      "caution_flags": _join(link.caution_flags),
    })
  text = buffer.getvalue()
  _assert_no_secrets(text)
  return text


def evidence_map_to_markdown(evidence_map: V8EvidenceMap) -> str:
  lines = [
    f"# Evidence Map — {evidence_map.case_id}",
    "",
    f"- publication_number: {evidence_map.publication_number}",
    f"- generated_at: {evidence_map.generated_at}",
    f"- link_count: {evidence_map.link_count}",
    f"- claim_count: {evidence_map.claim_count}",
    f"- source_count: {evidence_map.source_count}",
    f"- missing_evidence_count: {evidence_map.missing_evidence_count}",
    f"- claim_text_required_count: {evidence_map.claim_text_required_count}",
    "",
    "## Safety",
  ]
  for notice in EVIDENCE_MAP_SAFETY_NOTICES:
    lines.append(f"- {notice}")
  lines.extend([
    "",
    "## Summary",
    f"- count_by_support_type: {json.dumps(evidence_map.count_by_support_type, ensure_ascii=False)}",
    f"- count_by_support_level: {json.dumps(evidence_map.count_by_support_level, ensure_ascii=False)}",
    "",
    "## Evidence Map",
    "",
    "| claim_no | source_type | support_type | support_level | evidence_gap |",
    "| --- | --- | --- | --- | --- |",
  ])
  for link in evidence_map.links:
    lines.append(
      f"| {link.claim_no} | {link.source_type or '—'} | {link.support_type} | "
      f"{link.support_level} | {link.evidence_gap[:60]} |",
    )
  lines.extend(["", "## Evidence Gap summary"])
  gaps = [link for link in evidence_map.links if link.support_level in {"missing", "needs_human_review"}]
  for link in gaps[:20]:
    lines.append(f"- {link.publication_number} claim {link.claim_no}: {link.evidence_gap}")
  lines.extend(["", "## Next Verification Actions"])
  for link in evidence_map.links[:15]:
    lines.append(f"- {link.next_verification_action}")
  lines.extend(["", "## Next phases", *[f"- {p}" for p in EVIDENCE_MAP_NEXT_PHASES]])
  if evidence_map.warnings:
    lines.extend(["", "## Warnings", *[f"- {w}" for w in evidence_map.warnings]])
  text = "\n".join(lines)
  _assert_no_secrets(text)
  return text


def write_excel_evidence_map(evidence_map: V8EvidenceMap, path: Path) -> str:
  try:
    import pandas as pd

    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
      rows = []
      for link in evidence_map.links:
        row = link.to_dict()
        for col in ("technical_axis_labels", "evidence_needed", "matched_terms", "caution_flags", "source_artifact_paths"):
          row[col] = _join(row.get(col) or [])
        rows.append(row)
      pd.DataFrame(rows).to_excel(writer, sheet_name="Evidence Map", index=False)
      pd.DataFrame({
        "metric": [
          "link_count", "claim_count", "source_count",
          "missing_evidence_count", "claim_text_required_count",
        ],
        "value": [
          evidence_map.link_count, evidence_map.claim_count, evidence_map.source_count,
          evidence_map.missing_evidence_count, evidence_map.claim_text_required_count,
        ],
      }).to_excel(writer, sheet_name="Summary", index=False)
      gap_rows = [
        {"claim_no": l.claim_no, "support_type": l.support_type, "evidence_gap": l.evidence_gap}
        for l in evidence_map.links
        if l.support_level in {"missing", "needs_human_review"}
      ]
      pd.DataFrame(gap_rows or [{"evidence_gap": "(none)"}]).to_excel(writer, sheet_name="Gaps", index=False)
      pd.DataFrame({"warning": evidence_map.warnings or ["(none)"]}).to_excel(writer, sheet_name="Warnings", index=False)
    return ""
  except Exception as exc:
    return f"Excel export skipped: {exc}"


def export_evidence_map(
  evidence_map: V8EvidenceMap,
  *,
  project_root: Path | str | None = None,
) -> V8EvidenceMapExport:
  root = Path(project_root) if project_root else Path.cwd()
  slug = evidence_map.generated_at.replace(":", "").replace("-", "").replace("+00:00", "Z")
  pub_slug = evidence_map.publication_number.replace("/", "_") or "all"
  output_dir = get_v8_evidence_maps_dir(root) / f"{evidence_map.case_id}_{pub_slug}_{slug}"
  output_dir.mkdir(parents=True, exist_ok=True)

  csv_path = output_dir / "evidence_map.csv"
  md_path = output_dir / "evidence_map.md"
  xlsx_path = output_dir / "evidence_map.xlsx"
  manifest_path = output_dir / "evidence_map_manifest.json"

  csv_path.write_text(evidence_map_to_csv_text(evidence_map.links), encoding="utf-8")
  md_path.write_text(evidence_map_to_markdown(evidence_map), encoding="utf-8")
  excel_warning = write_excel_evidence_map(evidence_map, xlsx_path)

  manifest: dict[str, Any] = {
    "export_id": evidence_map.evidence_map_id,
    "case_id": evidence_map.case_id,
    "publication_number": evidence_map.publication_number,
    "generated_at": evidence_map.generated_at,
    "link_count": evidence_map.link_count,
    "missing_evidence_count": evidence_map.missing_evidence_count,
    "claim_text_required_count": evidence_map.claim_text_required_count,
    "count_by_support_type": evidence_map.count_by_support_type,
    "count_by_support_level": evidence_map.count_by_support_level,
    "safety_notices": list(EVIDENCE_MAP_SAFETY_NOTICES),
    "next_phase_connections": list(EVIDENCE_MAP_NEXT_PHASES),
    "files": {
      "evidence_map_csv": str(csv_path),
      "evidence_map_md": str(md_path),
      "evidence_map_xlsx": str(xlsx_path),
    },
    "excel_warning": excel_warning,
  }
  manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2)
  _assert_no_secrets(manifest_text)
  manifest_path.write_text(manifest_text, encoding="utf-8")

  return V8EvidenceMapExport(
    export_id=evidence_map.evidence_map_id,
    case_id=evidence_map.case_id,
    publication_number=evidence_map.publication_number,
    output_dir=str(output_dir),
    csv_path=str(csv_path),
    md_path=str(md_path),
    xlsx_path=str(xlsx_path),
    manifest_path=str(manifest_path),
    created_at=evidence_map.generated_at,
    excel_warning=excel_warning,
  )
