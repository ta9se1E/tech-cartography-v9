"""v8 Patent Shortlist export (Phase 27D)."""

from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from typing import Any

from tech_cartography.runtime.live_artifact_paths import get_live_outputs_root
from tech_cartography.runtime.v8_patent_shortlist_schema import (
  NEXT_PHASE_CONNECTIONS,
  SHORTLIST_SAFETY_NOTICES,
  V8PatentCandidate,
  V8PatentShortlist,
  V8PatentShortlistExport,
)

V8_PATENT_SHORTLISTS_SUBDIR = "v8_patent_shortlists"
LOCAL_V8_PATENT_SHORTLISTS_SUBDIR = "local_v8_patent_shortlists"

_SENSITIVE_RE = re.compile(
  r"(smtp_password|tavily_api_key|api[_-]?key\s*[:=]|authorization|oauth|jwt|eyJhbGci)",
  re.IGNORECASE,
)

CSV_COLUMNS: tuple[str, ...] = (
  "rank",
  "candidate_id",
  "case_id",
  "publication_number",
  "title",
  "assignee_or_organization",
  "year",
  "url",
  "total_score",
  "technical_axis_labels",
  "why_read",
  "expected_evidence_to_check",
  "next_verification_action",
  "human_review_required",
  "caution_flags",
)


def get_v8_patent_shortlists_dir(project_root: Path | str | None = None) -> Path:
  root = get_live_outputs_root(project_root)
  if root.name == "outputs" or not str(root).endswith("live"):
    return root / LOCAL_V8_PATENT_SHORTLISTS_SUBDIR
  return root / V8_PATENT_SHORTLISTS_SUBDIR


def find_latest_patent_shortlist_dir(
  case_id: str | None = None,
  project_root: Path | str | None = None,
) -> Path | None:
  base = get_v8_patent_shortlists_dir(project_root)
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


def shortlist_to_csv_text(candidates: list[V8PatentCandidate]) -> str:
  buffer = io.StringIO()
  writer = csv.DictWriter(buffer, fieldnames=list(CSV_COLUMNS))
  writer.writeheader()
  for c in candidates:
    writer.writerow(
      {
        "rank": c.rank,
        "candidate_id": c.candidate_id,
        "case_id": c.case_id,
        "publication_number": c.publication_number,
        "title": c.title,
        "assignee_or_organization": c.assignee_or_organization,
        "year": c.year,
        "url": c.url,
        "total_score": c.total_score,
        "technical_axis_labels": "; ".join(c.technical_axis_labels),
        "why_read": c.why_read,
        "expected_evidence_to_check": c.expected_evidence_to_check,
        "next_verification_action": c.next_verification_action,
        "human_review_required": c.human_review_required,
        "caution_flags": "; ".join(c.caution_flags),
      },
    )
  text = buffer.getvalue()
  _assert_no_secrets(text)
  return text


def shortlist_to_markdown(shortlist: V8PatentShortlist) -> str:
  lines = [
    f"# Patent Shortlist — {shortlist.case_name}",
    "",
    f"- case_id: {shortlist.case_id}",
    f"- generated_at: {shortlist.generated_at}",
    f"- top_n: {shortlist.top_n}",
    f"- count: {shortlist.count}",
    "",
    "## Safety",
  ]
  for notice in SHORTLIST_SAFETY_NOTICES:
    lines.append(f"- {notice}")
  lines.extend(["", "## Top patents", ""])
  for c in shortlist.patent_candidates:
    lines.extend(
      [
        f"### #{c.rank} {c.publication_number} — {c.title}",
        f"- total_score (reading priority): {c.total_score}",
        f"- organization: {c.assignee_or_organization}",
        f"- year: {c.year}",
        f"- url: {c.url}",
        f"- technical_axis_labels: {', '.join(c.technical_axis_labels)}",
        f"- why_read: {c.why_read}",
        f"- score_breakdown: {json.dumps(c.score_breakdown, ensure_ascii=False)}",
        f"- expected_evidence_to_check: {c.expected_evidence_to_check}",
        f"- next_verification_action: {c.next_verification_action}",
        f"- caution_flags: {', '.join(c.caution_flags)}",
        "",
      ],
    )
  lines.extend(["## Next phases", *[f"- {p}" for p in NEXT_PHASE_CONNECTIONS]])
  if shortlist.warnings:
    lines.extend(["", "## Warnings", *[f"- {w}" for w in shortlist.warnings]])
  text = "\n".join(lines)
  _assert_no_secrets(text)
  return text


