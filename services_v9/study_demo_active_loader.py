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
  if loaded.get("status") in {"ok", "invalid"} and loaded.get("context"):
    ctx = dict(loaded.get("context", {}) or {})
    recoverable = set(loaded.get("errors", []) or []) <= {"context_type_run_origin_mismatch"}
    if loaded.get("status") == "ok" or recoverable:
      return {
        "status": "ok",
        "context": ctx,
        "generation": loaded.get("generation"),
        "source": "gcs",
        "recovered_from_invalid": loaded.get("status") == "invalid",
      }
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
  from services_v9.study_demo_source_url import enrich_signal_with_url_provenance, resolve_signal_source_url

  enriched = enrich_signal_with_url_provenance(signal)
  resolution = resolve_signal_source_url(enriched)
  source_type = str(enriched.get("source_type", "") or "")
  signal_type = SOURCE_TYPE_TO_SIGNAL_TYPE.get(source_type, "web")
  relevance_reason = str(enriched.get("relevance_reason", "") or "")
  title = str(enriched.get("title", "") or "")
  summary = str(enriched.get("summary", "") or "")
  organization = str(enriched.get("organization", "") or "")
  published = str(enriched.get("published_at", "") or "")
  url = resolution.resolved_url if resolution.is_valid else ""
  score = float(enriched.get("relevance_score", enriched.get("integrated_relevance_score", 0)) or 0) / 100.0
  signal_id = str(enriched.get("signal_id", "") or enriched.get("source_id", "") or f"study-demo-{index}")
  tags = list(enriched.get("matched_core_terms", []) or []) + list(enriched.get("matched_process_terms", []) or [])
  return {
    "id": signal_id,
    "title": title,
    "type": signal_type,
    "source_url": url,
    "source_url_original": enriched.get("source_url_original", ""),
    "source_url_resolved": enriched.get("source_url_resolved", ""),
    "source_url_status": enriched.get("source_url_status", ""),
    "source_url_source": enriched.get("source_url_source", ""),
    "url_resolution_status": enriched.get("url_resolution_status", ""),
    "resolved_url": enriched.get("resolved_url", ""),
    "source_name": organization or source_type,
    "published_date": published,
    "summary": summary,
    "score": max(0.0, min(1.0, score)),
    "previous_score": None,
    "status": "Stable",
    "action": "Read Now" if str(enriched.get("relevance_tier", "")) == "A" else "Watch",
    "why_read": relevance_reason or summary[:240],
    "what_to_check": build_what_to_check(enriched),
    "next_action": build_next_action(enriched),
    "tags": tags[:8],
    "companies": [organization] if organization else [],
    "language": str(enriched.get("language", "") or ""),
    "memo": "",
    "study_demo": {
      "relevance_tier": enriched.get("relevance_tier"),
      "relevance_score": enriched.get("relevance_score"),
      "relevance_reason": relevance_reason,
      "target_material_match": enriched.get("target_material_match"),
      "target_material_mismatch": enriched.get("target_material_mismatch"),
      "matched_core_terms": enriched.get("matched_core_terms", []),
      "matched_negative_terms": enriched.get("matched_negative_terms", []),
      "score_breakdown": enriched.get("score_breakdown", {}),
      "source_run_id": enriched.get("search_run_id", ""),
      "source_type_raw": source_type,
      "url_source": resolution.url_source,
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
  from services_v9.study_demo_run_metrics import (
    build_canonical_run_metrics,
    resolve_active_source_label,
    resolve_creation_path_label,
  )

  integrated = load_active_integrated_signals(context, storage_client=storage_client, recompute_relevance=True)
  adapted = adapt_integrated_signals_for_display(integrated)
  resolved = resolve_active_run_counts(context, storage_client=storage_client)
  provider_status = load_active_provider_status(context, storage_client=storage_client)
  usage_metrics = load_active_usage_metrics(context, storage_client=storage_client)
  metrics = build_canonical_run_metrics(
    context=context,
    resolved=resolved,
    provider_status=provider_status,
    usage_metrics=usage_metrics,
  )
  tier_counts = dict(resolved.get("tier_counts", {}) or {})
  label = resolve_active_source_label(context)
  return {
    "requested_mode": "temporary_search",
    "mode": "temporary_search",
    "label": label,
    "creation_path_label": resolve_creation_path_label(context),
    "signals": adapted,
    "loaded_count": int(metrics.get("integrated_count") or len(adapted) or 0),
    "warnings": [],
    "provisional_scoring": False,
    "active_context": dict(context),
    "resolved_context": resolved,
    "canonical_metrics": metrics,
    "provider_status": dict(provider_status or {}),
    "integration_summary": {
      "integration_run_id": str(context.get("active_search_run_id", "")),
      "ranked_count": metrics.get("ranked_count"),
      "integrated_count": metrics.get("integrated_count"),
      "saved_count": metrics.get("saved_count"),
      "provider_counts": dict(metrics.get("provider_counts", {}) or {}),
      "tier_counts": tier_counts,
      "data_origin": "active_search_run_artifact",
      "active_search_run_id": str(context.get("active_search_run_id", "")),
      "active_sources": list(metrics.get("active_retrieval_sources", []) or []),
      "provider_success_rate": metrics.get("provider_success_rate"),
      "metric_inconsistencies": list(metrics.get("inconsistencies", []) or []),
      "metric_sources": dict(metrics.get("metric_sources", {}) or {}),
    },
    "is_watch_profile_run": str(context.get("run_origin", "")) == "watch_profile"
      or str(context.get("context_type", "")) == "watch_profile",
  }


def resolve_loader_mode(context_type: str) -> str:
  mapping = {
    "temporary_search": "temporary_search",
    "watch_profile": "temporary_search",
    "uploaded_csv": "csv",
    "uploaded_json": "json",
    "stored_artifact": "retrieval_saved",
    "legacy_demo": "legacy_demo",
  }
  return mapping.get(context_type, "unselected")
