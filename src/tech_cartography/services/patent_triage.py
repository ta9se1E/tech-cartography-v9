"""Patent triage scoring for weekly diff and large-candidate shortlists (Phase 4)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

TRIAGE_SCORING_POLICY = (
  "Phase4 patent triage: include_terms +2/term, target_companies +3, US +1, "
  "pub/title/abstract +1 each, new_assignee +1, exclude_terms -5/term — reading priority only"
)


@dataclass
class PatentTriageConfig:
  include_terms: list[str] = field(default_factory=list)
  exclude_terms: list[str] = field(default_factory=list)
  target_companies: list[str] = field(default_factory=list)
  known_assignees: set[str] = field(default_factory=set)

  def to_dict(self) -> dict[str, Any]:
    return {
      "include_terms": list(self.include_terms),
      "exclude_terms": list(self.exclude_terms),
      "target_companies": list(self.target_companies),
      "known_assignees": sorted(self.known_assignees),
    }


@dataclass
class PatentTriageScoreContribution:
  factor_name: str
  matched_value: str = ""
  score_delta: float = 0.0
  reason: str = ""
  evidence_field: str = ""

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class PatentTriageScoredCandidate:
  candidate_id: str
  publication_number: str = ""
  title: str = ""
  abstract: str = ""
  assignee: str = ""
  organization: str = ""
  country_code: str = ""
  year: str = ""
  publication_date: str = ""
  source_type: str = "patent"
  total_score: float = 0.0
  contributions: list[PatentTriageScoreContribution] = field(default_factory=list)
  positive_reasons: list[str] = field(default_factory=list)
  negative_reasons: list[str] = field(default_factory=list)
  matched_include_terms: list[str] = field(default_factory=list)
  matched_exclude_terms: list[str] = field(default_factory=list)
  raw: dict[str, Any] = field(default_factory=dict)

  def to_dict(self) -> dict[str, Any]:
    return {
      "candidate_id": self.candidate_id,
      "publication_number": self.publication_number,
      "title": self.title,
      "abstract": self.abstract,
      "assignee": self.assignee,
      "organization": self.organization,
      "country_code": self.country_code,
      "year": self.year,
      "publication_date": self.publication_date,
      "source_type": self.source_type,
      "total_score": self.total_score,
      "contributions": [c.to_dict() for c in self.contributions],
      "positive_reasons": list(self.positive_reasons),
      "negative_reasons": list(self.negative_reasons),
      "matched_include_terms": list(self.matched_include_terms),
      "matched_exclude_terms": list(self.matched_exclude_terms),
    }


def _candidate_text(candidate: dict[str, Any]) -> str:
  return " ".join([
    str(candidate.get("title") or ""),
    str(candidate.get("abstract") or ""),
    str(candidate.get("assignee") or ""),
    str(candidate.get("organization") or ""),
    str(candidate.get("publication_number") or ""),
  ]).lower()


def _is_us_publication(candidate: dict[str, Any]) -> bool:
  country = str(candidate.get("country_code") or "").strip().upper()
  pub = str(candidate.get("publication_number") or "").strip().upper()
  return country == "US" or pub.startswith("US")


def score_patent_candidate(
  candidate: dict[str, Any],
  config: PatentTriageConfig,
) -> PatentTriageScoredCandidate:
  """Score one patent candidate using Phase 4 triage rules."""
  text = _candidate_text(candidate)
  assignee_blob = " ".join([
    str(candidate.get("assignee") or ""),
    str(candidate.get("organization") or ""),
  ]).lower()

  contributions: list[PatentTriageScoreContribution] = []
  positive: list[str] = []
  negative: list[str] = []
  score = 0.0

  matched_include: list[str] = []
  for term in config.include_terms:
    term_l = term.lower().strip()
    if not term_l:
      continue
    if term_l in text:
      matched_include.append(term)
      score += 2.0
      msg = f'include term "{term}" matched'
      contributions.append(PatentTriageScoreContribution(
        factor_name="include_term_hit",
        matched_value=term,
        score_delta=2.0,
        reason=msg,
        evidence_field="title/abstract/assignee",
      ))
      positive.append(msg)

  for company in config.target_companies:
    company_l = company.lower().strip()
    if company_l and company_l in assignee_blob:
      score += 3.0
      msg = f'target company "{company}" matched assignee'
      contributions.append(PatentTriageScoreContribution(
        factor_name="target_company_hit",
        matched_value=company,
        score_delta=3.0,
        reason=msg,
        evidence_field="assignee",
      ))
      positive.append(msg)

  if _is_us_publication(candidate):
    score += 1.0
    contributions.append(PatentTriageScoreContribution(
      factor_name="us_publication",
      matched_value=str(candidate.get("country_code") or candidate.get("publication_number") or "US"),
      score_delta=1.0,
      reason="US publication",
      evidence_field="country_code/publication_number",
    ))
    positive.append("US publication")

  pub = str(candidate.get("publication_number") or "").strip()
  if pub:
    score += 1.0
    contributions.append(PatentTriageScoreContribution(
      factor_name="publication_number_present",
      matched_value=pub,
      score_delta=1.0,
      reason="publication_number present",
      evidence_field="publication_number",
    ))
    positive.append("publication_number present")

  title = str(candidate.get("title") or "").strip()
  if title:
    score += 1.0
    contributions.append(PatentTriageScoreContribution(
      factor_name="title_present",
      matched_value=title[:60],
      score_delta=1.0,
      reason="title present",
      evidence_field="title",
    ))
    positive.append("title present")

  abstract = str(candidate.get("abstract") or "").strip()
  if abstract:
    score += 1.0
    contributions.append(PatentTriageScoreContribution(
      factor_name="abstract_present",
      matched_value=abstract[:60],
      score_delta=1.0,
      reason="abstract present",
      evidence_field="abstract",
    ))
    positive.append("abstract present")

  assignee = str(candidate.get("assignee") or candidate.get("organization") or "").strip()
  if assignee:
    known = {a.lower() for a in config.known_assignees}
    if assignee.lower() not in known:
      score += 1.0
      contributions.append(PatentTriageScoreContribution(
        factor_name="new_assignee",
        matched_value=assignee[:60],
        score_delta=1.0,
        reason="new assignee (not in known_assignees)",
        evidence_field="assignee",
      ))
      positive.append("new assignee")

  matched_exclude: list[str] = []
  for term in config.exclude_terms:
    term_l = term.lower().strip()
    if not term_l:
      continue
    if term_l in text:
      matched_exclude.append(term)
      score -= 5.0
      msg = f'exclude term "{term}" matched'
      contributions.append(PatentTriageScoreContribution(
        factor_name="exclude_term_hit",
        matched_value=term,
        score_delta=-5.0,
        reason=msg,
        evidence_field="title/abstract/assignee",
      ))
      negative.append(msg)

  return PatentTriageScoredCandidate(
    candidate_id=str(candidate.get("candidate_id") or candidate.get("publication_number") or title[:20]),
    publication_number=pub,
    title=title,
    abstract=abstract,
    assignee=assignee,
    organization=str(candidate.get("organization") or assignee),
    country_code=str(candidate.get("country_code") or ""),
    year=str(candidate.get("year") or ""),
    publication_date=str(candidate.get("publication_date") or ""),
    source_type=str(candidate.get("source_type") or "patent"),
    total_score=round(score, 4),
    contributions=contributions,
    positive_reasons=positive,
    negative_reasons=negative,
    matched_include_terms=matched_include,
    matched_exclude_terms=matched_exclude,
    raw=dict(candidate),
  )


def triage_top_n(
  candidates: list[dict[str, Any]],
  config: PatentTriageConfig,
  *,
  top_n: int,
) -> list[PatentTriageScoredCandidate]:
  """Return top N candidates by triage score (reading priority only)."""
  scored = [score_patent_candidate(c, config) for c in candidates]
  scored.sort(key=lambda r: (-r.total_score, r.publication_number or r.title))
  return scored[:top_n]


def deep_dive_top_n(
  candidates: list[dict[str, Any]],
  config: PatentTriageConfig,
  *,
  top_n: int,
) -> list[PatentTriageScoredCandidate]:
  """Alias for deep-dive shortlist selection (same scoring as triage_top_n)."""
  return triage_top_n(candidates, config, top_n=top_n)
