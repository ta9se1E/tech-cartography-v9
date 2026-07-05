"""Integration, deduplication, and ranking for study demo search."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from services_v9.signal_integration import integrate_multi_source_signals

from .relevance_ranking import apply_relevance_ranking, group_signals_by_tier
from .signals import normalize_patent_row, normalize_paper_row, normalize_web_row
from .web_classify import classify_web_activity


def integrate_search_results(
  *,
  patent_rows: Sequence[Mapping[str, Any]],
  paper_rows: Sequence[Mapping[str, Any]],
  web_rows: Sequence[Mapping[str, Any]],
  search_run_id: str,
  query_provenance: Mapping[str, Any],
) -> dict[str, Any]:
  patent_signals = [normalize_patent_row(row, search_run_id=search_run_id, query_provenance=query_provenance) for row in patent_rows]
  paper_signals = [normalize_paper_row(row, search_run_id=search_run_id, query_provenance=query_provenance) for row in paper_rows]
  web_signals = [normalize_web_row(row, search_run_id=search_run_id, query_provenance=query_provenance) for row in web_rows]
  for signal in web_signals:
    meta = dict(signal.get("metadata", {}) or {})
    meta["activity_category"] = classify_web_activity(str(signal.get("title", "") or ""), str(signal.get("summary", "") or ""))
    signal["metadata"] = meta

  patent_signals = _dedupe_patent_family(patent_signals)
  paper_signals = _dedupe_by_key(paper_signals, "source_id")
  web_signals = _dedupe_by_url(web_signals)

  watch_profile = _watch_profile_from_provenance(query_provenance)
  integrated = integrate_multi_source_signals(
    base_signals=[],
    watch_profile=watch_profile,
    patent_rows=[_signal_to_staged(item, "patent") for item in patent_signals],
    paper_rows=[_signal_to_staged(item, "paper") for item in paper_signals],
    web_company_rows=[_signal_to_staged(item, "web_company") for item in web_signals],
  )
  signals = [_normalize_scores(item) for item in list(integrated.get("signals", []) or [])]
  signals = apply_relevance_ranking(signals, query_provenance=query_provenance)
  grouped = group_signals_by_tier(signals)
  return {
    **integrated,
    "signals": signals,
    "patent_count": len(patent_signals),
    "paper_count": len(paper_signals),
    "web_count": len(web_signals),
    "ranked_count": len(signals),
    "relevance_summary": {
      "tier_a": len(grouped["A"]),
      "tier_b": len(grouped["B"]),
      "tier_c": len(grouped["C"]),
      "tier_d": len(grouped["D"]),
    },
  }


def _watch_profile_from_provenance(query_provenance: Mapping[str, Any]) -> dict[str, Any]:
  def _split_terms(value: Any) -> list[str]:
    text = str(value or "").strip()
    if not text:
      return []
    return [part.strip() for part in re.split(r"[,、\n]+", text) if part.strip()]

  keywords_ja = _split_terms(query_provenance.get("keywords_ja", ""))
  keywords_en = _split_terms(query_provenance.get("keywords_en", ""))
  exclude = _split_terms(query_provenance.get("exclude_keywords", ""))
  exact = str(query_provenance.get("exact_phrase", "") or "").strip()
  if exact:
    keywords_en = [*keywords_en, exact]
  return {
    "keywords": {
      "core_en": keywords_en,
      "core_ja": keywords_ja,
      "exclude_en": exclude,
      "exclude_ja": [],
      "material_process_en": [],
      "material_process_ja": [],
      "application_en": [],
      "application_ja": [],
    }
  }


def _signal_to_staged(signal: Mapping[str, Any], source_type: str) -> dict[str, Any]:
  return {
    "source_type": source_type,
    "external_id": signal.get("source_id"),
    "title": signal.get("title"),
    "abstract": signal.get("summary"),
    "source_url": signal.get("url"),
    "published_date": signal.get("published_at"),
    "organization": signal.get("organization"),
    "country": signal.get("country"),
    "language": signal.get("language"),
    "family_id": signal.get("family_id"),
    "relevance_score": signal.get("relevance_score"),
    "metadata": dict(signal.get("metadata", {}) or {}),
  }


def _dedupe_by_key(signals: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
  seen: set[str] = set()
  out: list[dict[str, Any]] = []
  for item in signals:
    token = str(item.get(key, "") or "")
    if token and token in seen:
      continue
    if token:
      seen.add(token)
    out.append(item)
  return out


def _dedupe_patent_family(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
  seen: set[str] = set()
  out: list[dict[str, Any]] = []
  for item in signals:
    family = str(item.get("family_id", "") or item.get("source_id", "") or "")
    if family and family in seen:
      continue
    if family:
      seen.add(family)
    out.append(item)
  return out


def _dedupe_by_url(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
  seen: set[str] = set()
  out: list[dict[str, Any]] = []
  for item in signals:
    url = _normalize_url(str(item.get("url", "") or ""))
    if url and url in seen:
      continue
    if url:
      seen.add(url)
    out.append(item)
  return out


def _normalize_url(url: str) -> str:
  parsed = urlparse(url.strip())
  host = (parsed.netloc or "").lower()
  path = re.sub(r"/+", "/", parsed.path or "/")
  return f"{host}{path.rstrip('/')}"


def _normalize_scores(signal: Mapping[str, Any]) -> dict[str, Any]:
  item = dict(signal)
  for key in ("relevance_score", "source_score", "final_score"):
    try:
      value = float(item.get(key, 0) or 0)
    except (TypeError, ValueError):
      value = 0.0
    item[key] = max(0.0, min(value, 1.0))
  return item
