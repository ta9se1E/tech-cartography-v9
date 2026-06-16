"""Noise detection for carbon fiber patent candidates."""

from __future__ import annotations

from typing import Any

from tech_cartography.curation.dedup import _as_list

# (pattern, weight, category)
NOISE_PATTERNS: list[tuple[str, float, str]] = [
  ("display apparatus", 0.50, "display_or_electronics_noise"),
  ("display device", 0.48, "display_or_electronics_noise"),
  ("electronic device", 0.40, "display_or_electronics_noise"),
  ("semiconductor", 0.45, "display_or_electronics_noise"),
  ("thin film", 0.30, "display_or_electronics_noise"),
  ("nanoparticle sensor", 0.50, "sensor_membrane_noise"),
  ("nanofibrous membrane", 0.48, "sensor_membrane_noise"),
  ("3d printing", 0.45, "carbon_or_graphite_not_fiber"),
  ("moulded articles from carbon or graphite", 0.50, "carbon_or_graphite_not_fiber"),
  ("molded articles from carbon or graphite", 0.50, "carbon_or_graphite_not_fiber"),
  ("battery electrode", 0.40, "battery_electrode_noise"),
  ("fuel cell electrode", 0.35, "battery_electrode_noise"),
  ("electrode", 0.25, "battery_electrode_noise"),
  ("battery", 0.30, "battery_electrode_noise"),
  ("lithium", 0.35, "battery_electrode_noise"),
  ("graphite electrode", 0.45, "battery_electrode_noise"),
  ("graphene", 0.45, "graphene_cnt_noise"),
  ("carbon nanotube", 0.45, "graphene_cnt_noise"),
  (" cnt ", 0.40, "graphene_cnt_noise"),
  ("activated carbon", 0.45, "activated_carbon_noise"),
  ("carbon black", 0.40, "activated_carbon_noise"),
  ("porous carbon sheet", 0.30, "activated_carbon_noise"),
  ("dye", 0.25, "unrelated_device"),
  ("heavy oil", 0.35, "unrelated_device"),
  ("gasification", 0.30, "unrelated_device"),
  ("recycling", 0.18, "recycling_only_low_priority"),
  ("composite resin only", 0.22, "generic_composite_only"),
]

MITIGATION_TERMS = [
  "pressure vessel",
  "aerospace",
  "prepreg",
  "composite",
  "carbon fiber",
  "carbon fibre",
  "polyacrylonitrile",
  "pan",
  "precursor fiber",
  "carbonization",
  "carbonisation",
  "sizing",
  "tow",
]

LOW_PRIORITY_TERMS = [
  "recycling",
  "resin",
  "composite",
]

CORE_FIBER_TERMS = [
  "carbon fiber",
  "carbon fibre",
  "polyacrylonitrile",
  "pan",
  "precursor",
  "carbonization",
  "carbonisation",
  "prepreg",
  "tow",
]

UNKNOWN_ASSIGNEE_VALUES = {"", "unknown", "nan", "n/a", "none", "null"}


def _combined_text(record: dict[str, Any]) -> str:
  matched = " ".join(_as_list(record.get("matched_terms")))
  return " ".join(
    str(record.get(field, "") or "")
    for field in ("title", "abstract", "assignee", "cpc_codes", "ipc_codes")
  ).lower() + " " + matched.lower()


def _is_unknown_assignee(record: dict[str, Any]) -> bool:
  assignee = str(record.get("assignee", "") or "").strip().lower()
  return assignee in UNKNOWN_ASSIGNEE_VALUES


def detect_noise_categories(record: dict[str, Any]) -> list[str]:
  text = _combined_text(record)
  categories: list[str] = []
  for pattern, _, category in NOISE_PATTERNS:
    if pattern in text and category not in categories:
      categories.append(category)
  if _is_unknown_assignee(record):
    categories.append("unknown_assignee_penalty")
  return categories


def detect_noise_signals(record: dict[str, Any]) -> list[str]:
  text = _combined_text(record)
  signals: list[str] = []
  for pattern, _, _ in NOISE_PATTERNS:
    if pattern in text:
      signals.append(pattern)
  return signals


def compute_noise_score(record: dict[str, Any]) -> float:
  text = _combined_text(record)
  score = 0.0
  for pattern, weight, _ in NOISE_PATTERNS:
    if pattern in text:
      score += weight

  if any(term in text for term in MITIGATION_TERMS):
    mitigation_hits = sum(1 for term in MITIGATION_TERMS if term in text)
    factor = 0.35 if mitigation_hits >= 2 else 0.55
    score *= factor

  if any(term in text for term in CORE_FIBER_TERMS):
    score *= 0.65

  if "fuel cell" in text and any(term in text for term in ("carbon fiber", "composite", "prepreg")):
    score = min(score, 0.40)

  if any(term in text for term in LOW_PRIORITY_TERMS) and not any(
    term in text for term in CORE_FIBER_TERMS
  ):
    score = max(score, 0.15)

  if _is_unknown_assignee(record):
    score += 0.12

  return round(min(score, 1.0), 4)


def is_likely_noise(record: dict[str, Any], threshold: float = 0.55) -> bool:
  return compute_noise_score(record) >= threshold
