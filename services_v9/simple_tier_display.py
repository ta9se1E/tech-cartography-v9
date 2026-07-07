"""Simple Mode tier presentation labels."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

TIER_PRIORITY = "priority"
TIER_WATCH = "watch"
TIER_REFERENCE_LOW = "reference_low"

TIER_GROUP_BY_LETTER = {
  "A": TIER_PRIORITY,
  "B": TIER_WATCH,
  "C": TIER_REFERENCE_LOW,
  "D": TIER_REFERENCE_LOW,
}

TIER_LABELS_JA = {
  "A": "優先確認",
  "B": "継続監視",
  "C": "背景資料",
  "D": "低優先",
}


def tier_group_for_letter(tier: str) -> str:
  return TIER_GROUP_BY_LETTER.get(str(tier or "").upper(), TIER_REFERENCE_LOW)


def tier_display_label_ja(tier: str) -> str:
  return TIER_LABELS_JA.get(str(tier or "").upper(), "低優先")


def classify_signals_by_tier_group(signals: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
  groups = {TIER_PRIORITY: [], TIER_WATCH: [], TIER_REFERENCE_LOW: []}
  for item in signals:
    tier = str(item.get("relevance_tier", "") or item.get("study_demo", {}).get("relevance_tier", "") or "D")
    groups[tier_group_for_letter(tier)].append(dict(item))
  return groups


def count_tier_groups(signals: Sequence[Mapping[str, Any]]) -> dict[str, int]:
  groups = classify_signals_by_tier_group(signals)
  return {key: len(value) for key, value in groups.items()}


__all__ = [
  "TIER_LABELS_JA",
  "TIER_PRIORITY",
  "TIER_REFERENCE_LOW",
  "TIER_WATCH",
  "classify_signals_by_tier_group",
  "count_tier_groups",
  "tier_display_label_ja",
  "tier_group_for_letter",
]
