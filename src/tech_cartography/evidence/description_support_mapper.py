"""Map claim elements to supporting description/examples/properties."""

from __future__ import annotations

import re
from typing import Any

from tech_cartography.domain.claim_element import ClaimElement


def find_supporting_snippets(
  element: ClaimElement,
  text: str | None,
  section_name: str,
  max_snippets: int = 3,
) -> list[dict[str, str]]:
  if not text:
    return []
  snippets: list[dict[str, str]] = []
  lowered = text.lower()
  for term in element.normalized_terms:
    term_lower = term.lower()
    index = lowered.find(term_lower)
    if index < 0 and not any(ord(ch) > 127 for ch in term):
      continue
    if index < 0:
      index = text.find(term)
    if index < 0:
      continue
    start = max(0, index - 80)
    end = min(len(text), index + len(term) + 120)
    snippet = re.sub(r"\s+", " ", text[start:end]).strip()
    snippets.append({"section": section_name, "term": term, "snippet": snippet})
    if len(snippets) >= max_snippets:
      break
  return snippets


def compute_support_score(element: ClaimElement, snippets: list[dict]) -> float:
  if not snippets:
    return 0.0
  unique_terms = {item.get("term", "").lower() for item in snippets}
  matched = sum(1 for term in element.normalized_terms if term.lower() in unique_terms)
  if not element.normalized_terms:
    return 0.2
  return min(1.0, matched / len(element.normalized_terms))


def assign_support_status(
  element: ClaimElement,
  description_snippets: list[dict],
  example_snippets: list[dict],
  property_hits: list[str],
) -> str:
  if element.support_status == "metadata_only":
    return "metadata_only"
  if property_hits:
    return "supported_by_measured_properties"
  if example_snippets:
    return "supported_by_examples"
  if description_snippets and len(description_snippets) >= 1:
    return "supported_by_description"
  if element.source_section == "claims":
    return "claim_only"
  return "unclear"


def map_description_support(
  record: dict[str, Any],
  elements: list[ClaimElement],
) -> list[ClaimElement]:
  description = str(record.get("description") or "")
  examples = str(record.get("examples") or "")
  measured = [str(item) for item in (record.get("measured_properties") or [])]
  measured_text = " ".join(measured)

  updated: list[ClaimElement] = []
  for element in elements:
    desc_snippets = find_supporting_snippets(element, description, "description")
    example_snippets = find_supporting_snippets(element, examples, "examples")
    property_hits = [
      term
      for term in element.normalized_terms
      if term.lower() in measured_text.lower() or term in measured_text
    ]
    support_status = assign_support_status(
      element,
      desc_snippets,
      example_snippets,
      property_hits,
    )
    support_sections = [item["section"] for item in desc_snippets + example_snippets]
    if property_hits:
      support_sections.append("measured_properties")
    confidence = max(
      element.confidence,
      compute_support_score(element, desc_snippets + example_snippets),
    )
    notes = list(element.notes)
    if support_status != "claim_only":
      notes.append(f"Support mapped from {', '.join(sorted(set(support_sections))) or 'none'}")
    updated.append(
      ClaimElement(
        element_id=element.element_id,
        publication_number=element.publication_number,
        claim_number=element.claim_number,
        element_type=element.element_type,
        element_text=element.element_text,
        normalized_terms=element.normalized_terms,
        source_section=element.source_section,
        evidence_snippet=element.evidence_snippet,
        confidence=round(confidence, 3),
        support_status=support_status,
        support_sections=sorted(set(support_sections)),
        notes=notes,
      ),
    )
  return updated
