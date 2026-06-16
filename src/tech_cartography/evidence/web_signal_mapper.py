"""Map web / company signals to patents and technology clusters."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from typing import Any

from tech_cartography.evidence.company_name_normalizer import match_company_name
from tech_cartography.evidence.web_signal_quality import evaluate_web_signal_quality

BUSINESS_SIGNAL_TYPES = {
  "product_launch",
  "capital_investment",
  "production_expansion",
  "partnership",
  "joint_development",
  "ir_strategy",
}
BACKGROUND_SIGNAL_TYPES = {
  "market_report",
  "industry_news",
  "exhibition",
  "patent_related_news",
  "customer_adoption",
  "regulation",
}
GENERIC_TERMS = {"carbon fiber", "carbon fibre", "cfrp", "composite", "炭素繊維", "複合材"}
CLUSTER_TERMS = {
  "core_manufacturing": ["carbonization", "pan", "precursor", "stabilization", "炭化", "前駆体"],
  "surface_interface": ["surface treatment", "interface", "adhesion", "sizing", "表面処理"],
  "bundle_prepreg": ["prepreg", "bundle", "tow", "impregnation", "prepreg"],
  "application_pressure_aerospace": ["aerospace", "pressure vessel", "automotive", "航空宇宙", "圧力容器"],
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


def _term_in_text(term: str, text: str) -> bool:
  lowered = term.lower()
  if any(ord(ch) > 127 for ch in term):
    return term in text
  return lowered in text.lower()


def _patent_text(patent: dict[str, Any]) -> str:
  parts = [
    str(patent.get("title") or ""),
    str(patent.get("abstract") or ""),
    str(patent.get("primary_cluster_id") or ""),
    str(patent.get("primary_cluster_name") or ""),
    " ".join(_parse_terms(patent.get("matched_terms"))),
  ]
  return " ".join(parts).lower()


def compute_signal_patent_relevance(signal: dict[str, Any], patent: dict[str, Any]) -> dict[str, Any]:
  company_match = match_company_name(signal.get("company"), patent.get("assignee"))
  terms = _parse_terms(signal.get("technology_terms"))
  patent_text = _patent_text(patent)
  matched_terms = [term for term in terms if _term_in_text(term, patent_text)]
  cluster_id = str(patent.get("primary_cluster_id") or "")
  cluster_terms = CLUSTER_TERMS.get(cluster_id, [])
  cluster_hits = [term for term in terms if any(_term_in_text(ct, term) or _term_in_text(term, ct) for ct in cluster_terms)]

  score = 0.0
  if company_match["matched"]:
    score += 0.35 + company_match["confidence"] * 0.15
  if matched_terms:
    score += min(0.35, 0.1 * len(matched_terms))
  if cluster_hits:
    score += 0.1
  signal_type = str(signal.get("signal_type") or "unknown")
  if signal_type in BUSINESS_SIGNAL_TYPES:
    score += 0.08
  quality = evaluate_web_signal_quality(signal)
  if quality.get("quality_level") in {"high", "medium"}:
    score += 0.08
  elif quality.get("quality_level") in {"low", "unknown"}:
    score -= 0.05

  generic_only = matched_terms and all(term.lower() in GENERIC_TERMS for term in matched_terms)
  if generic_only:
    score -= 0.1

  return {
    "relevance_score": round(max(0.0, min(1.0, score)), 3),
    "matched_company": company_match["matched"],
    "company_match_type": company_match["match_type"],
    "matched_terms": matched_terms,
    "cluster_hits": cluster_hits,
    "generic_only": generic_only,
    "signal_type": signal_type,
    "source_quality_level": quality.get("quality_level"),
    "source_quality_score": quality.get("quality_score"),
  }


def classify_web_signal_relation(relevance: dict[str, Any], signal_quality: dict[str, Any]) -> str:
  if not relevance.get("matched_company") and not relevance.get("matched_terms") and not relevance.get("cluster_hits"):
    return "unrelated"

  signal_type = str(relevance.get("signal_type") or "unknown")
  quality_level = str(signal_quality.get("quality_level") or relevance.get("source_quality_level") or "unknown")
  matched_terms = relevance.get("matched_terms", [])
  matched_company = relevance.get("matched_company", False)

  if (
    matched_company
    and matched_terms
    and quality_level in {"high", "medium"}
    and signal_type in BUSINESS_SIGNAL_TYPES
    and relevance.get("relevance_score", 0) >= 0.45
  ):
    return "business_signal_candidate"

  if matched_company and not matched_terms:
    return "weak_signal"

  if relevance.get("generic_only"):
    return "weak_signal"

  if (
    (matched_terms or relevance.get("cluster_hits"))
    and signal_type in BACKGROUND_SIGNAL_TYPES
  ) or (
    matched_terms and not matched_company
  ):
    return "technology_background_signal"

  if matched_company and matched_terms and relevance.get("relevance_score", 0) >= 0.35:
    return "business_signal_candidate" if signal_type in BUSINESS_SIGNAL_TYPES else "technology_background_signal"

  if matched_company or matched_terms:
    return "weak_signal"

  return "unrelated"


def _build_caveat(relation: str) -> str:
  parts = ["Web signal is a business context candidate, not proof of commercialization."]
  if relation == "business_signal_candidate":
    parts.append("Company-level signal may not correspond to this specific patent.")
  if relation in {"technology_background_signal", "weak_signal"}:
    parts.append("Technology term match is broad and requires human review.")
  return " ".join(parts)


def build_web_signal_links(signals: list[dict[str, Any]], patents: list[dict[str, Any]]) -> list[dict[str, Any]]:
  links: list[dict[str, Any]] = []
  for signal in signals:
    quality = evaluate_web_signal_quality(signal)
    for patent in patents:
      relevance = compute_signal_patent_relevance(signal, patent)
      relation = classify_web_signal_relation(relevance, quality)
      if relation == "unrelated":
        continue
      reason_parts = []
      if relevance.get("matched_company"):
        reason_parts.append(f"company_match={relevance.get('company_match_type')}")
      if relevance.get("matched_terms"):
        reason_parts.append(f"matched_terms={', '.join(relevance['matched_terms'])}")
      reason_parts.append(f"signal_type={signal.get('signal_type')}")
      reason_parts.append(f"quality={quality.get('quality_level')}")

      links.append(
        {
          "signal_id": signal.get("signal_id"),
          "publication_number": patent.get("publication_number"),
          "patent_title": patent.get("title"),
          "assignee": patent.get("assignee"),
          "primary_cluster_id": patent.get("primary_cluster_id"),
          "primary_cluster_name": patent.get("primary_cluster_name"),
          "company": signal.get("company"),
          "normalized_company": signal.get("normalized_company"),
          "signal_type": signal.get("signal_type"),
          "signal_date": signal.get("signal_date"),
          "source_title": signal.get("source_title"),
          "source_name": signal.get("source_name"),
          "display_url": signal.get("display_url") or signal.get("source_url"),
          "source_quality_level": quality.get("quality_level"),
          "source_quality_score": quality.get("quality_score"),
          "relation": relation,
          "relevance_score": relevance.get("relevance_score"),
          "matched_company": relevance.get("matched_company"),
          "matched_terms": relevance.get("matched_terms"),
          "relation_reason": "; ".join(reason_parts),
          "caveat": _build_caveat(relation),
          "recommended_use": quality.get("recommended_use"),
        },
      )
  return links


def summarize_web_signals_by_patent(links: list[dict[str, Any]]) -> list[dict[str, Any]]:
  grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
  for link in links:
    grouped[str(link.get("publication_number"))].append(link)

  summaries: list[dict[str, Any]] = []
  for publication_number, patent_links in grouped.items():
    relation_counter = Counter(link.get("relation") for link in patent_links)
    summaries.append(
      {
        "publication_number": publication_number,
        "patent_title": patent_links[0].get("patent_title"),
        "assignee": patent_links[0].get("assignee"),
        "signal_count": len({link.get("signal_id") for link in patent_links}),
        "business_signal_candidates": relation_counter.get("business_signal_candidate", 0),
        "background_signals": relation_counter.get("technology_background_signal", 0),
        "weak_signals": relation_counter.get("weak_signal", 0),
        "top_links": sorted(patent_links, key=lambda item: item.get("relevance_score", 0), reverse=True)[:5],
      },
    )
  return summaries


def summarize_web_signals_by_company(links: list[dict[str, Any]]) -> list[dict[str, Any]]:
  grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
  for link in links:
    grouped[str(link.get("normalized_company") or link.get("company"))].append(link)

  summaries: list[dict[str, Any]] = []
  for company, company_links in grouped.items():
    if not company:
      continue
    type_counter = Counter(link.get("signal_type") for link in company_links)
    term_counter = Counter(
      term for link in company_links for term in _parse_terms(link.get("matched_terms"))
    )
    summaries.append(
      {
        "normalized_company": company,
        "signal_count": len({link.get("signal_id") for link in company_links}),
        "signal_types": dict(type_counter),
        "linked_patents": len({link.get("publication_number") for link in company_links}),
        "major_technology_terms": [term for term, _ in term_counter.most_common(5)],
      },
    )
  return summaries


def summarize_web_signals_by_cluster(links: list[dict[str, Any]]) -> list[dict[str, Any]]:
  grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
  for link in links:
    grouped[str(link.get("primary_cluster_id") or "unknown")].append(link)

  summaries: list[dict[str, Any]] = []
  for cluster_id, cluster_links in grouped.items():
    summaries.append(
      {
        "primary_cluster_id": cluster_id,
        "primary_cluster_name": cluster_links[0].get("primary_cluster_name") if cluster_links else "",
        "signal_count": len({link.get("signal_id") for link in cluster_links}),
        "companies": sorted({link.get("normalized_company") for link in cluster_links if link.get("normalized_company")}),
        "representative_signals": [
          {
            "source_title": link.get("source_title"),
            "company": link.get("normalized_company"),
            "relation": link.get("relation"),
          }
          for link in sorted(cluster_links, key=lambda item: item.get("relevance_score", 0), reverse=True)[:3]
        ],
      },
    )
  return summaries


def map_web_signals_to_patents(signals: list[dict[str, Any]], patents: list[dict[str, Any]]) -> dict[str, Any]:
  quality_results = [evaluate_web_signal_quality(signal) for signal in signals]
  for signal, quality in zip(signals, quality_results, strict=True):
    signal["source_quality_level"] = quality.get("quality_level")
    signal["source_quality_score"] = quality.get("quality_score")
    signal["warnings"] = list(set(list(signal.get("warnings", [])) + list(quality.get("warnings", []))))

  links = build_web_signal_links(signals, patents)
  relation_counter = Counter(link.get("relation") for link in links)
  quality_counter = Counter(item.get("quality_level") for item in quality_results)

  return {
    "status": "ok",
    "signals_loaded": len(signals),
    "patents_loaded": len(patents),
    "normalized_signals": signals,
    "quality_results": quality_results,
    "links": links,
    "by_patent": summarize_web_signals_by_patent(links),
    "by_company": summarize_web_signals_by_company(links),
    "by_cluster": summarize_web_signals_by_cluster(links),
    "business_signal_candidates": relation_counter.get("business_signal_candidate", 0),
    "background_signals": relation_counter.get("technology_background_signal", 0),
    "weak_signals": relation_counter.get("weak_signal", 0),
    "high_quality_sources": quality_counter.get("high", 0),
    "medium_quality_sources": quality_counter.get("medium", 0),
    "low_quality_sources": quality_counter.get("low", 0),
    "unknown_quality_sources": quality_counter.get("unknown", 0),
    "warnings": [],
    "errors": [],
  }
