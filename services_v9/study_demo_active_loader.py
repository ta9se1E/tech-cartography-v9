"""Common loader for Study Demo active analysis context."""

from __future__ import annotations

from typing import Any, Mapping

from services_v9.study_demo_analysis_context import (
  ACTIVE_CONTEXT_OBJECT,
  load_active_context_from_storage,
  validate_active_context,
)
from services_v9.study_demo_config import get_study_demo_bucket
from services_v9.study_demo_search.relevance_ranking import enrich_integrated_signals
from services_v9.study_demo_search.storage import build_search_result_from_artifacts, load_search_run
from services_v9.study_demo_storage import validate_study_demo_write_target

SOURCE_TYPE_TO_SIGNAL_TYPE = {
  "patent": "patent",
  "paper": "paper",
  "web_company": "web",
}


def load_active_analysis_context(
  *,
  session_context: Mapping[str, Any] | None = None,
  environ: Mapping[str, str] | None = None,
  storage_client: Any | None = None,
  reload_from_storage: bool = False,
) -> dict[str, Any]:
  if session_context and not reload_from_storage:
    errors = validate_active_context(session_context)
    if not errors:
      return {"status": "ok", "context": dict(session_context), "source": "session"}
  loaded = load_active_context_from_storage(environ=environ, storage_client=storage_client)
  if loaded.get("status") == "ok":
    return {"status": "ok", "context": dict(loaded.get("context", {}) or {}), "generation": loaded.get("generation"), "source": "gcs"}
  return {"status": loaded.get("status", "missing"), "context": None, "generation": loaded.get("generation"), "source": "gcs"}


def _artifact_bundle_from_context(context: Mapping[str, Any], *, storage_client: Any | None = None) -> dict[str, Any]:
  run_id = str(context.get("active_search_run_id", "") or "")
  return load_search_run(run_id, storage_client=storage_client)


def load_active_search_request(
  context: Mapping[str, Any],
  *,
  storage_client: Any | None = None,
) -> dict[str, Any]:
  loaded = _artifact_bundle_from_context(context, storage_client=storage_client)
  return dict(loaded.get("artifacts", {}).get("search_request.json", {}) or {})


def load_active_integrated_signals(
  context: Mapping[str, Any],
  *,
  storage_client: Any | None = None,
  recompute_relevance: bool = True,
) -> dict[str, Any]:
  loaded = _artifact_bundle_from_context(context, storage_client=storage_client)
  if recompute_relevance:
    bundle = build_search_result_from_artifacts(loaded)
    return dict(bundle.get("integrated_signals", {}) or {})
  return dict(loaded.get("artifacts", {}).get("integrated_signals.json", {}) or {})


def load_active_provider_status(
  context: Mapping[str, Any],
  *,
  storage_client: Any | None = None,
) -> dict[str, Any]:
  loaded = _artifact_bundle_from_context(context, storage_client=storage_client)
  return dict(loaded.get("artifacts", {}).get("provider_status.json", {}) or {})


def load_active_usage_metrics(
  context: Mapping[str, Any],
  *,
  storage_client: Any | None = None,
) -> dict[str, Any]:
  loaded = _artifact_bundle_from_context(context, storage_client=storage_client)
  return dict(loaded.get("artifacts", {}).get("usage_metrics.json", {}) or {})


def load_active_search_report(
  context: Mapping[str, Any],
  *,
  storage_client: Any | None = None,
) -> str:
  loaded = _artifact_bundle_from_context(context, storage_client=storage_client)
  return str(loaded.get("artifacts", {}).get("search_report.md", "") or "")


