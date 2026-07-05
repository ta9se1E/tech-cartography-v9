"""Step 1 search plan preview for study demo three-source search."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

from services_v9.study_demo_config import (
  get_study_demo_bigquery_max_bytes_billed,
  is_study_demo_patent_search_enabled,
  is_study_demo_paper_search_enabled,
  is_study_demo_search_enabled,
  is_study_demo_web_search_enabled,
)

from .constants import STUDY_DEMO_BQ_MAX_BYTES_BILLED_DEFAULT
from .cost_preview import build_bigquery_cost_estimate, enrich_patent_plan_with_dry_run
from .patent_provider import build_study_demo_patent_plan, run_study_demo_patent_dry_run
from .paper_provider import build_study_demo_paper_plan
from .request import StudyDemoSearchRequest, request_fingerprint, validate_search_request
from .web_provider import build_study_demo_web_plan


def build_search_plan_preview(
  request: StudyDemoSearchRequest,
  *,
  environ: Mapping[str, str] | None = None,
  patent_dry_run_runner=None,
  patent_client_factory=None,
) -> dict[str, Any]:
  errors = validate_search_request(request)
  if errors:
    return {"status": "blocked", "errors": errors}
  if not is_study_demo_search_enabled(environ):
    return {"status": "blocked", "errors": ["study demo search is not enabled"]}

  search_plan_id = str(uuid.uuid4())
  fingerprint = request_fingerprint(request)
  providers: dict[str, Any] = {}
  dry_run_runner = patent_dry_run_runner or run_study_demo_patent_dry_run
  if request.enable_patent and is_study_demo_patent_search_enabled(environ):
    base_patent_plan = build_study_demo_patent_plan(request, environ=environ)
    if str(base_patent_plan.get("status", "")) == "blocked":
      providers["patent"] = base_patent_plan
    else:
      dry_run = dry_run_runner(
        request,
        environ=environ,
        client_factory=patent_client_factory,
      )
      providers["patent"] = enrich_patent_plan_with_dry_run(
        base_patent_plan,
        dry_run,
        dry_run_fingerprint=fingerprint,
        environ=environ,
      )
  elif request.enable_patent:
    providers["patent"] = {"status": "disabled", "message": "patent search disabled by configuration"}
  if request.enable_paper and is_study_demo_paper_search_enabled(environ):
    providers["paper"] = build_study_demo_paper_plan(request, environ=environ)
  elif request.enable_paper:
    providers["paper"] = {"status": "disabled", "message": "paper search disabled by configuration"}
  if request.enable_web and is_study_demo_web_search_enabled(environ):
    providers["web"] = build_study_demo_web_plan(request, environ=environ)
  elif request.enable_web:
    providers["web"] = {"status": "disabled", "message": "web search disabled by configuration"}

  patent_plan = dict(providers.get("patent", {}) or {})
  web_plan = dict(providers.get("web", {}) or {})
  bq_cost = build_bigquery_cost_estimate(patent_plan, environ=environ) if patent_plan else {
    "bigquery_max_bytes_billed": get_study_demo_bigquery_max_bytes_billed(environ) or STUDY_DEMO_BQ_MAX_BYTES_BILLED_DEFAULT,
    "bigquery_estimated_bytes": 0,
    "bigquery_estimated_gib": 0.0,
    "bigquery_estimated_tib": 0.0,
    "bigquery_reference_cost_usd": None,
    "bigquery_execution_allowed": False,
  }

  return {
    "status": "plan",
    "search_plan_id": search_plan_id,
    "request_fingerprint": fingerprint,
    "created_at": datetime.now(timezone.utc).isoformat(),
    "summary": {
      "theme": request.theme,
      "keywords_ja": request.keywords_ja,
      "keywords_en": request.keywords_en,
      "exact_phrase": request.exact_phrase,
      "exclude_keywords": request.exclude_keywords,
      "seed_patent": request.seed_patent,
      "year_start": request.year_start,
      "year_end": request.year_end,
      "providers": {
        "patent": request.enable_patent,
        "paper": request.enable_paper,
        "web": request.enable_web,
      },
    },
    "providers": providers,
    "cost_estimate": {
      **bq_cost,
      "tavily_credit_estimate_status": web_plan.get("credit_estimate_status"),
      "tavily_credit_hint": web_plan.get("credit_hint"),
      "tavily_credit_estimate_basis": web_plan.get("credit_estimate_basis"),
      "openalex_request_hint": providers.get("paper", {}).get("request_count_hint"),
    },
    "execution_blocked": True,
    "notes": [
      "Step 1 runs Patent BigQuery dry-run only; Paper/OpenAlex and Web/Tavily live search are not executed",
      "Step 2 requires confirmation checkbox, unchanged request fingerprint, and valid Patent dry-run",
    ],
  }


def plan_fingerprint(plan: Mapping[str, Any]) -> str:
  patent = dict(dict(plan.get("providers", {}) or {}).get("patent", {}) or {})
  payload = {
    "request_fingerprint": plan.get("request_fingerprint"),
    "providers": {
      key: {
        "status": value.get("status"),
        "query_fingerprint": value.get("query_fingerprint"),
      }
      for key, value in dict(plan.get("providers", {}) or {}).items()
      if isinstance(value, dict)
    },
    "patent_dry_run_fingerprint": patent.get("dry_run_fingerprint"),
    "patent_estimated_bytes": patent.get("bigquery_estimated_bytes", patent.get("estimated_bytes")),
  }
  digest = hashlib.sha256(repr(payload).encode()).hexdigest()
  return digest[:16]
