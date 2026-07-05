"""Usage metrics aggregation for study demo search."""

from __future__ import annotations

from typing import Any, Mapping


def init_usage_metrics() -> dict[str, Any]:
  return {
    "patent": {
      "dry_run_count": 0,
      "execution_count": 0,
      "estimated_bytes": 0,
      "processed_bytes": 0,
      "billed_bytes": 0,
      "cache_hit_count": 0,
      "reference_cost_usd": 0.0,
    },
    "paper": {
      "request_count": 0,
      "result_count": 0,
      "pagination_count": 0,
      "error_count": 0,
      "response_time_ms": 0,
    },
    "web": {
      "request_count": 0,
      "basic_count": 0,
      "advanced_count": 0,
      "total_credits": None,
      "result_count": 0,
      "error_count": 0,
      "response_time_ms": 0,
    },
    "overall": {
      "search_run_count": 0,
      "last_search_time": "",
      "provider_success_rate": 0.0,
    },
  }


def accumulate_usage_metrics(
  base: Mapping[str, Any],
  *,
  patent: Mapping[str, Any],
  paper: Mapping[str, Any],
  web: Mapping[str, Any],
  search_run_id: str,
) -> dict[str, Any]:
  metrics = {
    "patent": dict(base.get("patent", {}) or {}),
    "paper": dict(base.get("paper", {}) or {}),
    "web": dict(base.get("web", {}) or {}),
    "overall": dict(base.get("overall", {}) or {}),
    "search_run_id": search_run_id,
  }
  if patent:
    metrics["patent"]["execution_count"] = int(metrics["patent"].get("execution_count", 0) or 0) + 1
    metrics["patent"]["billed_bytes"] = int(metrics["patent"].get("billed_bytes", 0) or 0) + int(patent.get("total_bytes_billed", 0) or 0)
    metrics["patent"]["result_count"] = len(list(patent.get("rows", []) or []))
  if paper:
    metrics["paper"]["request_count"] = int(metrics["paper"].get("request_count", 0) or 0) + int(paper.get("request_count", 1) or 1)
    metrics["paper"]["result_count"] = len(list(paper.get("rows", []) or []))
    if str(paper.get("status", "")) == "failed":
      metrics["paper"]["error_count"] = int(metrics["paper"].get("error_count", 0) or 0) + 1
  if web:
    metrics["web"]["request_count"] = int(metrics["web"].get("request_count", 0) or 0) + 1
    metrics["web"]["result_count"] = len(list(web.get("rows", []) or []))
    usage_credits = web.get("usage_credits")
    if usage_credits is not None:
      current = metrics["web"].get("total_credits")
      metrics["web"]["total_credits"] = int(current or 0) + int(usage_credits or 0)
    if str(web.get("status", "")) == "failed":
      metrics["web"]["error_count"] = int(metrics["web"].get("error_count", 0) or 0) + 1
  return metrics
