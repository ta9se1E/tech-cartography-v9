"""v8 unified Sources repository (Phase 27C)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from tech_cartography.runtime.v8_sources_schema import V8SourceRecord, V8SourcesTable, utc_now_iso
from tech_cartography.services.v8_sources_loader import dedupe_key, load_source_records
from tech_cartography.services.v8_sources_table import load_case_profile, project_root_from_here


def deduplicate_records(records: list[V8SourceRecord]) -> tuple[list[V8SourceRecord], int]:
  seen: dict[str, V8SourceRecord] = {}
  duplicate_count = 0
  for record in records:
    key = dedupe_key(record)
    if key in seen:
      duplicate_count += 1
      continue
    seen[key] = record
  return list(seen.values()), duplicate_count


def load_sources_table(
  case_id: str | None = None,
  *,
  project_root: Path | str | None = None,
  dedupe: bool = True,
) -> V8SourcesTable:
  root = Path(project_root) if project_root else project_root_from_here()
  raw_records, warnings = load_source_records(case_id, project_root=root)
  excluded = 0
  records = raw_records
  if dedupe:
    records, excluded = deduplicate_records(raw_records)

  count_by_case = dict(Counter(record.case_id for record in records))
  count_by_type = dict(Counter(record.source_type for record in records))
  count_by_role = dict(Counter(record.evidence_role for record in records))

  return V8SourcesTable(
    records=records,
    source_count=len(records),
    count_by_case=count_by_case,
    count_by_type=count_by_type,
    count_by_evidence_role=count_by_role,
    warnings=warnings,
    excluded_or_duplicate_count=excluded,
    loaded_at=utc_now_iso(),
  )


def filter_sources_table(
  table: V8SourcesTable,
  *,
  case_id: str | None = None,
  source_type: str | None = None,
  evidence_role: str | None = None,
  verification_status: str | None = None,
  candidate_only: bool | None = None,
  search_text: str = "",
) -> V8SourcesTable:
  records = table.records
  if case_id and case_id != "all":
    records = [r for r in records if r.case_id == case_id]
  if source_type and source_type != "all":
    records = [r for r in records if r.source_type == source_type]
  if evidence_role and evidence_role != "all":
    records = [r for r in records if r.evidence_role == evidence_role]
  if verification_status and verification_status != "all":
    records = [r for r in records if r.verification_status == verification_status]
  if candidate_only is True:
    records = [r for r in records if r.candidate_information_only]
  elif candidate_only is False:
    records = [r for r in records if not r.candidate_information_only]

  query = search_text.strip().lower()
  if query:
    def _match(record: V8SourceRecord) -> bool:
      blob = " ".join(
        [
          record.title,
          record.organization,
          record.publication_number,
          record.notes,
          record.url,
        ],
      ).lower()
      return query in blob

    records = [r for r in records if _match(r)]

  count_by_case = dict(Counter(record.case_id for record in records))
  count_by_type = dict(Counter(record.source_type for record in records))
  count_by_role = dict(Counter(record.evidence_role for record in records))
  return V8SourcesTable(
    records=records,
    source_count=len(records),
    count_by_case=count_by_case,
    count_by_type=count_by_type,
    count_by_evidence_role=count_by_role,
    warnings=list(table.warnings),
    excluded_or_duplicate_count=table.excluded_or_duplicate_count,
    loaded_at=table.loaded_at,
  )


def resolve_case_name(case_id: str, project_root: Path | str | None = None) -> str:
  if case_id in {"", "all"}:
    return "All cases"
  profile = load_case_profile(case_id, project_root)
  if profile:
    return str(profile.get("case_name") or case_id)
  return case_id
