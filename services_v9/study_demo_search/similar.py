"""Similar patent suggestions within retrieved patent set."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Mapping, Sequence

_TOKEN = re.compile(r"[A-Za-z0-9\u3040-\u30ff\u3400-\u9fff]{2,}")


def _vectorize(text: str) -> Counter[str]:
  return Counter(_TOKEN.findall(text.lower()))


def _cosine(a: Counter[str], b: Counter[str]) -> float:
  if not a or not b:
    return 0.0
  common = set(a) & set(b)
  numerator = sum(a[token] * b[token] for token in common)
  denom_a = math.sqrt(sum(value * value for value in a.values()))
  denom_b = math.sqrt(sum(value * value for value in b.values()))
  if denom_a == 0 or denom_b == 0:
    return 0.0
  return numerator / (denom_a * denom_b)


def build_similar_patents(
  signals: Sequence[Mapping[str, Any]],
  *,
  seed_patent: str = "",
  limit: int = 10,
) -> dict[str, Any]:
  patents = [item for item in signals if str(item.get("source_type", "")) == "patent"]
  if not seed_patent or not patents:
    return {"seed_patent": seed_patent, "items": [], "disclaimer": "Not an infringement/FTO/identity judgment."}

  seed = next((item for item in patents if str(item.get("source_id", "")) == seed_patent), None)
  if seed is None:
    return {"seed_patent": seed_patent, "items": [], "disclaimer": "Seed patent not found in current results."}

  seed_vec = _vectorize(f"{seed.get('title', '')} {seed.get('summary', '')}")
  seed_family = str(seed.get("family_id", "") or "")
  ranked: list[dict[str, Any]] = []
  for item in patents:
    pub = str(item.get("source_id", "") or "")
    if pub == seed_patent:
      continue
    if seed_family and str(item.get("family_id", "") or "") == seed_family:
      continue
    vec = _vectorize(f"{item.get('title', '')} {item.get('summary', '')}")
    score = _cosine(seed_vec, vec)
    common = sorted(set(_TOKEN.findall(str(seed.get("title", "")).lower())) & set(_TOKEN.findall(str(item.get("title", "")).lower())))
    ranked.append(
      {
        "publication_number": pub,
        "title": item.get("title"),
        "similarity_score": round(score, 4),
        "common_keywords": common[:10],
        "google_patents_url": f"https://patents.google.com/patent/{pub}",
      }
    )
  ranked.sort(key=lambda row: row["similarity_score"], reverse=True)
  return {
    "seed_patent": seed_patent,
    "items": ranked[:limit],
    "disclaimer": "Similarity ranking only; not an infringement/FTO/identity judgment.",
  }
