"""Evidence confidence scoring for claim-paper evidence mapping."""

from __future__ import annotations

import json
import re
from typing import Any

GENERIC_TERMS = {"carbon fiber", "carbon fibre", "cfrp", "composite", "炭素繊維", "複合材"}
STRONG_SUPPORT_STATUSES = {"supported_by_examples", "supported_by_measured_properties"}


def _parse_terms(value: Any) -> list[str]:
  if isinstance(value, list):
    return [str(item).strip() for item in value if str(item).strip()]
  if isinstance(value, str):
    text = value.strip()
    if not text:
      return []
    if text.startswith("["):
      try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
          return [str(item).strip() for item in parsed if str(item).strip()]
      except json.JSONDecodeError:
        pass
    return [part.strip() for part in re.split(r"[;,]", text) if part.strip()]
  return []


def _to_float(value: Any, default: float = 0.0) -> float:
  try:
    return float(value)
  except (TypeError, ValueError):
    return default


def compute_evidence_score(
  link: dict[str, Any],
  claim_element: dict[str, Any] | None = None,
  source_quality: dict[str, Any] | None = None,
) -> float:
  relation = str(link.get("evidence_relation", ""))
  if relation == "unrelated":
    return 0.0

  score = _to_float(link.get("relevance_score"), 0.0) * 0.45
  matched_terms = _parse_terms(link.get("matched_terms"))
  if matched_terms:
    score += min(0.25, 0.08 * len(matched_terms))
  if len(matched_terms) >= 2:
    score += 0.1

  quality_level = str((source_quality or {}).get("quality_level") or link.get("source_quality_level") or "")
  quality_score = _to_float(
    (source_quality or {}).get("quality_score") or link.get("source_quality_score"),
    0.0,
  )
  if quality_level == "high":
    score += 0.15
  elif quality_level == "medium":
    score += 0.08
  elif quality_level in {"low", "unknown"}:
    score -= 0.05

  if relation in {"strong_evidence_candidate", "supporting_evidence_candidate"}:
    score += 0.12
  elif relation == "background_evidence":
    score += 0.05
  elif relation == "weak_match":
    score -= 0.1

  claim_element = claim_element or {}
  support_status = str(claim_element.get("support_status") or claim_element.get("claim_support_status") or "")
  if support_status in STRONG_SUPPORT_STATUSES:
    score += 0.08
  elif support_status == "claim_only":
    score -= 0.03

  element_type = str(claim_element.get("element_type") or link.get("element_type") or "")
  if element_type in {"material", "process", "property"} and len(matched_terms) >= 2:
    score += 0.08

  generic_only = matched_terms and all(term.lower() in GENERIC_TERMS for term in matched_terms)
  if generic_only:
    score -= 0.15

  if not link.get("paper_title"):
    score -= 0.05
  if not link.get("display_url"):
    score -= 0.05
  if not link.get("abstract") and not link.get("paper_abstract"):
    score -= 0.03

  return round(max(0.0, min(1.0, score)), 3)


def assign_evidence_confidence(
  score: float,
  relation: str,
  source_quality_level: str | None,
) -> str:
  if relation in {"no_paper_evidence", "unrelated"}:
    return "unknown" if relation == "no_paper_evidence" else "low"
  if relation == "weak_match":
    return "low"
  if score >= 0.7 and relation in {"strong_evidence_candidate", "supporting_evidence_candidate"}:
    if source_quality_level in {"high", "medium"}:
      return "high"
    return "medium"
  if score >= 0.45:
    return "medium"
  if score >= 0.2:
    return "low"
  return "unknown"


def upgrade_or_downgrade_relation(
  link: dict[str, Any],
  claim_element: dict[str, Any] | None = None,
  source_quality: dict[str, Any] | None = None,
) -> dict[str, Any]:
  updated = dict(link)
  relation = str(link.get("evidence_relation", "unrelated"))
  score = compute_evidence_score(link, claim_element, source_quality)
  quality_level = str((source_quality or {}).get("quality_level") or link.get("source_quality_level") or "")

  if relation == "supporting_evidence_candidate":
    if score >= 0.75 and quality_level == "high" and len(_parse_terms(link.get("matched_terms"))) >= 2:
      relation = "strong_evidence_candidate"
  elif relation == "background_evidence" and score < 0.2:
    relation = "weak_match"
  elif relation == "weak_match" and score >= 0.5 and quality_level in {"high", "medium"}:
    relation = "background_evidence"

  updated["evidence_relation"] = relation
  updated["evidence_score"] = score
  updated["evidence_confidence"] = assign_evidence_confidence(score, relation, quality_level)
  return updated


def build_evidence_caveat(
  relation: str,
  confidence: str,
  source_quality_level: str | None,
) -> str:
  parts = [
    "This is an evidence candidate, not proof of the patent claim.",
  ]
  if relation == "no_paper_evidence":
    parts.append("No related paper candidate was found for this claim element.")
  elif relation == "strong_evidence_candidate":
    parts.append("Multiple terms align with a paper candidate; human review is still required.")
  elif relation == "supporting_evidence_candidate":
    parts.append("Paper candidate may support the claim element but does not prove it.")
  elif relation == "background_evidence":
    parts.append("Paper appears related to the broader theme rather than this specific claim element.")
  elif relation == "weak_match":
    parts.append("Only weak term overlap was detected.")
  elif relation == "unrelated":
    parts.append("Paper appears unrelated to the claim element.")

  if confidence == "high":
    parts.append("Confidence is relatively high for candidate screening, not for legal or technical proof.")
  elif confidence in {"low", "unknown"}:
    parts.append("Confidence is limited due to sparse overlap or missing source metadata.")

  if source_quality_level in {"low", "unknown", None}:
    parts.append("Source quality is limited; verify the reference URL and bibliographic metadata manually.")

  return " ".join(parts)


def recommend_human_check(relation: str, confidence: str) -> str:
  if relation == "no_paper_evidence":
    return "Expand OpenAlex queries or add manual literature review."
  if relation in {"strong_evidence_candidate", "supporting_evidence_candidate"} and confidence in {"high", "medium"}:
    return "Review paper abstract and compare with claim element before citing."
  if relation == "background_evidence":
    return "Use as background context only unless a stronger match is found."
  if relation == "weak_match":
    return "Treat as low-priority candidate; consider broader search terms."
  if relation == "unrelated":
    return "Exclude unless manual review suggests relevance."
  return "Manual expert review recommended."