def write_excel_shortlist(shortlist: V8PatentShortlist, path: Path) -> str:
  try:
    import pandas as pd

    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
      rows = [c.to_dict() for c in shortlist.patent_candidates]
      for row in rows:
        row["technical_axis_labels"] = "; ".join(row.get("technical_axis_labels") or [])
        row["caution_flags"] = "; ".join(row.get("caution_flags") or [])
        row["score_breakdown"] = json.dumps(row.get("score_breakdown") or {}, ensure_ascii=False)
      pd.DataFrame(rows).to_excel(writer, sheet_name="Patent Shortlist", index=False)
      breakdown_rows = []
      for c in shortlist.patent_candidates:
        for key, val in c.score_breakdown.items():
          breakdown_rows.append({"rank": c.rank, "publication_number": c.publication_number, "metric": key, "value": val})
      pd.DataFrame(breakdown_rows).to_excel(writer, sheet_name="Score Breakdown", index=False)
      pd.DataFrame({"warning": shortlist.warnings or ["(none)"]}).to_excel(writer, sheet_name="Warnings", index=False)
    return ""
  except Exception as exc:
    return f"Excel export skipped: {exc}"


def export_patent_shortlist(
  shortlist: V8PatentShortlist,
  *,
  project_root: Path | str | None = None,
) -> V8PatentShortlistExport:
  root = Path(project_root) if project_root else Path.cwd()
  slug = shortlist.generated_at.replace(":", "").replace("-", "").replace("+00:00", "Z")
  output_dir = get_v8_patent_shortlists_dir(root) / f"{shortlist.case_id}_{slug}"
  output_dir.mkdir(parents=True, exist_ok=True)

  csv_path = output_dir / "patent_shortlist.csv"
  md_path = output_dir / "patent_shortlist.md"
  xlsx_path = output_dir / "patent_shortlist.xlsx"
  manifest_path = output_dir / "patent_shortlist_manifest.json"

  csv_path.write_text(shortlist_to_csv_text(shortlist.patent_candidates), encoding="utf-8")
  md_path.write_text(shortlist_to_markdown(shortlist), encoding="utf-8")
  excel_warning = write_excel_shortlist(shortlist, xlsx_path)

  manifest: dict[str, Any] = {
    "case_id": shortlist.case_id,
    "case_name": shortlist.case_name,
    "generated_at": shortlist.generated_at,
    "top_n": shortlist.top_n,
    "count": shortlist.count,
    "warnings": shortlist.warnings,
    "safety_notices": list(SHORTLIST_SAFETY_NOTICES),
    "next_phase_connections": list(NEXT_PHASE_CONNECTIONS),
    "files": {
      "patent_shortlist_csv": str(csv_path),
      "patent_shortlist_md": str(md_path),
      "patent_shortlist_xlsx": str(xlsx_path),
    },
    "excel_warning": excel_warning,
  }
  manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2)
  _assert_no_secrets(manifest_text)
  manifest_path.write_text(manifest_text, encoding="utf-8")

  return V8PatentShortlistExport(
    case_id=shortlist.case_id,
    case_name=shortlist.case_name,
    generated_at=shortlist.generated_at,
    top_n=shortlist.top_n,
    output_dir=str(output_dir),
    csv_path=str(csv_path),
    md_path=str(md_path),
    xlsx_path=str(xlsx_path),
    manifest_path=str(manifest_path),
    excel_warning=excel_warning,
  )
