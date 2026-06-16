"""JSON cache for OpenAlex search results."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def normalize_query_for_cache(query: str) -> str:
  normalized = re.sub(r"\s+", " ", str(query or "").strip().lower())
  return normalized


def get_openalex_cache_key(query: str, max_results: int = 10) -> str:
  normalized = normalize_query_for_cache(query)
  digest = hashlib.sha256(f"{normalized}|{max_results}".encode("utf-8")).hexdigest()[:16]
  slug = re.sub(r"[^\w]+", "_", normalized)[:48].strip("_") or "query"
  return f"{slug}_{digest}"


def get_openalex_cache_path(query: str, cache_dir: str, max_results: int = 10) -> str:
  return str(Path(cache_dir) / f"{get_openalex_cache_key(query, max_results)}.json")


def load_openalex_cache(query: str, cache_dir: str, max_results: int = 10) -> dict | None:
  path = Path(get_openalex_cache_path(query, cache_dir, max_results))
  if not path.exists():
    return None
  with path.open(encoding="utf-8") as handle:
    return json.load(handle)


def save_openalex_cache(
  query: str,
  result: dict[str, Any],
  cache_dir: str,
  max_results: int = 10,
) -> str:
  path = Path(get_openalex_cache_path(query, cache_dir, max_results))
  path.parent.mkdir(parents=True, exist_ok=True)
  payload = {
    "retrieved_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    "query": query,
    "max_results": max_results,
    "works": result.get("works", result.get("results", [])),
    "meta": result.get("meta", {}),
    "status": result.get("status", "ok"),
  }
  with path.open("w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, ensure_ascii=False)
  return str(path)


def openalex_cache_status(query: str, cache_dir: str, max_results: int = 10) -> str:
  path = Path(get_openalex_cache_path(query, cache_dir, max_results))
  return "cache_hit" if path.exists() else "cache_miss"
