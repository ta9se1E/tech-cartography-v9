"""Noise detection for carbon fiber patent candidates."""

from __future__ import annotations

import re
from typing import Any

from tech_cartography.curation.dedup import _as_list

NOISE_PATTERNS: list[tuple[str, float]] = [
  ("battery electrode", 0.35),
  ("fuel cell electrode", 0.25),
  ("activated carbon", 0.45),
  ("carbon black", 0.40),
  ("graphene", 0.40),
  ("carbon nanotube", 0.40),
  ("porous carbon sheet", 0.30),
  ("dye", 0.25),
  ("thin film", 0.20),
  ("heavy oil", 0.35),
  ("gasification", 0.30),
]

MITIGATION_TERMS = [
  "pressure vessel",
  "aerospace",
  "prepreg",
  "composite",
  "carbon fiber",
  "carbon fibre",
]


def _combined_text(record: dict[str, Any]) -> str:
  return " ".join(
    str(record.get(field, "") or "")
    for field in ("title", "abstract", "assignee", "cpc_codes", "ipc_codes")
  ).lower()


def detect_noise_signals(record: dict[str, Any]) -> list[str]:
  text = _combined_text(record)
  signals: list[str] = []
  for pattern, _ in NOISE_PATTERNS:
    if pattern in text:
      signals.append(pattern)
  return signals


def compute_noise_score(record: dict[str, Any]) -> float:
  text = _combined_text(record)
  score = 0.0
  for pattern, weight in NOISE_PATTERNS:
    if pattern in text:
      score += weight

  if any(term in text for term in MITIGATION_TERMS):
    score *= 0.5

  if "fuel cell" in text and any(term in text for term in ("carbon fiber", "composite", "prepreg")):
    score = min(score, 0.45)

  return round(min(score, 1.0), 4)


def is_likely_noise(record: dict[str, Any], threshold: float = 0.65) -> bool:
  return compute_noise_score(record) >= threshold
