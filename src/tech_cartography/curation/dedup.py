"""Patent record deduplication for multi-query retrieval."""

from __future__ import annotations

import re
from typing import Any


def normalize_publication_number(publication_number: str) -> str:
  compact = re.sub(r"[\s\-]+", "", str(publication_number or "").upper())
  return compact


def _as_list(value: Any) -> list[str]:
  if value is None:
    return []
  if isinstance(value, list):
    return [str(item) for item in value if str(item).strip()]
  text = str(value).strip()
  if not text:
    return []
  if ";" in text:
    return [part.strip() for part in text.split(";") if part.strip()]
  return [text]


def _dedupe_preserve(items: list[str]) -> list[str]:
  seen: set[str] = set()
  result: list[str] = []
  for item in items:
    key = item.lower()
    if key in seen:
      continue
    seen.add(key)
    result.append(item)
  return result


def merge_search_intents_for_duplicate(records: list[dict]) -> dict[str, list[str]]:
  intents: list[str] = []
  plan_ids: list[str] = []
  matched_terms: list[str] = []
  for record in records:
    intents.extend(_as_list(record.get("search_intent")))
    intents.extend(_as_list(record.get("search_intents")))
    plan_ids.extend(_as_list(record.get("query_plan_id")))
    plan_ids.extend(_as_list(record.get("query_plan_ids")))
    matched_terms.extend(_as_list(record.get("matched_terms")))
  return {
    "search_intents": _dedupe_preserve(intents),
    "query_plan_ids": _dedupe_preserve(plan_ids),
    "matched_terms": _dedupe_preserve(matched_terms),
  }


def deduplicate_patent_records(records: list[dict]) -> list[dict]:
  """Deduplicate records by publication_number and merge intent metadata."""
  grouped: dict[str, list[dict]] = {}
  order: list[str] = []

  for record in records:
    pub = normalize_publication_number(record.get("publication_number", ""))
    if not pub:
      continue
    if pub not in grouped:
      grouped[pub] = []
      order.append(pub)
    grouped[pub].append(record)

  deduped: list[dict] = []
  for pub in order:
    group = grouped[pub]
    primary = dict(group[0])
    merged = merge_search_intents_for_duplicate(group)

    primary["publication_number"] = primary.get("publication_number") or pub
    primary["search_intents"] = merged["search_intents"]
    primary["query_plan_ids"] = merged["query_plan_ids"]
    primary["matched_terms"] = merged["matched_terms"]
    primary.pop("search_intent", None)
    primary.pop("query_plan_id", None)
    primary.setdefault("source_type", "bigquery_lightweight")
    primary.setdefault("evidence_level", "metadata_only")
    primary.setdefault("claims_source", "not_fetched")
    primary.setdefault("description_source", "not_fetched")
    deduped.append(primary)

  return deduped
