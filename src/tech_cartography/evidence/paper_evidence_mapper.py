"""Map OpenAlex papers to claim elements."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any

from tech_cartography.evidence.source_quality_agent import evaluate_paper_source_quality

THEME_TERMS = {
  "carbon fiber",
  "carbon fibre",
  "pan",
  "polyacrylonitrile",
  "cfrp",
  "炭素繊維",
  "複合材",
}
NOISE_TERMS = {
  "machine learning",
  "deep learning",
  "stock market",
  "social media",
  "blockchain",
}


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


def _paper_text(paper: dict[str, Any]) -> str:
  parts = [
    str(paper.get("title") or ""),
    str(paper.get("abstract") or ""),
    " ".join(_parse_terms(paper.get("concepts"))),
    " ".join(_parse_terms(paper.get("keywords"))),
    str(paper.get("query") or ""),
  ]
  return " ".join(parts).lower()


def _term_in_text(term: str, text: str) -> bool:
  lowered = term.lower()
  if any(ord(ch) > 127 for ch in term):
    return term in text
  if lowered == "pan":
    return bool(re.search(r"\bpan\b", text))
  return lowered in text


def compute_paper_claim_relevance(paper: dict[str, Any], element: dict[str, Any]) -> dict[str, Any]:
  paper_text = _paper_text(paper)
  terms = _parse_terms(element.get("normalized_terms"))
  matched_terms = [term for term in terms if _term_in_text(term, paper_text)]
  title_text = str(paper.get("title") or "").lower()
  abstract_text = str(paper.get("abstract") or "").lower()
  title_matches = [term for term in terms if _term_in_text(term, title_text)]
  abstract_matches = [term for term in terms if _term_in_text(term, abstract_text)]

  type_hits = {
    element_type: 1
    for element_type in ("material", "process", "property")
    if str(element.get("element_type")) == element_type
    and any(_term_in_text(term, paper_text) for term in terms)
  }
  priority_bonus = {"high": 0.15, "medium": 0.08, "low": 0.0}.get(
    str(paper.get("query_priority") or element.get("query_priority") or "").lower(),
    0.0,
  )
  base = 0.0
  if matched_terms:
    base += min(0.6, 0.2 * len(matched_terms))
  if title_matches:
    base += 0.15
  if abstract_matches:
    base += 0.1
  if len(type_hits) >= 2:
    base += 0.15
  relevance_score = min(1.0, base + priority_bonus)

  return {
    "matched_terms": matched_terms,
    "title_matches": title_matches,
    "abstract_matches": abstract_matches,
    "relevance_score": round(relevance_score, 3),
    "theme_match": any(term in paper_text for term in THEME_TERMS),
    "noise_match": any(term in paper_text for term in NOISE_TERMS),
    "generic_only": matched_terms == ["carbon fiber"] or (
      len(matched_terms) == 1 and matched_terms[0].lower() in THEME_TERMS
    ),
  }


def classify_evidence_relation(relevance: dict[str, Any], source_quality: dict[str, Any]) -> str:
  if relevance.get("noise_match") and not relevance.get("theme_match"):
    return "unrelated"
  matched_count = len(relevance.get("matched_terms", []))
  quality_level = str(source_quality.get("quality_level", "unknown"))
  if matched_count >= 2 and relevance.get("relevance_score", 0) >= 0.45:
    if quality_level in {"high", "medium"}:
      return "supporting_evidence_candidate"
    return "background_evidence"
  if relevance.get("theme_match") and matched_count <= 1:
    if relevance.get("generic_only"):
      return "background_evidence"
    if matched_count == 1:
      return "weak_match"
    return "background_evidence"
  if matched_count == 1:
    return "weak_match"
  if relevance.get("theme_match"):
    return "background_evidence"
  return "unrelated"


def deduplicate_papers(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
  deduped: list[dict[str, Any]] = []
  seen: set[str] = set()
  for paper in papers:
    key = (
      str(paper.get("doi") or "").lower()
      or str(paper.get("openalex_id") or "").lower()
      or str(paper.get("paper_id") or "").lower()
    )
    if not key or key in seen:
      continue
    seen.add(key)
    deduped.append(paper)
  return deduped


def build_paper_evidence_links(
  papers: list[dict[str, Any]],
  claim_elements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
  links: list[dict[str, Any]] = []
  element_lookup = {str(element.get("element_id")): element for element in claim_elements}

  for paper in papers:
    element_id = str(paper.get("element_id") or "")
    element = element_lookup.get(element_id)
    if not element:
      for candidate in claim_elements:
        if str(candidate.get("publication_number")) == str(paper.get("publication_number")):
          element = candidate
          break
    if not element:
      continue

    relevance = compute_paper_claim_relevance(paper, element)
    source_quality = evaluate_paper_source_quality(paper).to_dict()
    evidence_relation = classify_evidence_relation(relevance, source_quality)
    if evidence_relation == "unrelated":
      continue

    reason_parts = []
    if relevance.get("matched_terms"):
      reason_parts.append(f"matched_terms={', '.join(relevance['matched_terms'])}")
    reason_parts.append(f"relevance_score={relevance.get('relevance_score')}")
    reason_parts.append(f"source_quality={source_quality.get('quality_level')}")

    links.append(
      {
        "publication_number": element.get("publication_number"),
        "element_id": element.get("element_id"),
        "element_type": element.get("element_type"),
        "element_text": element.get("element_text"),
        "paper_id": paper.get("paper_id"),
        "paper_title": paper.get("title"),
        "paper_year": paper.get("publication_year"),
        "source_name": paper.get("source_name"),
        "doi": paper.get("doi"),
        "display_url": paper.get("display_url") or source_quality.get("display_url"),
        "source_quality_level": source_quality.get("quality_level"),
        "source_quality_score": source_quality.get("quality_score"),
        "evidence_relation": evidence_relation,
        "relevance_score": relevance.get("relevance_score"),
        "matched_terms": relevance.get("matched_terms"),
        "relation_reason": "; ".join(reason_parts),
        "recommended_use": source_quality.get("recommended_use"),
      },
    )
  return links


def summarize_paper_evidence_by_patent(evidence_links: list[dict[str, Any]]) -> list[dict[str, Any]]:
  grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
  for link in evidence_links:
    grouped[str(link.get("publication_number"))].append(link)

  summaries: list[dict[str, Any]] = []
  for publication_number, links in grouped.items():
    relation_counts: dict[str, int] = defaultdict(int)
    for link in links:
      relation_counts[str(link.get("evidence_relation"))] += 1
    top_links = sorted(links, key=lambda item: item.get("relevance_score", 0), reverse=True)[:5]
    summaries.append(
      {
        "publication_number": publication_number,
        "linked_papers_count": len({link.get("paper_id") for link in links}),
        "claim_elements_linked": len({link.get("element_id") for link in links}),
        "supporting_evidence_candidates": relation_counts.get("supporting_evidence_candidate", 0),
        "background_evidence": relation_counts.get("background_evidence", 0),
        "weak_matches": relation_counts.get("weak_match", 0),
        "top_linked_papers": [
          {
            "paper_title": link.get("paper_title"),
            "evidence_relation": link.get("evidence_relation"),
            "relevance_score": link.get("relevance_score"),
            "display_url": link.get("display_url"),
          }
          for link in top_links
        ],
      },
    )
  return summaries


def map_papers_to_claim_elements(
  papers: list[dict[str, Any]],
  claim_elements: list[dict[str, Any]],
) -> dict[str, Any]:
  deduped = deduplicate_papers(papers)
  links = build_paper_evidence_links(deduped, claim_elements)
  by_patent = summarize_paper_evidence_by_patent(links)
  return {
    "papers_dedup": deduped,
    "evidence_links": links,
    "evidence_by_patent": by_patent,
  }
