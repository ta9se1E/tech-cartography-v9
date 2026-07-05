"""Step 2 orchestration for study demo three-source search."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

from services_v9.study_demo_config import (
  is_study_demo_patent_search_enabled,
  is_study_demo_paper_search_enabled,
  is_study_demo_search_enabled,
  is_study_demo_web_search_enabled,
)

from .export import build_export_bundle
from .integration import integrate_search_results
from .keywords import build_keyword_suggestions
from .lock import acquire_search_lock, release_search_lock
from .patent_provider import run_study_demo_patent_execute
from .paper_provider import run_study_demo_paper_execute
from .plan import build_search_plan_preview, plan_fingerprint
from .request import StudyDemoSearchRequest, request_fingerprint, validate_search_request
from .similar import build_similar_patents
from .storage import save_search_run
from .usage import accumulate_usage_metrics, init_usage_metrics
from .web_provider import run_study_demo_web_execute


def _provider_result_status(payload: Mapping[str, Any]) -> str:
  raw = str(payload.get("status", "") or payload.get("provider_status", "") or "").strip().lower()
  if raw in {"success", "partial_success"}:
    return "success"
  if raw in {"no_results"}:
    return "failed"
  if raw in {"error", "failed", "validation_error"}:
    return "failed"
  return raw or "failed"


def execute_three_source_search(
  request: StudyDemoSearchRequest,
  *,
  plan: Mapping[str, Any],
  confirmed: bool,
  executed_plan_ids: set[str] | None = None,
  environ: Mapping[str, str] | None = None,
  storage_client: Any | None = None,
  patent_client_factory=None,
  open_url=None,
  json_post_fn=None,
) -> dict[str, Any]:
  errors = validate_search_request(request)
  if errors:
    return {"status": "blocked", "errors": errors}
  if not confirmed:
    return {"status": "blocked", "errors": ["confirmation checkbox is required"]}
  if not is_study_demo_search_enabled(environ):
    return {"status": "blocked", "errors": ["study demo search is not enabled"]}

  plan_id = str(plan.get("search_plan_id", "") or "")
  if not plan_id:
    return {"status": "blocked", "errors": ["search plan id is required"]}
  if executed_plan_ids and plan_id in executed_plan_ids:
    return {"status": "blocked", "errors": ["duplicate search_plan_id execution is forbidden"]}
  if str(plan.get("request_fingerprint", "")) != request_fingerprint(request):
    return {"status": "blocked", "errors": ["search conditions changed since plan; regenerate plan"]}

  patent_plan = dict(dict(plan.get("providers", {}) or {}).get("patent", {}) or {})
  if request.enable_patent and is_study_demo_patent_search_enabled(environ):
    patent_status = str(patent_plan.get("status", "") or "")
    if patent_status == "dry_run_failed":
      return {"status": "blocked", "errors": ["patent BigQuery dry-run failed; regenerate plan"]}
    if patent_status == "dry_run_zero_bytes":
      return {"status": "blocked", "errors": ["patent BigQuery dry-run returned zero bytes; regenerate plan"]}
    if patent_plan.get("dry_run_fingerprint") != request_fingerprint(request):
      return {"status": "blocked", "errors": ["patent dry-run fingerprint mismatch; regenerate plan"]}
    dry_run = dict(patent_plan.get("dry_run", {}) or {})
    if str(dry_run.get("dry_run_status", "") or "") != "ok":
      return {"status": "blocked", "errors": ["patent dry-run result missing or invalid; regenerate plan"]}
    if not bool(patent_plan.get("bigquery_execution_allowed", False)):
      return {"status": "blocked", "errors": ["patent BigQuery execution blocked by cost guard; regenerate plan"]}

  search_run_id = f"study_demo_search_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
  lock_info: dict[str, Any] = {}
  try:
    lock_info = acquire_search_lock(search_run_id, environ=environ, storage_client=storage_client)
    if not lock_info.get("acquired"):
      return {"status": "blocked", "message": lock_info.get("message", "search lock not acquired")}

    provider_status: dict[str, Any] = {}
    patent_results: dict[str, Any] = {}
    paper_results: dict[str, Any] = {}
    web_results: dict[str, Any] = {}

    if request.enable_patent and is_study_demo_patent_search_enabled(environ):
      try:
        dry_run = dict(patent_plan.get("dry_run", {}) or {})
        patent_results = run_study_demo_patent_execute(
          request,
          dry_run_result=dry_run,
          environ=environ,
          client_factory=patent_client_factory,
        )
        provider_status["patent"] = {"status": _provider_result_status(patent_results), "error_category": patent_results.get("error_category")}
      except Exception as exc:  # noqa: BLE001
        provider_status["patent"] = {"status": "failed", "error_category": type(exc).__name__}
    elif request.enable_patent:
      provider_status["patent"] = {"status": "skipped", "error_category": "disabled"}

    if request.enable_paper and is_study_demo_paper_search_enabled(environ):
      try:
        paper_results = run_study_demo_paper_execute(request, environ=environ, open_url=open_url)
        provider_status["paper"] = {"status": _provider_result_status(paper_results), "error_category": paper_results.get("error_category")}
      except Exception as exc:  # noqa: BLE001
        provider_status["paper"] = {"status": "failed", "error_category": type(exc).__name__}
    elif request.enable_paper:
      provider_status["paper"] = {"status": "skipped", "error_category": "disabled"}

    if request.enable_web and is_study_demo_web_search_enabled(environ):
      try:
        web_results = run_study_demo_web_execute(request, environ=environ, json_post_fn=json_post_fn)
        provider_status["web"] = {"status": _provider_result_status(web_results), "error_category": web_results.get("error_category")}
      except Exception as exc:  # noqa: BLE001
        provider_status["web"] = {"status": "failed", "error_category": type(exc).__name__}
    elif request.enable_web:
      provider_status["web"] = {"status": "skipped", "error_category": "disabled"}

    integrated = integrate_search_results(
      patent_rows=list(patent_results.get("rows", []) or []),
      paper_rows=list(paper_results.get("rows", []) or []),
      web_rows=list(web_results.get("rows", []) or []),
      search_run_id=search_run_id,
      query_provenance=plan.get("summary", {}),
    )
    keywords = build_keyword_suggestions(integrated.get("signals", []))
    similar = build_similar_patents(
      integrated.get("signals", []),
      seed_patent=request.seed_patent,
    )
    usage = accumulate_usage_metrics(
      init_usage_metrics(),
      patent=patent_results,
      paper=paper_results,
      web=web_results,
      search_run_id=search_run_id,
    )

    successes = [name for name, item in provider_status.items() if item.get("status") == "success"]
    failures = [name for name, item in provider_status.items() if item.get("status") == "failed"]
    if successes and failures:
      overall = "partial_success"
    elif successes:
      overall = "success"
    else:
      overall = "failed"

    bundle = {
      "search_run_id": search_run_id,
      "search_plan_id": plan_id,
      "search_plan": dict(plan),
      "summary": dict(plan.get("summary", {}) or {}),
      "cost_estimate": dict(plan.get("cost_estimate", {}) or {}),
      "status": overall,
      "provider_status": provider_status,
      "patent_results": patent_results,
      "paper_results": paper_results,
      "web_results": web_results,
      "integrated_signals": integrated,
      "keyword_suggestions": keywords,
      "similar_patents": similar,
      "usage_metrics": usage,
      "export": build_export_bundle(integrated.get("signals", []), keywords, similar, usage),
    }
    save_search_run(bundle, environ=environ, storage_client=storage_client)
    return bundle
  finally:
    if lock_info:
      release_search_lock(lock_info, storage_client=storage_client)


def request_fingerprint_from_plan(plan: Mapping[str, Any], request: StudyDemoSearchRequest) -> str:
  from .request import request_fingerprint

  return request_fingerprint(request)


__all__ = ["build_search_plan_preview", "execute_three_source_search", "plan_fingerprint"]
