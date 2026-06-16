"""Source quality evaluation for papers and other evidence sources."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import urlparse

from tech_cartography.domain.paper_record import build_display_url_from_parts


@dataclass
class SourceQualityResult:
  source_id: str
  source_type: str
  source_name: str | None = None
  url: str | None = None
  display_url: str | None = None
  quality_level: str = "unknown"
  quality_score: float = 0.0
  reasons: list[str] = field(default_factory=list)
  warnings: list[str] = field(default_factory=list)
  recommended_use: str = "use_with_caution"

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


def evaluate_url_quality(url: str | None) -> dict[str, Any]:
  if not url:
    return {"has_url": False, "scheme": None, "host": None, "score": 0.0}
  parsed = urlparse(url)
  score = 0.4
  if parsed.scheme in {"http", "https"}:
    score += 0.2
  if parsed.netloc:
    score += 0.2
  if "doi.org" in parsed.netloc:
    score += 0.2
  return {
    "has_url": True,
    "scheme": parsed.scheme,
    "host": parsed.netloc,
    "score": min(1.0, score),
  }


def classify_source_type(source: dict[str, Any]) -> str:
  explicit = str(source.get("source_type") or "").strip()
  if explicit:
    return explicit
  if source.get("openalex_id") or source.get("doi"):
    return "paper"
  if source.get("publication_number"):
    return "patent"
  return "unknown"


def build_display_url(source: dict[str, Any]) -> str | None:
  existing = source.get("display_url")
  if existing:
    return str(existing)
  return build_display_url_from_parts(
    source.get("landing_page_url"),
    source.get("doi"),
    source.get("pdf_url"),
    source.get("openalex_id"),
  )


def evaluate_paper_source_quality(paper: dict[str, Any]) -> SourceQualityResult:
  source_id = str(paper.get("paper_id") or paper.get("openalex_id") or paper.get("doi") or paper.get("title") or "unknown")
  display_url = build_display_url(paper)
  url_info = evaluate_url_quality(display_url)
  score = 0.0
  reasons: list[str] = []
  warnings: list[str] = []

  if paper.get("doi"):
    score += 0.2
    reasons.append("DOI present")
  if paper.get("source_name"):
    score += 0.15
    reasons.append("source_name present")
  if paper.get("title"):
    score += 0.15
    reasons.append("title present")
  if paper.get("publication_year"):
    score += 0.1
    reasons.append("publication_year present")
  if display_url:
    score += 0.15
    reasons.append("display_url present")
  if paper.get("cited_by_count") is not None:
    score += 0.05
    reasons.append("cited_by_count present")
  if paper.get("openalex_id"):
    score += 0.1
    reasons.append("OpenAlex ID present")
  score += url_info["score"] * 0.1

  if not display_url:
    warnings.append("No display URL available")
  if not paper.get("abstract"):
    warnings.append("Abstract missing")

  if score >= 0.7:
    quality_level = "high"
    recommended_use = "cite_as_evidence_candidate"
  elif score >= 0.45:
    quality_level = "medium"
    recommended_use = "cite_as_background"
  elif score >= 0.2:
    quality_level = "low"
    recommended_use = "use_with_caution"
  else:
    quality_level = "unknown"
    recommended_use = "do_not_cite"

  if not display_url and quality_level in {"low", "unknown"}:
    recommended_use = "do_not_cite"

  return SourceQualityResult(
    source_id=source_id,
    source_type="paper",
    source_name=paper.get("source_name"),
    url=display_url,
    display_url=display_url,
    quality_level=quality_level,
    quality_score=round(min(1.0, score), 3),
    reasons=reasons,
    warnings=warnings,
    recommended_use=recommended_use,
  )


def evaluate_source_quality(source: dict[str, Any]) -> SourceQualityResult:
  source_type = classify_source_type(source)
  if source_type == "paper":
    return evaluate_paper_source_quality(source)
  display_url = build_display_url(source)
  url_info = evaluate_url_quality(display_url)
  score = url_info["score"] * 0.5
  if source.get("title"):
    score += 0.2
  quality_level = "medium" if score >= 0.45 else "low" if score >= 0.2 else "unknown"
  return SourceQualityResult(
    source_id=str(source.get("source_id") or source.get("paper_id") or source.get("publication_number") or "unknown"),
    source_type=source_type,
    source_name=source.get("source_name") or source.get("title"),
    url=display_url,
    display_url=display_url,
    quality_level=quality_level,
    quality_score=round(score, 3),
    reasons=["generic source evaluation"],
    warnings=[] if display_url else ["No display URL available"],
    recommended_use="use_with_caution" if display_url else "do_not_cite",
  )
