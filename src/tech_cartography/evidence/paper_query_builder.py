"""Build paper search query candidates from claim elements."""

from __future__ import annotations

import uuid
from typing import Any

from tech_cartography.domain.claim_element import ClaimElement

HIGH_PRIORITY_TYPES = {
  "material",
  "process",
  "property",
  "numerical_condition",
  "structure",
}
MEDIUM_PRIORITY_TYPES = {"application", "evaluation_method"}
LOW_PRIORITY_TYPES = {"unknown", "problem_effect"}


def _query_priority(element: ClaimElement, query: str) -> str:
  lowered = query.lower()
  type_count = sum(
    1
    for element_type in ("material", "process", "property")
    if element_type in {element.element_type}
    or any(token in lowered for token in ("pan", "carbonization", "modulus", "tensile"))
  )
  if element.element_type in HIGH_PRIORITY_TYPES and type_count >= 1:
    if element.element_type in {"material", "process", "property", "numerical_condition"}:
      return "high"
  if "surface treatment" in lowered or "interface adhesion" in lowered:
    return "high"
  if element.element_type in MEDIUM_PRIORITY_TYPES:
    return "medium"
  if "carbon fiber" in lowered and len(element.normalized_terms) <= 2:
    return "low"
  return "medium"


def build_paper_queries_for_element(
  element: ClaimElement,
  max_queries: int = 3,
) -> list[dict[str, Any]]:
  if not element.normalized_terms:
    return []
  terms = element.normalized_terms[:6]
  queries: list[dict[str, Any]] = []

  primary_query = " ".join(terms[:4])
  queries.append(
    {
      "query_id": f"pq-{uuid.uuid4().hex[:8]}",
      "publication_number": element.publication_number,
      "element_id": element.element_id,
      "element_type": element.element_type,
      "query": primary_query,
      "purpose": "openalex_paper_evidence_search",
      "priority": _query_priority(element, primary_query),
      "reason": f"Derived from {element.element_type} claim element",
    },
  )

  if element.element_type in {"material", "process", "property"} and len(terms) >= 2:
    combo = " ".join(terms[:3])
    queries.append(
      {
        "query_id": f"pq-{uuid.uuid4().hex[:8]}",
        "publication_number": element.publication_number,
        "element_id": element.element_id,
        "element_type": element.element_type,
        "query": combo,
        "purpose": "material_process_property_combo",
        "priority": "high",
        "reason": "material + process + property style query",
      },
    )

  if element.element_type == "structure" and "prepreg" in " ".join(terms).lower():
    query = "carbon fiber bundle resin impregnation prepreg"
    queries.append(
      {
        "query_id": f"pq-{uuid.uuid4().hex[:8]}",
        "publication_number": element.publication_number,
        "element_id": element.element_id,
        "element_type": element.element_type,
        "query": query,
        "purpose": "bundle_prepreg_search",
        "priority": "high",
        "reason": "bundle/prepreg structure-application query",
      },
    )

  deduped: list[dict[str, Any]] = []
  seen: set[str] = set()
  for item in queries:
    key = item["query"].lower()
    if key in seen:
      continue
    seen.add(key)
    deduped.append(item)
    if len(deduped) >= max_queries:
      break
  return deduped


def build_paper_queries_for_record(record_result: dict[str, Any]) -> list[dict[str, Any]]:
  queries: list[dict[str, Any]] = []
  for element in record_result.get("elements", []):
    claim_element = (
      element if isinstance(element, ClaimElement) else ClaimElement.from_dict(element)
    )
    queries.extend(build_paper_queries_for_element(claim_element))
  return queries


def prioritize_paper_queries(queries: list[dict[str, Any]], top_n: int = 20) -> list[dict[str, Any]]:
  priority_order = {"high": 0, "medium": 1, "low": 2}
  return sorted(
    queries,
    key=lambda item: priority_order.get(str(item.get("priority", "medium")), 9),
  )[:top_n]
