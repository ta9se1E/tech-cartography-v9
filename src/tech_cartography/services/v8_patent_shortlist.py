"""v8 Patent Shortlist builder — heuristic scoring (Phase 27D)."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from tech_cartography.runtime.v8_patent_shortlist_schema import (
  SHORTLIST_SAFETY_NOTICES,
  V8PatentCandidate,
  V8PatentShortlist,
)
from tech_cartography.runtime.v8_sources_schema import V8SourceRecord, V8SourcesTable, utc_now_iso
from tech_cartography.services.v8_sources_repository import load_sources_table, resolve_case_name
from tech_cartography.services.v8_sources_table import load_case_profile, project_root_from_here

CASE_AXIS_KEYWORDS: dict[str, tuple[str, ...]] = {
  "case_01_pan_graphitization": (
    "pan", "precursor", "stabilized", "stabilization", "oxidation", "carbonization",
    "graphitization", "tensile", "strength", "modulus", "process", "fiber", "bundle",
  ),
  "case_02_sizing_interface": (
    "sizing", "surface", "treatment", "coating", "interface", "interfacial", "adhesion",
    "matrix", "resin", "composite", "ilss", "shear", "strength",
  ),
  "case_03_pressure_vessel_filament_winding": (
    "pressure", "vessel", "hydrogen", "tank", "filament", "winding", "cfrp", "composite",
    "liner", "type iv", "burst", "fatigue", "hoop",
  ),
}

SPECIFICITY_KEYWORDS: tuple[str, ...] = (
  "process", "property", "material", "application", "strength", "modulus", "temperature",
  "fiber", "resin", "method", "composition", "layer", "winding",
)

EVIDENCE_ROLE_SCORES: dict[str, float] = {
  "claim_source": 1.0,
  "claim_support": 0.95,
  "process_claim_support": 0.9,
  "example_source": 0.85,
  "process_property": 0.8,
  "interface_claim": 0.75,
  "safety_claim": 0.75,
  "unknown": 0.4,
}

SCORE_WEIGHTS: dict[str, float] = {
  "theme_fit_score": 0.25,
  "evidence_potential_score": 0.2,
  "claim_specificity_score": 0.15,
  "recency_score": 0.1,
  "strategic_relevance_score": 0.2,
  "manual_review_priority_score": 0.1,
}


def _blob(record: V8SourceRecord) -> str:
  return f"{record.title} {record.organization} {record.notes}".lower()


def _keyword_hits(text: str, keywords: tuple[str, ...]) -> list[str]:
  hits: list[str] = []
  for kw in keywords:
    if kw.lower() in text:
      hits.append(kw)
  return hits


def _theme_fit_score(record: V8SourceRecord, profile: dict[str, Any]) -> float:
  text = _blob(record)
  seeds = [str(k).lower() for k in (profile.get("seed_keywords") or [])]
  seeds += [str(p).lower() for p in (profile.get("target_processes") or [])]
  seeds += [str(p).lower() for p in (profile.get("target_properties") or [])]
  if not seeds:
    return 0.3
  hits = sum(1 for s in seeds if s and s in text)
  return min(1.0, hits / max(3, len(seeds) * 0.5))


def _evidence_potential_score(record: V8SourceRecord) -> float:
  return EVIDENCE_ROLE_SCORES.get(record.evidence_role, 0.5)


def _claim_specificity_score(record: V8SourceRecord) -> float:
  text = _blob(record)
  hits = sum(1 for kw in SPECIFICITY_KEYWORDS if kw in text)
  return min(1.0, hits / 4.0)


def _recency_score(year_str: str) -> float:
  try:
    year = int(str(year_str).strip())
  except ValueError:
    return 0.4
  if year >= 2015:
    return 1.0
  if year >= 2000:
    return 0.75
  if year >= 1985:
    return 0.55
  return 0.45


def _strategic_relevance_score(record: V8SourceRecord, case_id: str) -> float:
  keywords = CASE_AXIS_KEYWORDS.get(case_id, ())
  hits = _keyword_hits(_blob(record), keywords)
  if not hits:
    return 0.2
  return min(1.0, len(hits) / 3.0)


def _manual_review_priority_score(record: V8SourceRecord) -> float:
  score = 0.0
  if record.publication_number.strip():
    score += 0.5
  if record.url.strip():
    score += 0.4
  if not record.human_review_required:
    score += 0.1
  return min(1.0, score)


def _total_score(breakdown: dict[str, float]) -> float:
  return round(sum(breakdown[k] * SCORE_WEIGHTS[k] for k in SCORE_WEIGHTS), 4)


def _candidate_id(case_id: str, publication_number: str, source_id: str) -> str:
  key = publication_number or source_id
  digest = hashlib.sha256(f"{case_id}|{key}".encode()).hexdigest()[:10]
  return f"{case_id}:patent_candidate:{digest}"


def _build_why_read(record: V8SourceRecord, axes: list[str], breakdown: dict[str, float]) -> str:
  parts = [
    f"heuristic draft selection — theme_fit={breakdown.get('theme_fit_score', 0):.2f}, "
    f"strategic={breakdown.get('strategic_relevance_score', 0):.2f}.",
  ]
  if axes:
    parts.append(f"技術軸候補: {', '.join(axes[:3])}.")
  if record.publication_number:
    parts.append(f"公報番号 {record.publication_number} を原典で確認。")
  parts.append("claim text not loaded — 請求項は未読。")
  return " ".join(parts)


def _build_next_action(record: V8SourceRecord) -> str:
  if record.url:
    return f"Google Patents / 原典公報で請求項・実施例を人手確認: {record.url}"
  if record.publication_number:
    return f"公報番号 {record.publication_number} で請求項を検索・確認（URL未登録）"
  return "publication_number / URL を特定し、請求項を人手確認"


def _build_expected_evidence(record: V8SourceRecord) -> str:
  return (
    f"請求項・実施例の一次確認（{record.publication_number or 'claim text not loaded'}）。"
    " description未確認。関連論文・process-property の裏取りは Evidence Map へ。"
  )


def _build_gap_hypothesis(record: V8SourceRecord) -> str:
  return (
    f"請求項と {record.evidence_role} の対応が未確認。"
    " 実施例・論文 Evidence が Evidence Map で不足している可能性。"
  )


def build_patent_candidate(
  record: V8SourceRecord,
  *,
  profile: dict[str, Any],
  rank: int = 0,
) -> V8PatentCandidate:
  case_id = record.case_id
  breakdown = {
    "theme_fit_score": round(_theme_fit_score(record, profile), 4),
    "evidence_potential_score": round(_evidence_potential_score(record), 4),
    "claim_specificity_score": round(_claim_specificity_score(record), 4),
    "recency_score": round(_recency_score(record.year), 4),
    "strategic_relevance_score": round(_strategic_relevance_score(record, case_id), 4),
    "manual_review_priority_score": round(_manual_review_priority_score(record), 4),
  }
  total = _total_score(breakdown)
  axis_keywords = CASE_AXIS_KEYWORDS.get(case_id, ())
  technical_axes = _keyword_hits(_blob(record), axis_keywords)
  claim_axes = list(profile.get("expected_claim_axes") or [])[:3]

  caution = [
    "heuristic_draft_selection",
    "reading_priority_not_patent_value",
    "claim_text_not_loaded",
    "no_legal_judgement",
  ]
  if record.candidate_information_only:
    caution.append("candidate_information_only")
  if record.human_review_required or not record.url:
    caution.append("human_review_required")

  return V8PatentCandidate(
    candidate_id=_candidate_id(case_id, record.publication_number, record.source_id),
    case_id=case_id,
    rank=rank,
    publication_number=record.publication_number,
    title=record.title,
    assignee_or_organization=record.organization,
    year=record.year,
    url=record.url,
    source_id=record.source_id,
    source_status=record.source_status,
    evidence_role=record.evidence_role,
    related_claim_axes=claim_axes,
    technical_axis_labels=technical_axes,
    theme_fit_score=breakdown["theme_fit_score"],
    evidence_potential_score=breakdown["evidence_potential_score"],
    claim_specificity_score=breakdown["claim_specificity_score"],
    recency_score=breakdown["recency_score"],
    strategic_relevance_score=breakdown["strategic_relevance_score"],
    manual_review_priority_score=breakdown["manual_review_priority_score"],
    total_score=total,
    score_breakdown=breakdown,
    why_read=_build_why_read(record, technical_axes, breakdown),
    key_claim_focus="claim text not loaded — 請求項焦点は原典確認後に Claim Map へ",
    expected_evidence_to_check=_build_expected_evidence(record),
    evidence_gap_hypothesis=_build_gap_hypothesis(record),
    next_verification_action=_build_next_action(record),
    next_phase="Claim Map",
    caution_flags=caution,
    candidate_information_only=record.candidate_information_only,
    human_review_required=record.human_review_required or not record.url.strip(),
    no_legal_judgement=True,
  )


def build_patent_shortlist(
  sources: V8SourcesTable | None = None,
  *,
  case_id: str,
  top_n: int = 5,
  project_root: Any = None,
) -> V8PatentShortlist:
  root = project_root or project_root_from_here()
  if sources is None:
    sources = load_sources_table(case_id, project_root=root)

  profile = load_case_profile(case_id, root) or {}
  case_name = resolve_case_name(case_id, root)
  warnings: list[str] = list(sources.warnings)
  warnings.append(SHORTLIST_SAFETY_NOTICES[0])

  patents = [r for r in sources.records if r.source_type == "patent"]
  excluded: list[str] = []
  ranked: list[V8PatentCandidate] = []

  with_pub = [p for p in patents if p.publication_number.strip()]
  without_pub = [p for p in patents if not p.publication_number.strip()]
  for p in without_pub:
    excluded.append(p.source_id)
    warnings.append(f"excluded patent without publication_number: {p.title}")

  candidates = [build_patent_candidate(p, profile=profile) for p in with_pub]
  candidates.sort(key=lambda c: (-c.total_score, c.publication_number))
  for index, candidate in enumerate(candidates[:top_n], start=1):
    candidate.rank = index
    ranked.append(candidate)

  if len(ranked) < top_n:
    warnings.append(f"only {len(ranked)} patent candidates available (requested top_n={top_n})")

  return V8PatentShortlist(
    case_id=case_id,
    case_name=case_name,
    top_n=top_n,
    count=len(ranked),
    patent_candidates=ranked,
    excluded_sources=excluded,
    warnings=warnings,
    generated_at=utc_now_iso(),
  )
