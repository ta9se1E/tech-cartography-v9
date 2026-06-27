"""Deep Dive shortlist — Large Candidate Top5 preferred over legacy patent shortlist (Phase27O.2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tech_cartography.runtime.v8_patent_shortlist_schema import (
  SHORTLIST_SAFETY_NOTICES,
  V8PatentCandidate,
  V8PatentShortlist,
)
from tech_cartography.runtime.v8_sources_schema import utc_now_iso
from tech_cartography.services.v8_large_candidate_import import load_large_candidates_csv
from tech_cartography.services.v8_large_candidate_shortlist import (
  find_latest_large_shortlist_dir,
  get_large_shortlist_dir,
  load_top5_publications,
)
from tech_cartography.services.v8_patent_shortlist import build_patent_shortlist
from tech_cartography.services.v8_sources_repository import load_sources_table, resolve_case_name
from tech_cartography.services.v8_sources_table import project_root_from_here

DEEP_DIVE_TOP_N = 5


def _top5_csv_path(case_id: str, project_root: Path) -> Path | None:
  latest = find_latest_large_shortlist_dir(case_id, project_root)
  if latest:
    candidate = latest / "large_candidate_top5.csv"
    if candidate.exists():
      return candidate
  flat = get_large_shortlist_dir(case_id, project_root) / "large_candidate_top5.csv"
  if flat.exists():
    return flat
  return None


def load_top5_candidate_records(
  case_id: str,
  project_root: Path | str | None = None,
) -> dict[str, dict[str, str]]:
  """Return publication_number -> {title, url, organization, year} from Top5 CSV."""
  root = Path(project_root or project_root_from_here())
  path = _top5_csv_path(case_id, root)
  if not path:
    return {}
  records = load_large_candidates_csv(path)
  by_pub: dict[str, dict[str, str]] = {}
  for rec in records:
    if not rec.publication_number:
      continue
    by_pub[rec.publication_number] = {
      "title": rec.title or "",
      "url": rec.url or "",
      "organization": rec.organization or rec.assignee or "",
      "year": str(rec.year or ""),
    }
  return by_pub


def _lookup_source_metadata(
  case_id: str,
  publication_number: str,
  project_root: Path,
) -> dict[str, str]:
  table = load_sources_table(case_id, project_root=project_root)
  for rec in table.records:
    if rec.publication_number == publication_number:
      return {
        "title": rec.title or "",
        "url": rec.url or "",
        "organization": rec.organization or "",
        "year": str(rec.year or ""),
      }
  return {"title": "", "url": "", "organization": "", "year": ""}


def _candidate_from_publication(
  *,
  case_id: str,
  publication_number: str,
  rank: int,
  meta: dict[str, str],
  shortlist_source: str,
) -> V8PatentCandidate:
  title = meta.get("title") or publication_number
  url = meta.get("url") or ""
  caution = [
    "heuristic_draft_selection",
    "reading_priority_not_patent_value",
    "claim_text_not_loaded",
    "no_legal_judgement",
    shortlist_source,
  ]
  return V8PatentCandidate(
    candidate_id=f"{case_id}:deep_dive:{publication_number}",
    case_id=case_id,
    rank=rank,
    publication_number=publication_number,
    title=title,
    assignee_or_organization=meta.get("organization") or "",
    year=meta.get("year") or "",
    url=url,
    why_read=f"Large Candidate Top5 Deep Dive — {publication_number}",
    next_verification_action=f"Claim Map / Evidence Map で {publication_number} を確認",
    caution_flags=caution,
    human_review_required=True,
  )


def resolve_deep_dive_shortlist(
  case_id: str,
  project_root: Path | str | None = None,
) -> V8PatentShortlist:
  """Prefer Large Candidate Top5; fall back to legacy patent shortlist from Sources."""
  root = Path(project_root or project_root_from_here())
  case_name = resolve_case_name(case_id, root)
  top5_pubs = load_top5_publications(case_id, root)
  if top5_pubs:
    meta_by_pub = load_top5_candidate_records(case_id, root)
    candidates: list[V8PatentCandidate] = []
    for rank, pub in enumerate(top5_pubs[:DEEP_DIVE_TOP_N], start=1):
      meta = meta_by_pub.get(pub) or _lookup_source_metadata(case_id, pub, root)
      candidates.append(
        _candidate_from_publication(
          case_id=case_id,
          publication_number=pub,
          rank=rank,
          meta=meta,
          shortlist_source="large_candidate_top5",
        ),
      )
    return V8PatentShortlist(
      case_id=case_id,
      case_name=case_name,
      top_n=DEEP_DIVE_TOP_N,
      count=len(candidates),
      patent_candidates=candidates,
      excluded_sources=[],
      warnings=[
        SHORTLIST_SAFETY_NOTICES[0],
        "Large Candidate Top5 を Deep Dive 対象として使用 — legacy US shortlist は使用しません。",
      ],
      generated_at=utc_now_iso(),
    )

  legacy = build_patent_shortlist(case_id=case_id, top_n=DEEP_DIVE_TOP_N, project_root=root)
  legacy.warnings.append(
    "legacy_patent_shortlist_fallback — Large Candidate Top5 未生成のため Sources 由来 shortlist を使用。"
  )
  for candidate in legacy.patent_candidates:
    if "legacy_patent_shortlist_fallback" not in candidate.caution_flags:
      candidate.caution_flags.append("legacy_patent_shortlist_fallback")
  return legacy


def list_deep_dive_publications(
  case_id: str,
  project_root: Path | str | None = None,
) -> tuple[list[str], str]:
  """Return (publication_numbers, source_label). source_label is large_candidate_top5 or legacy."""
  root = Path(project_root or project_root_from_here())
  top5 = load_top5_publications(case_id, root)
  if top5:
    return top5[:DEEP_DIVE_TOP_N], "large_candidate_top5"
  shortlist = build_patent_shortlist(case_id=case_id, top_n=DEEP_DIVE_TOP_N, project_root=root)
  return [p.publication_number for p in shortlist.patent_candidates], "legacy"


def patent_candidate_for_publication(
  *,
  case_id: str,
  publication_number: str,
  project_root: Path | str | None = None,
  patent_title: str = "",
  claim_source_url: str = "",
) -> V8PatentCandidate:
  """Build a minimal deep-dive candidate when pub is selected but absent from shortlist pack."""
  root = Path(project_root or project_root_from_here())
  meta = load_top5_candidate_records(case_id, root).get(publication_number) or _lookup_source_metadata(
    case_id,
    publication_number,
    root,
  )
  if patent_title:
    meta = {**meta, "title": patent_title}
  if claim_source_url:
    meta = {**meta, "url": claim_source_url}
  pubs, source = list_deep_dive_publications(case_id, root)
  rank = pubs.index(publication_number) + 1 if publication_number in pubs else 0
  return _candidate_from_publication(
    case_id=case_id,
    publication_number=publication_number,
    rank=rank or 1,
    meta=meta,
    shortlist_source=source if publication_number in pubs else "manual_claim_selection",
  )
