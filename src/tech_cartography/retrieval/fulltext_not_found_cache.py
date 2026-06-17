"""Cache for known BigQuery fulltext not_found results — avoid repeat charges."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_NOT_FOUND_CACHE_PATH = "outputs/fulltext_cache/not_found_cache.json"


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_not_found_cache_key(
  publication_number: str,
  scope: str,
  query_strategy: str = "bigquery_publications",
) -> str:
  compact = str(publication_number or "").upper().replace(" ", "").replace("-", "")
  return f"{compact}|{scope}|{query_strategy}"


def load_not_found_cache(path: str | Path = DEFAULT_NOT_FOUND_CACHE_PATH) -> dict[str, Any]:
  cache_path = Path(path)
  if not cache_path.exists():
    return {"entries": {}}
  try:
    data = json.loads(cache_path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "entries" in data:
      return data
    if isinstance(data, dict):
      return {"entries": data}
  except json.JSONDecodeError:
    pass
  return {"entries": {}}


def save_not_found_cache(cache: dict[str, Any], path: str | Path = DEFAULT_NOT_FOUND_CACHE_PATH) -> None:
  cache_path = Path(path)
  cache_path.parent.mkdir(parents=True, exist_ok=True)
  cache_path.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")


def is_known_not_found(
  publication_number: str,
  scope: str,
  query_strategy: str = "bigquery_publications",
  *,
  path: str | Path = DEFAULT_NOT_FOUND_CACHE_PATH,
) -> bool:
  cache = load_not_found_cache(path)
  key = build_not_found_cache_key(publication_number, scope, query_strategy)
  return key in (cache.get("entries") or {})


def mark_not_found(
  publication_number: str,
  scope: str,
  *,
  query_strategy: str = "bigquery_publications",
  probe_status: str = "not_found_in_bigquery",
  matched_variant: str = "",
  notes: str = "",
  path: str | Path = DEFAULT_NOT_FOUND_CACHE_PATH,
) -> dict[str, Any]:
  cache = load_not_found_cache(path)
  entries = cache.setdefault("entries", {})
  key = build_not_found_cache_key(publication_number, scope, query_strategy)
  entry = {
    "publication_number": publication_number,
    "scope": scope,
    "query_strategy": query_strategy,
    "probe_status": probe_status,
    "matched_variant": matched_variant,
    "notes": notes,
    "marked_at": _utc_now_iso(),
  }
  entries[key] = entry
  save_not_found_cache(cache, path)
  return entry


def get_not_found_entry(
  publication_number: str,
  scope: str,
  query_strategy: str = "bigquery_publications",
  *,
  path: str | Path = DEFAULT_NOT_FOUND_CACHE_PATH,
) -> dict[str, Any] | None:
  cache = load_not_found_cache(path)
  key = build_not_found_cache_key(publication_number, scope, query_strategy)
  entry = (cache.get("entries") or {}).get(key)
  return entry if isinstance(entry, dict) else None
