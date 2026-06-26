"""v8 Large Candidate import service (Phase 27J.0)."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from tech_cartography.runtime.v8_large_candidate_schema import (
  LARGE_CANDIDATE_SAFETY_NOTICES,
  V8LargeCandidateImportResult,
  V8LargeCandidatePopulationProfile,
  V8LargeCandidateQualityIssue,
  V8LargeCandidateRecord,
)
from tech_cartography.runtime.v8_sources_schema import utc_now_iso
from tech_cartography.services.v8_sources_table import project_root_from_here

MAX_ROWS_DEFAULT = 1000
MAX_ROWS_LIMIT = 1000

COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
  "publication_number": ("publication_number", "publication", "patent_id", "publication_id", "pub_number"),
  "title": ("title", "invention_title", "patent_title"),
  "abstract": ("abstract", "abstract_text"),
  "assignee": ("assignee", "applicant"),
  "organization": ("organization", "assignee", "applicant", "company"),
  "inventors": ("inventors", "inventor"),
  "publication_date": ("publication_date", "pub_date", "date"),
  "year": ("year", "publication_year"),
  "country_code": ("country_code", "country"),
  "kind_code": ("kind_code", "kind"),
  "family_id": ("family_id", "patent_family_id"),
  "url": ("url", "source_url", "google_patents_url", "patent_url"),
  "source_type": ("source_type", "type"),
  "notes": ("notes", "comment"),
}

OUTPUT_COLUMNS: tuple[str, ...] = tuple(V8LargeCandidateRecord.__dataclass_fields__.keys())  # type: ignore[attr-defined]

FAKE_URL_RE = re.compile(
  r"10\.(0000|1234)/|example\.com|fake-doi|placeholder",
  re.IGNORECASE,
)


def _import_id(case_id: str, path: str) -> str:
  digest = hashlib.sha256(f"{case_id}|{path}|import".encode()).hexdigest()[:12]
  return f"{case_id}:large_import:{digest}"


def _profile_id(case_id: str) -> str:
  digest = hashlib.sha256(f"{case_id}|profile".encode()).hexdigest()[:12]
  return f"{case_id}:large_profile:{digest}"


def _candidate_id(case_id: str, row_no: int, pub: str) -> str:
  digest = hashlib.sha256(f"{case_id}|{row_no}|{pub}".encode()).hexdigest()[:10]
  return f"{case_id}:lc:{digest}"


def normalize_publication_number(raw: str) -> str:
  value = re.sub(r"[\s\-/]", "", str(raw or "").strip().upper())
  return value


def normalize_title(raw: str) -> str:
  return " ".join(str(raw or "").lower().split())


def build_dedupe_key(pub: str, family_id: str, title: str) -> str:
  if pub:
    return f"pub:{pub}"
  if family_id:
    return f"family:{family_id.strip().lower()}"
  if title:
    digest = hashlib.sha256(normalize_title(title).encode()).hexdigest()[:12]
    return f"title:{digest}"
  return "empty"


def _map_row(raw: dict[str, Any], fieldnames: list[str]) -> dict[str, str]:
  lowered = {str(k).strip().lower(): str(v or "").strip() for k, v in raw.items() if k}
  mapped: dict[str, str] = {}
  for target, aliases in COLUMN_ALIASES.items():
    for alias in aliases:
      if alias.lower() in lowered and lowered[alias.lower()]:
        mapped[target] = lowered[alias.lower()]
        break
  return mapped


def _read_input_rows(input_path: Path) -> tuple[list[dict[str, str]], list[str]]:
  warnings: list[str] = []
  suffix = input_path.suffix.lower()
  if suffix == ".csv":
    with input_path.open(encoding="utf-8-sig", newline="") as handle:
      reader = csv.DictReader(handle)
      fieldnames = list(reader.fieldnames or [])
      rows = [dict(row) for row in reader]
    return rows, warnings
  if suffix in {".xlsx", ".xls"}:
    try:
      import pandas as pd

      df = pd.read_excel(input_path)
      rows = df.fillna("").astype(str).to_dict(orient="records")
      return rows, warnings
    except Exception as exc:
      warnings.append(f"Excel read failed: {exc}")
      return [], warnings
  warnings.append(f"unsupported file type: {suffix}")
  return [], warnings


def _extract_year(mapped: dict[str, str]) -> str:
  year = str(mapped.get("year") or "").strip()
  if year.isdigit():
    return year
  pub_date = str(mapped.get("publication_date") or "")
  match = re.search(r"(19|20)\d{2}", pub_date)
  return match.group(0) if match else ""


def _row_to_record(
  *,
  case_id: str,
  mapped: dict[str, str],
  row_no: int,
  source_file: str,
  default_source_type: str,
) -> tuple[V8LargeCandidateRecord | None, str]:
  pub = normalize_publication_number(mapped.get("publication_number", ""))
  title = str(mapped.get("title") or "").strip()
  url = str(mapped.get("url") or "").strip()
  if FAKE_URL_RE.search(url):
    return None, "fake-like URL rejected"
  if not pub and not title:
    return None, "missing publication_number and title"

  source_type = str(mapped.get("source_type") or default_source_type or "patent").lower()
  if source_type not in {"patent", "paper", "web", "company"}:
    source_type = "patent" if pub else "unknown"

  family_id = str(mapped.get("family_id") or "").strip()
  norm_title = normalize_title(title)
  year = _extract_year(mapped)
  assignee = str(mapped.get("assignee") or mapped.get("organization") or "").strip()
  org = str(mapped.get("organization") or assignee).strip()

  record = V8LargeCandidateRecord(
    candidate_id=_candidate_id(case_id, row_no, pub or title[:20]),
    case_id=case_id,
    source_type=source_type,
    publication_number=pub,
    family_id=family_id,
    title=title,
    abstract=str(mapped.get("abstract") or "").strip(),
    organization=org,
    assignee=assignee,
    inventors=str(mapped.get("inventors") or "").strip(),
    country_code=str(mapped.get("country_code") or "").strip(),
    kind_code=str(mapped.get("kind_code") or "").strip(),
    publication_date=str(mapped.get("publication_date") or "").strip(),
    year=year,
    url=url,
    source_url=url,
    raw_source_file=source_file,
    raw_row_number=row_no,
    normalized_title=norm_title,
    normalized_publication_number=pub,
    dedupe_key=build_dedupe_key(pub, family_id, title),
    stage_label="population",
  )
  return record, ""


def build_population_profile(
  case_id: str,
  records: list[V8LargeCandidateRecord],
) -> V8LargeCandidatePopulationProfile:
  from collections import Counter

  years = [int(r.year) for r in records if r.year.isdigit()]
  pubs = {r.publication_number for r in records if r.publication_number}
  by_type = Counter(r.source_type for r in records)
  by_year = Counter(r.year for r in records if r.year)
  by_org = Counter(r.organization for r in records if r.organization)
  by_country = Counter(r.country_code for r in records if r.country_code)
  by_stage = Counter(r.stage_label for r in records)

  return V8LargeCandidatePopulationProfile(
    profile_id=_profile_id(case_id),
    case_id=case_id,
    generated_at=utc_now_iso(),
    total_candidates=len(records),
    patent_count=by_type.get("patent", 0),
    paper_count=by_type.get("paper", 0),
    web_count=by_type.get("web", 0),
    company_count=by_type.get("company", 0),
    unknown_count=by_type.get("unknown", 0),
    unique_publication_count=len(pubs),
    duplicate_count=sum(1 for r in records if r.is_duplicate),
    missing_title_count=sum(1 for r in records if not r.title),
    missing_publication_number_count=sum(1 for r in records if not r.publication_number),
    missing_url_count=sum(1 for r in records if not r.url),
    year_min=str(min(years)) if years else "",
    year_max=str(max(years)) if years else "",
    count_by_year=dict(by_year),
    count_by_organization=dict(by_org.most_common(20)),
    count_by_country=dict(by_country),
    count_by_source_type=dict(by_type),
    count_by_stage_label=dict(by_stage),
    warnings=list(LARGE_CANDIDATE_SAFETY_NOTICES[:3]),
  )


def records_to_csv(records: list[V8LargeCandidateRecord], path: Path) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  with path.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(OUTPUT_COLUMNS))
    writer.writeheader()
    for rec in records:
      row = rec.to_dict()
      row["matched_keywords"] = "|".join(rec.matched_keywords)
      writer.writerow(row)


def load_large_candidates_csv(path: Path) -> list[V8LargeCandidateRecord]:
  if not path.exists():
    return []
  records: list[V8LargeCandidateRecord] = []
  with path.open(encoding="utf-8-sig", newline="") as handle:
    reader = csv.DictReader(handle)
    for raw in reader:
      kw = str(raw.get("matched_keywords") or "")
      raw["matched_keywords"] = [k for k in kw.split("|") if k] if kw else []
      for bool_key in ("candidate_information_only", "human_review_required", "is_duplicate"):
        if bool_key in raw:
          raw[bool_key] = str(raw.get(bool_key, "")).lower() in {"true", "1", "yes"}
      if "heuristic_score" in raw:
        try:
          raw["heuristic_score"] = float(raw.get("heuristic_score") or 0)
        except ValueError:
          raw["heuristic_score"] = 0.0
      if "keyword_match_count" in raw:
        try:
          raw["keyword_match_count"] = int(raw.get("keyword_match_count") or 0)
        except ValueError:
          raw["keyword_match_count"] = 0
      records.append(V8LargeCandidateRecord.from_dict(raw))
  return records


def large_candidates_paths(case_id: str, project_root: Path | str | None = None) -> dict[str, Path]:
  root = Path(project_root or project_root_from_here())
  case_dir = root / "cases" / case_id
  return {
    "population": case_dir / "source_candidates_large.csv",
    "profile": case_dir / "source_candidates_large_profile.json",
    "quality_report": case_dir / "source_candidates_large_quality_report.md",
    "deduped": case_dir / "source_candidates_large_deduped.csv",
    "quality_issues": case_dir / "source_candidates_large_quality_issues.csv",
    "dedupe_report": case_dir / "source_candidates_large_dedupe_report.md",
  }


def import_large_candidates(
  *,
  case_id: str,
  input_path: Path | str,
  max_rows: int = MAX_ROWS_DEFAULT,
  default_source_type: str = "patent",
  project_root: Path | str | None = None,
) -> V8LargeCandidateImportResult:
  """Import CSV/Excel candidates. No external API calls."""
  root = Path(project_root or project_root_from_here())
  src = Path(input_path)
  max_rows = min(max(max_rows, 1), MAX_ROWS_LIMIT)

  raw_rows, read_warnings = _read_input_rows(src)
  warnings = list(read_warnings)
  quality_issues: list[dict[str, Any]] = []
  accepted: list[V8LargeCandidateRecord] = []
  rejected = 0

  for idx, raw in enumerate(raw_rows[:max_rows], start=2):
    mapped = _map_row(raw, list(raw.keys()))
    record, reason = _row_to_record(
      case_id=case_id,
      mapped=mapped,
      row_no=idx,
      source_file=str(src),
      default_source_type=default_source_type,
    )
    if record is None:
      rejected += 1
      quality_issues.append(
        V8LargeCandidateQualityIssue(
          issue_id=f"{case_id}:qi:{idx}",
          case_id=case_id,
          candidate_id="",
          issue_type="rejected_row",
          severity="warning",
          message=reason,
          raw_row_number=idx,
        ).to_dict(),
      )
      continue
    accepted.append(record)

  if len(raw_rows) > max_rows:
    warnings.append(f"input truncated to max_rows={max_rows} (input had {len(raw_rows)} rows)")

  paths = large_candidates_paths(case_id, root)
  records_to_csv(accepted, paths["population"])
  profile = build_population_profile(case_id, accepted)
  paths["profile"].write_text(json.dumps(profile.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

  report_lines = [
    f"# Large Candidate Quality Report — {case_id}",
    "",
    f"- imported_at: {utc_now_iso()}",
    f"- input_path: {src}",
    f"- accepted: {len(accepted)}",
    f"- rejected: {rejected}",
    "",
    "## Safety",
    *[f"- {n}" for n in LARGE_CANDIDATE_SAFETY_NOTICES],
  ]
  paths["quality_report"].write_text("\n".join(report_lines), encoding="utf-8")

  return V8LargeCandidateImportResult(
    import_id=_import_id(case_id, str(src)),
    case_id=case_id,
    input_path=str(src),
    imported_at=utc_now_iso(),
    input_row_count=len(raw_rows),
    accepted_row_count=len(accepted),
    rejected_row_count=rejected,
    max_rows_applied=max_rows,
    output_candidates_path=str(paths["population"]),
    output_profile_path=str(paths["profile"]),
    warnings=warnings,
    quality_issues=quality_issues,
    no_external_api=True,
    no_bigquery_execution=True,
    no_email_send=True,
    no_scheduler_start=True,
  )
