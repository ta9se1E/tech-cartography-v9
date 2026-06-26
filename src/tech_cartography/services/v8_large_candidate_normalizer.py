"""v8 Large Candidate normalizer / dedupe (Phase 27J.0)."""

from __future__ import annotations

import csv
import difflib
from pathlib import Path

from tech_cartography.runtime.v8_large_candidate_schema import (
  LARGE_CANDIDATE_SAFETY_NOTICES,
  V8LargeCandidateQualityIssue,
  V8LargeCandidateRecord,
)
from tech_cartography.runtime.v8_sources_schema import utc_now_iso
from tech_cartography.services.v8_large_candidate_import import (
  build_population_profile,
  large_candidates_paths,
  load_large_candidates_csv,
  records_to_csv,
)
from tech_cartography.services.v8_sources_table import project_root_from_here

TITLE_SIMILARITY_THRESHOLD = 0.92


def _collect_quality_issues(records: list[V8LargeCandidateRecord]) -> list[V8LargeCandidateQualityIssue]:
  issues: list[V8LargeCandidateQualityIssue] = []
  for rec in records:
    if not rec.title:
      issues.append(V8LargeCandidateQualityIssue(
        issue_id=f"{rec.case_id}:qi:title:{rec.candidate_id}",
        case_id=rec.case_id,
        candidate_id=rec.candidate_id,
        issue_type="missing_title",
        severity="warning",
        message="title missing",
        publication_number=rec.publication_number,
        raw_row_number=rec.raw_row_number,
      ))
    if not rec.publication_number:
      issues.append(V8LargeCandidateQualityIssue(
        issue_id=f"{rec.case_id}:qi:pub:{rec.candidate_id}",
        case_id=rec.case_id,
        candidate_id=rec.candidate_id,
        issue_type="missing_publication_number",
        severity="warning",
        message="publication_number missing",
        publication_number="",
        raw_row_number=rec.raw_row_number,
      ))
    if not rec.year:
      issues.append(V8LargeCandidateQualityIssue(
        issue_id=f"{rec.case_id}:qi:year:{rec.candidate_id}",
        case_id=rec.case_id,
        candidate_id=rec.candidate_id,
        issue_type="missing_year",
        severity="info",
        message="year missing",
        publication_number=rec.publication_number,
        raw_row_number=rec.raw_row_number,
      ))
    if not rec.organization and not rec.assignee:
      issues.append(V8LargeCandidateQualityIssue(
        issue_id=f"{rec.case_id}:qi:org:{rec.candidate_id}",
        case_id=rec.case_id,
        candidate_id=rec.candidate_id,
        issue_type="missing_organization",
        severity="info",
        message="organization/assignee missing",
        publication_number=rec.publication_number,
        raw_row_number=rec.raw_row_number,
      ))
  return issues


def dedupe_large_candidates(
  records: list[V8LargeCandidateRecord],
) -> tuple[list[V8LargeCandidateRecord], list[V8LargeCandidateRecord]]:
  """Dedupe by publication_number, family_id, weak title similarity. Heuristic only."""
  working = [V8LargeCandidateRecord.from_dict(r.to_dict()) for r in records]
  for rec in working:
    rec.stage_label = "deduped"
    rec.is_duplicate = False
    rec.duplicate_of = ""

  kept: list[V8LargeCandidateRecord] = []
  duplicates: list[V8LargeCandidateRecord] = []

  by_pub: dict[str, V8LargeCandidateRecord] = {}
  by_family: dict[str, V8LargeCandidateRecord] = {}
  by_title: list[V8LargeCandidateRecord] = []

  for rec in working:
    dup_of = ""
    if rec.publication_number and rec.publication_number in by_pub:
      dup_of = by_pub[rec.publication_number].candidate_id
    elif rec.family_id and rec.family_id in by_family:
      dup_of = by_family[rec.family_id].candidate_id
    elif rec.normalized_title:
      for prior in by_title:
        ratio = difflib.SequenceMatcher(None, rec.normalized_title, prior.normalized_title).ratio()
        if ratio >= TITLE_SIMILARITY_THRESHOLD:
          dup_of = prior.candidate_id
          break

    if dup_of:
      rec.is_duplicate = True
      rec.duplicate_of = dup_of
      rec.stage_label = "excluded"
      rec.exclusion_reason = "duplicate_heuristic"
      duplicates.append(rec)
      continue

    kept.append(rec)
    if rec.publication_number:
      by_pub[rec.publication_number] = rec
    if rec.family_id:
      by_family[rec.family_id] = rec
    if rec.normalized_title:
      by_title.append(rec)

  return kept, duplicates


def normalize_and_dedupe_large_candidates(
  case_id: str,
  *,
  project_root: Path | str | None = None,
) -> tuple[list[V8LargeCandidateRecord], list[V8LargeCandidateQualityIssue]]:
  root = Path(project_root or project_root_from_here())
  paths = large_candidates_paths(case_id, root)
  population = load_large_candidates_csv(paths["population"])
  if not population:
    return [], []

  issues = _collect_quality_issues(population)
  deduped, dups = dedupe_large_candidates(population)

  records_to_csv(deduped, paths["deduped"])

  issue_rows = issues + [
    V8LargeCandidateQualityIssue(
      issue_id=f"{case_id}:dup:{d.candidate_id}",
      case_id=case_id,
      candidate_id=d.candidate_id,
      issue_type="duplicate",
      severity="info",
      message=f"duplicate_of={d.duplicate_of}",
      publication_number=d.publication_number,
      raw_row_number=d.raw_row_number,
    )
    for d in dups
  ]
  paths["quality_issues"].parent.mkdir(parents=True, exist_ok=True)
  with paths["quality_issues"].open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=[
      "issue_id", "case_id", "candidate_id", "issue_type", "severity",
      "message", "publication_number", "raw_row_number",
    ])
    writer.writeheader()
    for issue in issue_rows:
      writer.writerow(issue.to_dict())

  profile = build_population_profile(case_id, deduped)
  profile.duplicate_count = len(dups)
  paths["profile"].write_text(
    __import__("json").dumps(profile.to_dict(), ensure_ascii=False, indent=2),
    encoding="utf-8",
  )

  report = "\n".join([
    f"# Large Candidate Dedupe Report — {case_id}",
    "",
    f"- generated_at: {utc_now_iso()}",
    f"- population: {len(population)}",
    f"- deduped: {len(deduped)}",
    f"- duplicates: {len(dups)}",
    "",
    "重複除去は暫定 heuristic です。human_review_required を維持してください。",
    "",
    "## Safety",
    *[f"- {n}" for n in LARGE_CANDIDATE_SAFETY_NOTICES[:4]],
  ])
  paths["dedupe_report"].write_text(report, encoding="utf-8")

  return deduped, issue_rows
