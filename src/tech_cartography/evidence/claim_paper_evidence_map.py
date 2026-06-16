"""Build Patent Claim × Paper Evidence Map."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from typing import Any

from tech_cartography.domain.evidence_map import ClaimPaperEvidenceItem, PatentEvidenceMap
from tech_cartography.evidence.evidence_confidence import (
  build_evidence_caveat,
  compute_evidence_score,
  recommend_human_check,
  upgrade_or_downgrade_relation,
)
from tech_cartography.evidence.evidence_gap_analyzer import analyze_evidence_gaps


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


def _lookup_by_id(rows: list[dict[str, Any]] | None, key_field: str) -> dict[str, dict[str, Any]]:
  lookup: dict[str, dict[str, Any]] = {}
  for row in rows or []:
    key = str(row.get(key_field) or row.get("source_id") or "")
    if key:
      lookup[key] = row
  return lookup


def _item_to_dict(item: ClaimPaperEvidenceItem) -> dict[str, Any]:
  return item.to_dict()


def build_evidence_items_for_element(
  element: dict[str, Any],
  links: list[dict[str, Any]],
  paper_by_id: dict[str, dict[str, Any]],
  source_quality_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
  items: list[dict[str, Any]] = []
  element_id = str(element.get("element_id"))
  publication_number = str(element.get("publication_number"))
  patent_title = element.get("title") or element.get("patent_title")
  assignee = element.get("assignee")
  normalized_terms = _parse_terms(element.get("normalized_terms"))
  claim_support_status = str(element.get("support_status") or element.get("claim_support_status") or "unclear")

  if not links:
    item = ClaimPaperEvidenceItem(
      publication_number=publication_number,
      patent_title=patent_title,
      assignee=assignee,
      element_id=element_id,
      element_type=str(element.get("element_type", "unknown")),
      element_text=str(element.get("element_text", "")),
      normalized_terms=normalized_terms,
      claim_support_status=claim_support_status,
      evidence_relation="no_paper_evidence",
      evidence_confidence="unknown",
      evidence_score=0.0,
      relation_reason="No paper evidence link found for this claim element.",
      caveat=build_evidence_caveat("no_paper_evidence", "unknown", None),
      recommended_human_check=recommend_human_check("no_paper_evidence", "unknown"),
    )
    return [_item_to_dict(item)]

  for link in links:
    paper_id = str(link.get("paper_id") or "")
    paper = paper_by_id.get(paper_id, {})
    source_quality = source_quality_by_id.get(paper_id, {})
    enriched_link = dict(link)
    enriched_link.update(
      {
        "paper_title": link.get("paper_title") or paper.get("title"),
        "paper_year": link.get("paper_year") or paper.get("publication_year"),
        "source_name": link.get("source_name") or paper.get("source_name"),
        "doi": link.get("doi") or paper.get("doi"),
        "display_url": link.get("display_url") or paper.get("display_url"),
        "abstract": paper.get("abstract"),
      },
    )
    scored = upgrade_or_downgrade_relation(enriched_link, element, source_quality)
    relation = str(scored.get("evidence_relation", "unrelated"))
    confidence = str(scored.get("evidence_confidence", "unknown"))
    quality_level = str(
      scored.get("source_quality_level")
      or source_quality.get("quality_level")
      or "unknown",
    )
    item = ClaimPaperEvidenceItem(
      publication_number=publication_number,
      patent_title=patent_title,
      assignee=assignee,
      element_id=element_id,
      element_type=str(element.get("element_type", "unknown")),
      element_text=str(element.get("element_text", "")),
      normalized_terms=normalized_terms,
      claim_support_status=claim_support_status,
      paper_id=paper_id or None,
      paper_title=scored.get("paper_title"),
      paper_year=int(scored["paper_year"]) if scored.get("paper_year") not in (None, "") else None,
      source_name=scored.get("source_name"),
      doi=scored.get("doi"),
      display_url=scored.get("display_url"),
      source_quality_level=quality_level,
      source_quality_score=float(scored.get("source_quality_score") or source_quality.get("quality_score") or 0.0)
      if (scored.get("source_quality_score") or source_quality.get("quality_score")) not in (None, "")
      else None,
      evidence_relation=relation,
      evidence_confidence=confidence,
      evidence_score=float(scored.get("evidence_score", compute_evidence_score(scored, element, source_quality))),
      matched_terms=_parse_terms(scored.get("matched_terms")),
      relation_reason=str(scored.get("relation_reason") or ""),
      caveat=build_evidence_caveat(relation, confidence, quality_level),
      recommended_human_check=recommend_human_check(relation, confidence),
    )
    if relation != "unrelated":
      items.append(_item_to_dict(item))
  return items


def summarize_evidence_by_patent(patent_map: dict[str, Any]) -> dict[str, Any]:
  items = patent_map.get("evidence_items", [])
  relation_counter = Counter(item.get("evidence_relation") for item in items)
  confidence_counter = Counter(item.get("evidence_confidence") for item in items)
  return {
    "publication_number": patent_map.get("publication_number"),
    "total_items": len(items),
    "relation_counts": dict(relation_counter),
    "confidence_counts": dict(confidence_counter),
    "high_quality_sources": sum(
      1 for item in items if item.get("source_quality_level") == "high"
    ),
  }


def summarize_evidence_by_element_type(evidence_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
  grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
  for item in evidence_items:
    grouped[str(item.get("element_type", "unknown"))].append(item)

  summaries: list[dict[str, Any]] = []
  for element_type, items in sorted(grouped.items()):
    relation_counter = Counter(item.get("evidence_relation") for item in items)
    summaries.append(
      {
        "element_type": element_type,
        "item_count": len(items),
        "supporting_candidates": relation_counter.get("supporting_evidence_candidate", 0)
        + relation_counter.get("strong_evidence_candidate", 0),
        "background_evidence": relation_counter.get("background_evidence", 0),
        "weak_matches": relation_counter.get("weak_match", 0),
        "no_paper_evidence": relation_counter.get("no_paper_evidence", 0),
      },
    )
  return summaries


def select_top_evidence_items(evidence_items: list[dict[str, Any]], top_n: int = 30) -> list[dict[str, Any]]:
  ranked = sorted(
    evidence_items,
    key=lambda item: (
      item.get("evidence_relation") not in {"strong_evidence_candidate", "supporting_evidence_candidate"},
      item.get("evidence_confidence") != "high",
      -float(item.get("evidence_score") or 0.0),
    ),
  )
  return ranked[:top_n]


def build_patent_evidence_maps(
  evidence_items: list[dict[str, Any]],
  claim_elements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
  elements_by_patent: dict[str, list[dict[str, Any]]] = defaultdict(list)
  for element in claim_elements:
    elements_by_patent[str(element.get("publication_number"))].append(element)

  items_by_patent: dict[str, list[dict[str, Any]]] = defaultdict(list)
  for item in evidence_items:
    items_by_patent[str(item.get("publication_number"))].append(item)

  patent_maps: list[dict[str, Any]] = []
  for publication_number, elements in elements_by_patent.items():
    items = items_by_patent.get(publication_number, [])
    element_ids = {str(element.get("element_id")) for element in elements}
    supporting_element_ids = {
      str(item.get("element_id"))
      for item in items
      if item.get("evidence_relation") in {"strong_evidence_candidate", "supporting_evidence_candidate"}
    }
    background_element_ids = {
      str(item.get("element_id"))
      for item in items
      if item.get("evidence_relation") == "background_evidence"
    }
    elements_without_papers = {
      element_id
      for element_id in element_ids
      if all(
        item.get("evidence_relation") == "no_paper_evidence"
        for item in items
        if str(item.get("element_id")) == element_id
      )
    }
    first_element = elements[0]
    patent_map = PatentEvidenceMap(
      publication_number=publication_number,
      patent_title=first_element.get("title") or first_element.get("patent_title"),
      assignee=first_element.get("assignee"),
      evidence_level=first_element.get("evidence_level"),
      total_claim_elements=len(elements),
      elements_with_supporting_papers=len(supporting_element_ids),
      elements_with_background_papers=len(background_element_ids),
      elements_without_papers=len(elements_without_papers),
      high_quality_sources=sum(1 for item in items if item.get("source_quality_level") == "high"),
      evidence_items=[ClaimPaperEvidenceItem.from_dict(item) for item in items],
      evidence_summary=summarize_evidence_by_patent(
        {"publication_number": publication_number, "evidence_items": items},
      ),
      caveats=[
        "OpenAlex papers are evidence candidates, not proof of patent claims.",
        "SourceQuality reflects reference usability, not technical correctness.",
      ],
      next_actions=[
        "Review top supporting evidence candidates manually.",
        "Address evidence gaps with broader queries or manual literature review.",
      ],
    )
    patent_maps.append(patent_map.to_dict())
  return patent_maps


def build_claim_paper_evidence_map(
  claim_elements: list[dict[str, Any]],
  paper_links: list[dict[str, Any]],
  paper_records: list[dict[str, Any]] | None = None,
  source_quality_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
  warnings: list[str] = []
  errors: list[str] = []

  paper_by_id = _lookup_by_id(paper_records, "paper_id")
  source_quality_by_id = _lookup_by_id(source_quality_results, "source_id")
  for paper in paper_records or []:
    paper_id = str(paper.get("paper_id") or "")
    if paper_id:
      paper_by_id[paper_id] = paper
      if paper_id not in source_quality_by_id:
        source_quality_by_id[paper_id] = {
          "source_id": paper_id,
          "quality_level": paper.get("source_quality_level"),
          "quality_score": paper.get("source_quality_score"),
        }

  links_by_element: dict[str, list[dict[str, Any]]] = defaultdict(list)
  for link in paper_links:
    key = str(link.get("element_id"))
    links_by_element[key].append(link)

  evidence_items: list[dict[str, Any]] = []
  seen_element_ids: set[str] = set()
  for element in claim_elements:
    element_id = str(element.get("element_id"))
    seen_element_ids.add(element_id)
    items = build_evidence_items_for_element(
      element,
      links_by_element.get(element_id, []),
      paper_by_id,
      source_quality_by_id,
    )
    evidence_items.extend(items)

  if not claim_elements:
    warnings.append("No claim elements provided.")

  patent_evidence_maps = build_patent_evidence_maps(evidence_items, claim_elements)
  evidence_by_element_type = summarize_evidence_by_element_type(evidence_items)
  top_evidence_items = select_top_evidence_items(evidence_items, top_n=30)
  evidence_gaps = analyze_evidence_gaps(evidence_items, claim_elements)

  relation_counter = Counter(item.get("evidence_relation") for item in evidence_items)
  return {
    "status": "ok",
    "total_patents": len({element.get("publication_number") for element in claim_elements}),
    "total_claim_elements": len(claim_elements),
    "total_evidence_items": len(evidence_items),
    "strong_evidence_candidates": relation_counter.get("strong_evidence_candidate", 0),
    "supporting_evidence_candidates": relation_counter.get("supporting_evidence_candidate", 0),
    "background_evidence_items": relation_counter.get("background_evidence", 0),
    "weak_matches": relation_counter.get("weak_match", 0),
    "no_paper_evidence_items": relation_counter.get("no_paper_evidence", 0),
    "patent_evidence_maps": patent_evidence_maps,
    "evidence_items": evidence_items,
    "evidence_by_element_type": evidence_by_element_type,
    "top_evidence_items": top_evidence_items,
    "evidence_gaps": evidence_gaps,
    "warnings": warnings,
    "errors": errors,
  }
