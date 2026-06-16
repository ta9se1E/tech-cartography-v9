"""Evidence gap analysis for claim-paper evidence mapping."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any

SUPPORTING_RELATIONS = {"strong_evidence_candidate", "supporting_evidence_candidate"}
BACKGROUND_RELATIONS = {"background_evidence"}
WEAK_RELATIONS = {"weak_match"}


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


def classify_gap_type(element: dict[str, Any], related_items: list[dict[str, Any]]) -> str:
  if not related_items or all(
    item.get("evidence_relation") == "no_paper_evidence" for item in related_items
  ):
    return "no_paper_found"

  relations = {str(item.get("evidence_relation")) for item in related_items}
  quality_levels = {
    str(item.get("source_quality_level"))
    for item in related_items
    if item.get("source_quality_level")
  }

  if relations <= WEAK_RELATIONS | {"no_paper_evidence", "unrelated"}:
    return "weak_only"

  support_status = str(element.get("support_status") or element.get("claim_support_status") or "")
  if support_status == "claim_only" and not (relations & SUPPORTING_RELATIONS):
    return "claim_only_no_description_support"

  if relations <= BACKGROUND_RELATIONS | WEAK_RELATIONS | {"no_paper_evidence"}:
    if not (relations & SUPPORTING_RELATIONS):
      return "background_only"

  if quality_levels and quality_levels <= {"low", "unknown"}:
    return "low_quality_sources_only"

  terms = _parse_terms(element.get("normalized_terms"))
  if len(terms) <= 1:
    return "insufficient_query_terms"

  return "background_only"


def recommend_gap_action(gap: dict[str, Any]) -> str:
  gap_type = str(gap.get("gap_type", ""))
  mapping = {
    "no_paper_found": "Broaden OpenAlex query terms and rerun paper evidence search.",
    "weak_only": "Refine query with material/process/property combinations or add manual literature review.",
    "background_only": "Review examples and measured properties; consider more specific search terms.",
    "low_quality_sources_only": "Seek papers with DOI/journal metadata or verify URLs manually.",
    "claim_only_no_description_support": "Check description/examples in full text and strengthen patent-side support.",
    "insufficient_query_terms": "Expand normalized terms during claim element extraction or query building.",
  }
  if gap_type in mapping:
    return mapping[gap_type]
  return "Manual expert review recommended."


def analyze_evidence_gaps(
  evidence_items: list[dict[str, Any]],
  claim_elements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
  items_by_element: dict[str, list[dict[str, Any]]] = defaultdict(list)
  for item in evidence_items:
    key = str(item.get("element_id"))
    items_by_element[key].append(item)

  gaps: list[dict[str, Any]] = []
  for element in claim_elements:
    element_id = str(element.get("element_id"))
    related = items_by_element.get(element_id, [])
    gap_type = classify_gap_type(element, related)
    if gap_type in {"background_only", "insufficient_query_terms"} and any(
      item.get("evidence_relation") in SUPPORTING_RELATIONS for item in related
    ):
      continue
    if gap_type == "background_only" and any(
      item.get("evidence_relation") in SUPPORTING_RELATIONS for item in related
    ):
      continue

    should_report = gap_type in {
      "no_paper_found",
      "weak_only",
      "background_only",
      "low_quality_sources_only",
      "claim_only_no_description_support",
      "insufficient_query_terms",
    }
    if not should_report:
      continue

    gap = {
      "publication_number": element.get("publication_number"),
      "element_id": element_id,
      "element_type": element.get("element_type"),
      "element_text": element.get("element_text"),
      "claim_support_status": element.get("support_status") or element.get("claim_support_status"),
      "gap_type": gap_type,
      "related_item_count": len(related),
      "recommended_action": "",
    }
    gap["recommended_action"] = recommend_gap_action(gap)
    gaps.append(gap)
  return gaps


def summarize_gaps_by_patent(gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
  grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
  for gap in gaps:
    grouped[str(gap.get("publication_number"))].append(gap)

  summaries: list[dict[str, Any]] = []
  for publication_number, patent_gaps in grouped.items():
    gap_types = defaultdict(int)
    for gap in patent_gaps:
      gap_types[str(gap.get("gap_type"))] += 1
    summaries.append(
      {
        "publication_number": publication_number,
        "gap_count": len(patent_gaps),
        "gap_types": dict(gap_types),
        "gaps": patent_gaps,
      },
    )
  return summaries
