"""Canonical run metrics for Study Demo active search run display."""

from __future__ import annotations

from typing import Any, Mapping

UNKNOWN_METRIC_LABEL = "未記録"


def format_unknown_metric(value: object) -> str:
  if value is None:
    return UNKNOWN_METRIC_LABEL
  if isinstance(value, str) and not value.strip():
    return UNKNOWN_METRIC_LABEL
  return str(value)


def _provider_status_entry(provider_status: Mapping[str, Any], name: str) -> dict[str, Any]:
  return dict(provider_status.get(name, {}) or {})


def derive_run_success_rate(*, provider_success_count: int | None, provider_total: int | None) -> float | None:
  if provider_success_count is None or provider_total is None or provider_total <= 0:
    return None
  return round((provider_success_count / provider_total) * 100.0, 2)


def build_canonical_run_metrics(
  *,
  context: Mapping[str, Any],
  resolved: Mapping[str, Any] | None = None,
  provider_status: Mapping[str, Any] | None = None,
  usage_metrics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
  ctx = dict(context or {})
  res = dict(resolved or {})
  status = dict(provider_status or {})
  usage = dict(usage_metrics or {})

  provider_counts = {
    "patent": _first_int(
      res.get("integrated_source_counts", {}).get("patent") if isinstance(res.get("integrated_source_counts"), dict) else None,
      ctx.get("provider_counts", {}).get("patent") if isinstance(ctx.get("provider_counts"), dict) else None,
      res.get("stored_artifact_counts", {}).get("patent") if isinstance(res.get("stored_artifact_counts"), dict) else None,
    ),
    "paper": _first_int(
      res.get("integrated_source_counts", {}).get("paper") if isinstance(res.get("integrated_source_counts"), dict) else None,
      ctx.get("provider_counts", {}).get("paper") if isinstance(ctx.get("provider_counts"), dict) else None,
      res.get("stored_artifact_counts", {}).get("paper") if isinstance(res.get("stored_artifact_counts"), dict) else None,
    ),
    "web": _first_int(
      res.get("integrated_source_counts", {}).get("web") if isinstance(res.get("integrated_source_counts"), dict) else None,
      ctx.get("provider_counts", {}).get("web") if isinstance(ctx.get("provider_counts"), dict) else None,
      res.get("stored_artifact_counts", {}).get("web") if isinstance(res.get("stored_artifact_counts"), dict) else None,
    ),
  }

  provider_success = {}
  for name in ("patent", "paper", "web"):
    entry = _provider_status_entry(status, name)
    state = str(entry.get("status", "") or "").lower()
    count = _first_int(entry.get("result_count"), entry.get("returned_count"), entry.get("count"), provider_counts.get(name))
    provider_success[name] = {
      "status": state or None,
      "count": count,
      "success": state == "success",
    }

  success_count = sum(1 for item in provider_success.values() if item.get("success"))
  success_rate = derive_run_success_rate(provider_success_count=success_count, provider_total=3)

  integrated_count = _first_int(
    res.get("integrated_ranked_count"),
    ctx.get("ranked_count"),
  )
  resolved_tiers = dict(res.get("tier_counts", {}) or {})
  ctx_tier_counts = dict(ctx.get("tier_counts", {}) or {})
  resolved_tier_sum = sum(int(resolved_tiers.get(key, 0) or 0) for key in ("A", "B", "C", "D"))
  ctx_tier_sum = sum(int(ctx_tier_counts.get(key, 0) or 0) for key in ("A", "B", "C", "D"))
  if (
    integrated_count
    and ctx_tier_sum == integrated_count
    and resolved_tiers != ctx_tier_counts
  ):
    tier_counts = ctx_tier_counts
    tier_sum = ctx_tier_sum
  elif integrated_count and resolved_tier_sum == integrated_count:
    tier_counts = resolved_tiers
    tier_sum = resolved_tier_sum
  else:
    tier_counts = resolved_tiers or ctx_tier_counts
    tier_sum = sum(int(tier_counts.get(key, 0) or 0) for key in ("A", "B", "C", "D"))

  saved_count = _first_int(
    integrated_count,
    sum(provider_counts.values()) if all(v is not None for v in provider_counts.values()) else None,
  )

  raw_counts = dict(res.get("raw_provider_counts", {}) or {})
  stored_counts = dict(res.get("stored_artifact_counts", {}) or {})

  metrics = {
    "active_search_run_id": str(ctx.get("active_search_run_id", "") or res.get("search_run_id", "")),
    "run_origin": str(ctx.get("run_origin", "") or ""),
    "context_type": str(ctx.get("context_type", "") or ""),
    "lineage_status": str(ctx.get("lineage_status", "") or ""),
    "provider_counts": provider_counts,
    "provider_success": provider_success,
    "provider_success_count": success_count,
    "provider_success_rate": success_rate,
    "saved_count": saved_count,
    "integrated_count": integrated_count,
    "ranked_count": integrated_count,
    "tier_counts": tier_counts,
    "tier_sum": tier_sum,
    "active_retrieval_sources": [name for name, item in provider_success.items() if item.get("success")],
    "raw_provider_counts": raw_counts,
    "stored_artifact_counts": stored_counts,
    "search_run_count": 1 if ctx.get("active_search_run_id") else None,
    "executed_at": ctx.get("selected_at"),
    "usage_summary": {
      key: dict(value)
      for key, value in usage.items()
      if isinstance(value, dict)
    },
  }
  metrics["metric_sources"] = _derive_metric_sources(metrics, res)
  metrics["inconsistencies"] = validate_run_metric_consistency(metrics)
  return metrics


def _derive_metric_sources(metrics: Mapping[str, Any], resolved: Mapping[str, Any]) -> dict[str, str]:
  sources: dict[str, str] = {}
  if resolved.get("stored_artifact_counts"):
    sources["provider_counts"] = "derived_from_provider_saved_counts"
  if metrics.get("integrated_count") is not None:
    sources["integrated_count"] = "integrated_signals"
  if metrics.get("tier_counts"):
    sources["tier_counts"] = "integrated_signals"
  return sources


def validate_run_metric_consistency(metrics: Mapping[str, Any]) -> list[str]:
  errors: list[str] = []
  provider_counts = dict(metrics.get("provider_counts", {}) or {})
  integrated = metrics.get("integrated_count")
  ranked = metrics.get("ranked_count")
  tier_sum = int(metrics.get("tier_sum", 0) or 0)
  saved = metrics.get("saved_count")

  if integrated is not None and ranked is not None and integrated != ranked:
    errors.append("integrated_ranked_mismatch")

  if integrated is not None and tier_sum and tier_sum != integrated:
    errors.append("tier_integrated_mismatch")

  if saved is not None and integrated is not None and saved != integrated:
    if all(provider_counts.get(k) is not None for k in ("patent", "paper", "web")):
      provider_total = sum(int(provider_counts[k] or 0) for k in ("patent", "paper", "web"))
      if provider_total != integrated:
        errors.append("provider_total_integrated_mismatch")

  for name in ("patent", "paper", "web"):
    item = dict(dict(metrics.get("provider_success", {}) or {}).get(name, {}) or {})
    if item.get("success") and item.get("count") in (None, 0):
      errors.append(f"{name}_success_without_count")

  return errors


def build_active_run_source_rows(metrics: Mapping[str, Any]) -> list[dict[str, Any]]:
  provider_counts = dict(metrics.get("provider_counts", {}) or {})
  provider_success = dict(metrics.get("provider_success", {}) or {})
  executed_at = format_unknown_metric(metrics.get("executed_at"))
  rows = []
  for source_type in ("patent", "paper", "web"):
    item = dict(provider_success.get(source_type, {}) or {})
    count = provider_counts.get(source_type)
    rows.append(
      {
        "enabled": True,
        "source_type": source_type,
        "mode": "loaded" if item.get("success") else "off",
        "top_n": int(count or 0),
        "last_updated": executed_at,
        "note": "保存済み検索結果を表示しています。ページ表示では外部APIを実行しません。",
        "provider_status": item.get("status"),
        "result_count": count,
      }
    )
  return rows


def build_active_run_operation_rows(metrics: Mapping[str, Any]) -> list[dict[str, str]]:
  provider_success = dict(metrics.get("provider_success", {}) or {})
  rows = []
  for label, key in (("patent", "patent"), ("paper", "paper"), ("web", "web")):
    item = dict(provider_success.get(key, {}) or {})
    mode = "loaded" if item.get("success") else "off"
    rows.append({"label": label, "mode": mode})
  rows.extend(
    [
      {"label": "BigQuery", "mode": "off"},
      {"label": "OpenAlex", "mode": "off"},
      {"label": "Web検索", "mode": "off"},
      {"label": "メール配信", "mode": "off"},
    ]
  )
  return rows


def resolve_active_source_label(context: Mapping[str, Any]) -> str:
  run_origin = str(context.get("run_origin", "") or "")
  context_type = str(context.get("context_type", "") or "")
  if run_origin == "watch_profile" or context_type == "watch_profile":
    return "保存済み標準検索run"
  if run_origin == "temporary_search" or context_type == "temporary_search":
    return "一時検索run"
  return "保存済み検索run"


def resolve_creation_path_label(context: Mapping[str, Any]) -> str:
  run_origin = str(context.get("run_origin", "") or "")
  if run_origin == "watch_profile":
    return "標準監視テーマ"
  if run_origin == "temporary_search":
    return "一時キーワード検索"
  return run_origin or "不明"


def _first_int(*values: object) -> int | None:
  for value in values:
    if value is None:
      continue
    try:
      return int(value)
    except (TypeError, ValueError):
      continue
  return None


__all__ = [
  "UNKNOWN_METRIC_LABEL",
  "build_active_run_operation_rows",
  "build_active_run_source_rows",
  "build_canonical_run_metrics",
  "derive_run_success_rate",
  "format_unknown_metric",
  "resolve_active_source_label",
  "resolve_creation_path_label",
  "validate_run_metric_consistency",
]
