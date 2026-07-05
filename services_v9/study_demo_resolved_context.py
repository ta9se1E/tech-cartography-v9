"""Resolve display counts for Study Demo active analysis context from artifacts."""

from __future__ import annotations

import re
from typing import Any, Mapping

from services_v9.study_demo_search.relevance_ranking import TIER_A, TIER_B, TIER_C, TIER_D
from services_v9.study_demo_search.storage import build_search_result_from_artifacts, load_search_run

_TIER_ALIASES = {
  "A": TIER_A,
  "B": TIER_B,
  "C": TIER_C,
  "D": TIER_D,
  "TIER A": TIER_A,
  "TIER B": TIER_B,
  "TIER C": TIER_C,
  "TIER D": TIER_D,
  "TIER_A": TIER_A,
  "TIER_B": TIER_B,
  "TIER_C": TIER_C,
  "TIER_D": TIER_D,
}


def normalize_relevance_tier(value: object) -> str | None:
  raw = str(value or "").strip()
  if not raw:
    return None
  upper = raw.upper()
  if upper in _TIER_ALIASES:
    return _TIER_ALIASES[upper]
  match = re.fullmatch(r"TIER[\s_-]*([ABCD])", upper)
  if match:
    return match.group(1)
  if upper in {"A", "B", "C", "D"}:
    return upper
  return None


def count_tiers_from_signals(signals: list[Mapping[str, Any]]) -> dict[str, Any]:
  tier_counts = {TIER_A: 0, TIER_B: 0, TIER_C: 0, TIER_D: 0}
  unknown_tier_count = 0
  for signal in signals:
    tier = normalize_relevance_tier(signal.get("relevance_tier"))
    if tier in tier_counts:
      tier_counts[tier] += 1
    else:
      unknown_tier_count += 1
  return {
    "tier_counts": tier_counts,
    "unknown_tier_count": unknown_tier_count,
  }


def _artifact_row_count(payload: Mapping[str, Any]) -> int:
  if not payload:
    return 0
  for key in ("rows", "results", "items", "signals"):
    rows = payload.get(key)
    if isinstance(rows, list):
      return len(rows)
  return 0


def _provider_return_count(name: str, artifacts: Mapping[str, Any]) -> int | None:
  usage = dict(artifacts.get("usage_metrics.json", {}) or {})
  usage_entry = dict(usage.get(name, {}) or {}) if isinstance(usage.get(name), dict) else {}
  for field in ("result_count", "returned_count", "count"):
    if usage_entry.get(field) is not None:
      return int(usage_entry.get(field) or 0)

  status = dict(dict(artifacts.get("provider_status.json", {}) or {}).get(name, {}) or {})
  for field in ("result_count", "returned_count", "count"):
    if status.get(field) is not None:
      return int(status.get(field) or 0)
  return None


def _integrated_source_counts(signals: list[Mapping[str, Any]]) -> dict[str, int]:
  counts = {"patent": 0, "paper": 0, "web": 0}
  for signal in signals:
    source_type = str(signal.get("source_type", "") or "")
    if source_type == "patent":
      counts["patent"] += 1
    elif source_type == "paper":
      counts["paper"] += 1
    elif source_type in {"web", "web_company"}:
      counts["web"] += 1
  return counts


def resolve_active_run_counts(
  context: Mapping[str, Any],
  *,
  storage_client: Any | None = None,
  loaded_bundle: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
  loaded = dict(loaded_bundle or load_search_run(str(context.get("active_search_run_id", "") or ""), storage_client=storage_client))
  artifacts = dict(loaded.get("artifacts", {}) or {})
  search_result = build_search_result_from_artifacts(loaded)
  integrated = dict(search_result.get("integrated_signals", {}) or {})
  signals = list(integrated.get("signals", []) or [])

  tier_info = count_tiers_from_signals(signals)
  tier_counts = dict(tier_info["tier_counts"])
  unknown_tier_count = int(tier_info["unknown_tier_count"])
  integrated_ranked_count = int(integrated.get("ranked_count", len(signals)) or len(signals))
  integrated_source_counts = _integrated_source_counts(signals)

  raw_provider_counts: dict[str, int | None] = {
    "patent": _provider_return_count("patent", artifacts),
    "paper": _provider_return_count("paper", artifacts),
    "web": _provider_return_count("web", artifacts),
  }
  stored_artifact_counts = {
    "patent": _artifact_row_count(dict(artifacts.get("patent_results.json", {}) or {})),
    "paper": _artifact_row_count(dict(artifacts.get("paper_results.json", {}) or {})),
    "web": _artifact_row_count(dict(artifacts.get("web_results.json", {}) or {})),
  }

  tier_total = sum(tier_counts.values())
  stored_tier_counts = dict(context.get("tier_counts", {}) or {})
  stored_provider_counts = dict(context.get("provider_counts", {}) or {})

  count_validation_status = "ok"
  messages: list[str] = []
  if unknown_tier_count:
    count_validation_status = "warning"
    messages.append(f"不明Tier: {unknown_tier_count}件")
  if tier_total != integrated_ranked_count:
    count_validation_status = "mismatch"
    messages.append(f"Tier合計({tier_total})と統合件数({integrated_ranked_count})が一致しません")
  if any(stored_tier_counts.values()) and stored_tier_counts != tier_counts:
    if count_validation_status == "ok":
      count_validation_status = "stored_mismatch"
    messages.append("保存済みtier_countsと再計算値が一致しません")

  raw_total = sum(value for value in raw_provider_counts.values() if value is not None)
  stored_total = sum(stored_artifact_counts.values())
  if raw_total and integrated_ranked_count and raw_total != integrated_ranked_count:
    messages.append("取得件数と統合後件数が一致しない場合、重複除去・family統合等の可能性があります")

  return {
    "search_run_id": str(context.get("active_search_run_id", "") or loaded.get("search_run_id", "")),
    "theme": str(context.get("theme", "") or dict(artifacts.get("search_request.json", {}) or {}).get("theme", "")),
    "raw_provider_counts": raw_provider_counts,
    "stored_artifact_counts": stored_artifact_counts,
    "integrated_ranked_count": integrated_ranked_count,
    "integrated_source_counts": integrated_source_counts,
    "tier_counts": tier_counts,
    "unknown_tier_count": unknown_tier_count,
    "count_validation_status": count_validation_status,
    "count_validation_message": " / ".join(messages),
    "stored_tier_counts": stored_tier_counts,
    "stored_provider_counts": stored_provider_counts,
    "selected_at": context.get("selected_at"),
  }


def build_resolved_context_cache_patch(resolved: Mapping[str, Any]) -> dict[str, Any]:
  source_counts = dict(resolved.get("integrated_source_counts", {}) or {})
  tier_counts = dict(resolved.get("tier_counts", {}) or {})
  return {
    "provider_counts": {
      "patent": int(source_counts.get("patent", 0) or 0),
      "paper": int(source_counts.get("paper", 0) or 0),
      "web": int(source_counts.get("web", 0) or 0),
    },
    "tier_counts": {
      "A": int(tier_counts.get("A", 0) or 0),
      "B": int(tier_counts.get("B", 0) or 0),
      "C": int(tier_counts.get("C", 0) or 0),
      "D": int(tier_counts.get("D", 0) or 0),
    },
    "ranked_count": int(resolved.get("integrated_ranked_count", 0) or 0),
  }