def adapt_study_demo_signal_to_display(signal: Mapping[str, Any], *, index: int = 0) -> dict[str, Any]:
  from services_v9.study_demo_downstream import build_what_to_check, build_next_action

  source_type = str(signal.get("source_type", "") or "")
  signal_type = SOURCE_TYPE_TO_SIGNAL_TYPE.get(source_type, "web")
  relevance_reason = str(signal.get("relevance_reason", "") or "")
  title = str(signal.get("title", "") or "")
  summary = str(signal.get("summary", "") or "")
  organization = str(signal.get("organization", "") or "")
  published = str(signal.get("published_at", "") or "")
  url = str(signal.get("url", "") or "")
  score = float(signal.get("relevance_score", signal.get("integrated_relevance_score", 0)) or 0) / 100.0
  signal_id = str(signal.get("signal_id", "") or signal.get("source_id", "") or f"study-demo-{index}")
  tags = list(signal.get("matched_core_terms", []) or []) + list(signal.get("matched_process_terms", []) or [])
  return {
    "id": signal_id,
    "title": title,
    "type": signal_type,
    "source_url": url,
    "source_name": organization or source_type,
    "published_date": published,
    "summary": summary,
    "score": max(0.0, min(1.0, score)),
    "previous_score": None,
    "status": "Stable",
    "action": "Read Now" if str(signal.get("relevance_tier", "")) == "A" else "Watch",
    "why_read": relevance_reason or summary[:240],
    "what_to_check": build_what_to_check(signal),
    "next_action": build_next_action(signal),
    "tags": tags[:8],
    "companies": [organization] if organization else [],
    "language": str(signal.get("language", "") or ""),
    "memo": "",
    "study_demo": {
      "relevance_tier": signal.get("relevance_tier"),
      "relevance_score": signal.get("relevance_score"),
      "relevance_reason": relevance_reason,
      "target_material_match": signal.get("target_material_match"),
      "target_material_mismatch": signal.get("target_material_mismatch"),
      "matched_core_terms": signal.get("matched_core_terms", []),
      "matched_negative_terms": signal.get("matched_negative_terms", []),
      "score_breakdown": signal.get("score_breakdown", {}),
      "source_run_id": signal.get("search_run_id", ""),
      "source_type_raw": source_type,
    },
  }


def adapt_integrated_signals_for_display(integrated: Mapping[str, Any]) -> list[dict[str, Any]]:
  signals = list(integrated.get("signals", []) or [])
  return [adapt_study_demo_signal_to_display(item, index=index) for index, item in enumerate(signals)]


def build_temporary_search_source_payload(
  context: Mapping[str, Any],
  *,
  storage_client: Any | None = None,
) -> dict[str, Any]:
  from services_v9.study_demo_resolved_context import resolve_active_run_counts

  integrated = load_active_integrated_signals(context, storage_client=storage_client, recompute_relevance=True)
  adapted = adapt_integrated_signals_for_display(integrated)
  resolved = resolve_active_run_counts(context, storage_client=storage_client)
  tier_counts = dict(resolved.get("tier_counts", {}) or {})
  return {
    "requested_mode": "temporary_search",
    "mode": "temporary_search",
    "label": "一時検索run",
    "signals": adapted,
    "loaded_count": int(resolved.get("integrated_ranked_count", len(adapted)) or len(adapted)),
    "warnings": [],
    "provisional_scoring": False,
    "active_context": dict(context),
    "resolved_context": resolved,
    "integration_summary": {
      "integration_run_id": str(context.get("active_search_run_id", "")),
      "ranked_count": int(resolved.get("integrated_ranked_count", len(adapted)) or len(adapted)),
      "provider_counts": dict(resolved.get("integrated_source_counts", {}) or {}),
      "tier_counts": tier_counts,
      "data_origin": "temporary_search_artifact",
      "active_search_run_id": str(context.get("active_search_run_id", "")),
    },
  }


def resolve_loader_mode(context_type: str) -> str:
  mapping = {
    "temporary_search": "temporary_search",
    "uploaded_csv": "csv",
    "uploaded_json": "json",
    "stored_artifact": "retrieval_saved",
    "legacy_demo": "legacy_demo",
  }
  return mapping.get(context_type, "unselected")
