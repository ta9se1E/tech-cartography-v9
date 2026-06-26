"""v8 Patent Triage adapter for Large Candidate records (Phase 27J.1)."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tech_cartography.runtime.v8_large_candidate_schema import CASE_KEYWORDS, V8LargeCandidateRecord

PATENT_TRIAGE_POLICY = "patent_triage_adapter — Phase4 scoring via patent_triage.py"
FALLBACK_POLICY = "fallback_large_candidate_heuristic — Phase27J.0 keyword heuristic"
FALLBACK_WARNING = "patent_triage.py not found; fallback heuristic used"


def _search_blob(rec: V8LargeCandidateRecord) -> str:
  return " ".join([
    rec.title, rec.abstract, rec.organization, rec.assignee, rec.publication_number,
  ]).lower()


def _fallback_score_candidate(
  rec: V8LargeCandidateRecord,
  *,
  case_id: str,
  include_keywords: tuple[str, ...] = (),
  exclude_keywords: tuple[str, ...] = (),
) -> V8LargeCandidateRecord:
  keywords = list(CASE_KEYWORDS.get(case_id, ())) + list(include_keywords)
  blob = _search_blob(rec)
  matched = [kw for kw in keywords if kw.lower() in blob]
  excluded = [kw for kw in exclude_keywords if kw.lower() in blob]
  score = len(matched) * 0.12
  reasons: list[str] = []
  if matched:
    reasons.append(f"keyword_hits={len(matched)}")
  if rec.publication_number:
    score += 0.15
    reasons.append("has_publication_number")
  if rec.year:
    score += 0.08
    reasons.append("has_year")
  if rec.title:
    score += 0.05
    reasons.append("title present")
  else:
    score -= 0.2
    reasons.append("missing_title_penalty")
  if not rec.publication_number:
    score -= 0.15
    reasons.append("missing_pub_penalty")
  if rec.source_type == "patent":
    score += 0.1
    reasons.append("patent_priority")
  if excluded:
    score -= 0.25 * len(excluded)
    reasons.append(f"excluded_hits={len(excluded)}")
  score = max(0.0, min(1.0, score))
  copy = V8LargeCandidateRecord.from_dict(rec.to_dict())
  copy.heuristic_score = round(score, 4)
  copy.score_reason = "; ".join(reasons) or "baseline_heuristic"
  copy.matched_keywords = matched
  copy.keyword_match_count = len(matched)
  copy.positive_reasons = [p for p in copy.score_reason.split("; ") if "penalty" not in p and "excluded" not in p]
  copy.negative_reasons = [p for p in copy.score_reason.split("; ") if "penalty" in p or "excluded" in p]
  copy.ranking_policy = FALLBACK_POLICY
  return copy


@dataclass
class V8PatentTriageAdapterResult:
  case_id: str
  triage_engine: str
  ranking_policy: str
  warnings: list[str] = field(default_factory=list)
  scored_records: list[V8LargeCandidateRecord] = field(default_factory=list)
  triage_results: list[Any] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return {
      "case_id": self.case_id,
      "triage_engine": self.triage_engine,
      "ranking_policy": self.ranking_policy,
      "warnings": self.warnings,
      "scored_count": len(self.scored_records),
    }


def patent_triage_available() -> bool:
  spec = importlib.util.find_spec("tech_cartography.services.patent_triage")
  return spec is not None


def _load_case_profile_terms(case_id: str, project_root: Path | None) -> tuple[list[str], list[str], list[str]]:
  include = list(CASE_KEYWORDS.get(case_id, ()))
  exclude: list[str] = []
  companies: list[str] = []
  if project_root:
    profile_path = project_root / "cases" / case_id / "case_profile.yaml"
    if profile_path.exists():
      try:
        import yaml

        data = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
        seed = data.get("seed_keywords") or data.get("keywords") or []
        if isinstance(seed, list):
          include.extend(str(s) for s in seed if s)
        ex = data.get("exclusion_keywords") or []
        if isinstance(ex, list):
          exclude.extend(str(s) for s in ex if s)
        comps = data.get("target_companies") or data.get("watch_companies") or []
        if isinstance(comps, list):
          companies.extend(str(c) for c in comps if c)
      except Exception:
        pass
  # dedupe preserve order
  seen: set[str] = set()
  include_deduped: list[str] = []
  for t in include:
    tl = t.lower()
    if tl not in seen:
      seen.add(tl)
      include_deduped.append(t)
  return include_deduped, exclude, companies


def large_candidate_to_triage_dict(rec: V8LargeCandidateRecord) -> dict[str, Any]:
  return {
    "candidate_id": rec.candidate_id,
    "publication_number": rec.publication_number,
    "title": rec.title,
    "abstract": rec.abstract,
    "assignee": rec.assignee,
    "organization": rec.organization,
    "country_code": rec.country_code,
    "year": rec.year,
    "publication_date": rec.publication_date,
    "source_type": rec.source_type,
  }


def _apply_triage_result(
  rec: V8LargeCandidateRecord,
  triage_result: Any,
  *,
  ranking_policy: str,
) -> V8LargeCandidateRecord:
  copy = V8LargeCandidateRecord.from_dict(rec.to_dict())
  copy.heuristic_score = float(getattr(triage_result, "total_score", 0.0))
  copy.matched_keywords = list(getattr(triage_result, "matched_include_terms", []) or [])
  copy.keyword_match_count = len(copy.matched_keywords)
  copy.positive_reasons = list(getattr(triage_result, "positive_reasons", []) or [])
  copy.negative_reasons = list(getattr(triage_result, "negative_reasons", []) or [])
  copy.ranking_policy = ranking_policy
  parts = copy.positive_reasons[:3] + [f"-{n}" for n in copy.negative_reasons[:2]]
  copy.score_reason = "; ".join(parts) if parts else "patent_triage baseline"
  return copy


def _apply_fallback(
  rec: V8LargeCandidateRecord,
  *,
  case_id: str,
  include_keywords: tuple[str, ...],
  exclude_keywords: tuple[str, ...],
) -> V8LargeCandidateRecord:
  return _fallback_score_candidate(
    rec, case_id=case_id, include_keywords=include_keywords, exclude_keywords=exclude_keywords,
  )


def score_large_candidates_with_triage(
  records: list[V8LargeCandidateRecord],
  *,
  case_id: str,
  include_keywords: tuple[str, ...] = (),
  exclude_keywords: tuple[str, ...] = (),
  project_root: Path | str | None = None,
) -> V8PatentTriageAdapterResult:
  """Score large candidates via patent_triage.py or fallback heuristic."""
  root = Path(project_root) if project_root else None
  profile_include, profile_exclude, profile_companies = _load_case_profile_terms(case_id, root)
  include_terms = list(dict.fromkeys([*profile_include, *include_keywords]))
  exclude_terms = list(dict.fromkeys([*profile_exclude, *exclude_keywords]))

  warnings: list[str] = []
  if not patent_triage_available():
    warnings.append(FALLBACK_WARNING)
    scored = [
      _apply_fallback(r, case_id=case_id, include_keywords=tuple(include_terms), exclude_keywords=tuple(exclude_terms))
      for r in records
    ]
    return V8PatentTriageAdapterResult(
      case_id=case_id,
      triage_engine="fallback_large_candidate_heuristic",
      ranking_policy=FALLBACK_POLICY,
      warnings=warnings,
      scored_records=scored,
    )

  from tech_cartography.services.patent_triage import PatentTriageConfig, score_patent_candidate

  known_assignees = {
    str(r.assignee or r.organization).strip().lower()
    for r in records
    if (r.assignee or r.organization)
  }
  config = PatentTriageConfig(
    include_terms=include_terms,
    exclude_terms=exclude_terms,
    target_companies=profile_companies,
    known_assignees=known_assignees,
  )

  scored_records: list[V8LargeCandidateRecord] = []
  triage_results = []
  for rec in records:
    triage_dict = large_candidate_to_triage_dict(rec)
    result = score_patent_candidate(triage_dict, config)
    triage_results.append(result)
    scored_records.append(_apply_triage_result(rec, result, ranking_policy=PATENT_TRIAGE_POLICY))

  return V8PatentTriageAdapterResult(
    case_id=case_id,
    triage_engine="patent_triage",
    ranking_policy=PATENT_TRIAGE_POLICY,
    warnings=warnings,
    scored_records=scored_records,
    triage_results=triage_results,
  )


def staged_triage_top_n(
  adapter_result: V8PatentTriageAdapterResult,
  *,
  top100: int = 100,
  top20: int = 20,
  top5: int = 5,
) -> tuple[list[V8LargeCandidateRecord], list[V8LargeCandidateRecord], list[V8LargeCandidateRecord]]:
  """Slice adapter scored records into Top100/Top20/Top5."""
  scored = sorted(
    adapter_result.scored_records,
    key=lambda r: (-r.heuristic_score, r.publication_number or r.title),
  )
  top100_n = min(top100, len(scored))
  top20_n = min(top20, top100_n)
  top5_n = min(top5, top20_n)
  return scored[:top100_n], scored[:top20_n], scored[:top5_n]
