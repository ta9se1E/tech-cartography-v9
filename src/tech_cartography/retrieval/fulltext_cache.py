"""JSON cache for full text retrieval results."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def get_cache_key(publication_number: str, scope: str | None = None) -> str:
  compact = re.sub(r"[^\w]+", "_", str(publication_number or "").upper())
  base = compact or "unknown"
  if scope:
    return f"{base}_{str(scope).lower()}"
  return base


def get_cache_path(publication_number: str, cache_dir: str, scope: str | None = None) -> str:
  return str(Path(cache_dir) / f"{get_cache_key(publication_number, scope)}.json")


def cache_status(publication_number: str, cache_dir: str, scope: str | None = None) -> str:
  path = Path(get_cache_path(publication_number, cache_dir, scope))
  return "cache_hit" if path.exists() else "cache_miss"


def load_fulltext_from_cache(
  publication_number: str,
  cache_dir: str,
  scope: str | None = None,
) -> dict | None:
  path = Path(get_cache_path(publication_number, cache_dir, scope))
  if not path.exists() and scope:
    path = Path(get_cache_path(publication_number, cache_dir, None))
  if not path.exists():
    return None
  with path.open(encoding="utf-8") as handle:
    return json.load(handle)


def save_fulltext_to_cache(record: dict, cache_dir: str, scope: str | None = None) -> str:
  scope = scope or record.get("fulltext_scope")
  path = Path(get_cache_path(record.get("publication_number", ""), cache_dir, scope))
  path.parent.mkdir(parents=True, exist_ok=True)
  payload = dict(record)
  payload["retrieved_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
  with path.open("w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, ensure_ascii=False)
  return str(path)
