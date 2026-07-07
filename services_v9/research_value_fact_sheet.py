"""Signal fact sheet for research value synthesis."""

from __future__ import annotations

import re
from typing import Any, Mapping

from services_v9.research_value_theme_axes import (
  AXIS_COMPOSITION,
  AXIS_CONDITION,
  AXIS_HANDLING_PROPERTY,
  AXIS_INTERFACE_PROPERTY,
  AXIS_MATERIAL,
  AXIS_MECHANICAL_PROPERTY,
  AXIS_PROCESS,
  DOMAIN_AXIS_HINTS,
  classify_theme_axis,
)

IMPORTANT_MISSING_BY_SOURCE = {
  "patent": ("add_on_amount", "drying_temperature", "mechanical_property", "comparative_examples"),
  "paper": ("sample_count", "statistics", "matrix_resin", "sizing_removal_method"),
  "web": ("primary_source_link", "quantitative_data", "implementation_stage"),
}


def _text_blob(signal: Mapping[str, Any]) -> tuple[str, str]:
  title = str(signal.get("title", "") or "")
  summary = str(signal.get("summary", "") or signal.get("abstract", "") or "")
  return title, summary


def extract_supported_concepts(signal: Mapping[str, Any]) -> list[dict[str, str]]:
  title, summary = _text_blob(signal)
  blob_title = title.lower()
  blob_summary = summary.lower()
  concepts: list[dict[str, str]] = []
  for hints in DOMAIN_AXIS_HINTS.values():
    for hint in hints:
      if hint in blob_title:
        concepts.append({"concept": hint, "basis": "title"})
      elif hint in blob_summary:
        concepts.append({"concept": hint, "basis": "abstract"})
  deduped: list[dict[str, str]] = []
  seen: set[str] = set()
  for item in concepts:
    key = item["concept"]
    if key in seen:
      continue
    seen.add(key)
    deduped.append(item)
  return deduped


def extract_source_specific_clues(signal: Mapping[str, Any]) -> dict[str, Any]:
  source_type = str(signal.get("source_type", "") or signal.get("type", "") or "").lower()
  if source_type == "web_company":
    source_type = "web"
  title, summary = _text_blob(signal)
  blob = f"{title} {summary}".lower()
  clues: dict[str, Any] = {"source_type": source_type}
  if source_type == "patent":
    clues.update(
      {
        "claim_scope_possible": True,
        "examples_possible": "example" in blob or "embodiment" in blob or "実施例" in blob,
        "comparative_examples_possible": "comparative" in blob or "comparison" in blob or "比較" in blob,
        "publication_number": str(signal.get("source_id", "") or signal.get("publication_number", "") or ""),
      }
    )
  elif source_type == "paper":
    metadata = dict(signal.get("metadata", {}) or {})
    clues.update(
      {
        "doi": str(metadata.get("doi", "") or signal.get("doi", "") or ""),
        "cited_by_count": metadata.get("cited_by_count"),
        "venue_authors_possible": bool(signal.get("organization") or metadata.get("authors")),
      }
    )
  else:
    clues.update(
      {
        "organization": str(signal.get("organization", "") or ""),
        "url_present": bool(signal.get("url") or signal.get("source_url")),
      }
    )
  return clues


def extract_missing_information(
  signal: Mapping[str, Any],
  *,
  supported_concepts: list[Mapping[str, str]],
) -> list[str]:
  source_type = str(signal.get("source_type", "") or signal.get("type", "") or "").lower()
  if source_type == "web_company":
    source_type = "web"
  supported_axes = {classify_theme_axis(item["concept"]) for item in supported_concepts}
  missing: list[str] = []
  if AXIS_COMPOSITION not in supported_axes:
    missing.append("composition_detail")
  if AXIS_PROCESS not in supported_axes:
    missing.append("application_process")
  if AXIS_CONDITION not in supported_axes:
    missing.append("drying_or_curing_condition")
  if AXIS_MECHANICAL_PROPERTY not in supported_axes and source_type == "paper":
    missing.append("mechanical_property")
  missing.extend(list(IMPORTANT_MISSING_BY_SOURCE.get(source_type, ())))
  deduped: list[str] = []
  for item in missing:
    if item not in deduped:
      deduped.append(item)
  return deduped


def build_signal_fact_sheet(signal: Mapping[str, Any], theme_axes: Mapping[str, Any]) -> dict[str, Any]:
  supported = extract_supported_concepts(signal)
  matched_axes = sorted(
    {
      classify_theme_axis(item["concept"])
      for item in supported
      if classify_theme_axis(item["concept"]) in dict(theme_axes.get("axis_terms", {}) or {})
      or classify_theme_axis(item["concept"]) in list(theme_axes.get("priority_axes", []) or [])
    }
  )
  if not matched_axes:
    matched_axes = sorted({classify_theme_axis(item["concept"]) for item in supported})[:3]
  missing = extract_missing_information(signal, supported_concepts=supported)
  source_type = str(signal.get("source_type", "") or signal.get("type", "") or "").lower()
  if source_type == "web_company":
    source_type = "web"
  return {
    "source_type": source_type,
    "title": str(signal.get("title", "") or ""),
    "summary": str(signal.get("summary", "") or ""),
    "supported_concepts": supported,
    "matched_theme_axes": matched_axes,
    "missing_but_important_axes": missing,
    "source_specific_fields": extract_source_specific_clues(signal),
    "matched_terms": list(signal.get("matched_core_terms", []) or []) + list(signal.get("matched_process_terms", []) or []),
    "relevance_reason": str(signal.get("relevance_reason", "") or ""),
    "relevance_score": float(signal.get("relevance_score", signal.get("integrated_relevance_score", 0)) or 0),
    "relevance_tier": str(signal.get("relevance_tier", "") or ""),
  }


def validate_fact_sheet(fact_sheet: Mapping[str, Any]) -> list[str]:
  errors: list[str] = []
  if not fact_sheet.get("source_type"):
    errors.append("missing_source_type")
  supported = list(fact_sheet.get("supported_concepts", []) or [])
  missing = list(fact_sheet.get("missing_but_important_axes", []) or [])
  supported_concepts = {item.get("concept") for item in supported}
  for missing_item in missing:
    if missing_item in supported_concepts:
      errors.append(f"missing_marked_supported:{missing_item}")
  return errors


__all__ = [
  "build_signal_fact_sheet",
  "extract_missing_information",
  "extract_source_specific_clues",
  "extract_supported_concepts",
  "validate_fact_sheet",
]
