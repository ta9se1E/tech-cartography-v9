"""Step 1 search plan preview for study demo three-source search."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

from services_v9.study_demo_config import (
  get_study_demo_bigquery_max_bytes_billed,
  get_study_demo_bigquery_price_per_tib_usd,
  is_study_demo_patent_search_enabled,
  is_study_demo_paper_search_enabled,
  is_study_demo_search_enabled,
  is_study_demo_web_search_enabled,
)

from .constants import STUDY_DEMO_BQ_MAX_BYTES_BILLED_DEFAULT
from .patent_provider import build_study_demo_patent_plan
from .paper_provider import build_study_demo_paper_plan
from .request import StudyDemoSearchRequest, request_fingerprint, validate_search_request
from .web_provider import build_study_demo_web_plan


def build_search_plan_preview(
  request: StudyDemoSearchRequest,
  *,
  environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
  errors = validate_search_request(request)
  if errors:
    return {"status": "blocked", "errors": errors}
  if not is_study_demo_search_enabled(environ):
    return {"status": "blocked", "errors": ["study demo search is not enabled"]}

  search_plan_id = str(uuid.uuid4())
  fingerprint = request_fingerprint(request)
  providers: dict[str, Any] = {}
  if request.enable_patent and is_study_demo_patent_search_enabled(environ):
    providers["patent"] = build_study_demo_patent_plan(request, environ=environ)
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

  max_bytes = get_study_demo_bigquery_max_bytes_billed(environ) or STUDY_DEMO_BQ_MAX_BYTES_BILLED_DEFAULT
  price_per_tib = get_study_demo_bigquery_price_per_tib_usd(environ)
  patent_plan = dict(providers.get("patent", {}) or {})
  estimated_bytes = int(patent_plan.get("estimated_bytes", 0) or 0)
  reference_cost_usd = None
  if price_per_tib > 0 and estimated_bytes > 0:
    reference_cost_usd = round((estimated_bytes / (1024**4)) * price_per_tib, 4)

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
      "bigquery_max_bytes_billed": max_bytes,
      "bigquery_estimated_bytes": estimated_bytes,
      "bigquery_reference_cost_usd": reference_cost_usd,
      "tavily_credit_hint": providers.get("web", {}).get("credit_hint"),
      "openalex_request_hint": providers.get("paper", {}).get("request_count_hint"),
    },
    "execution_blocked": True,
    "notes": [
      "Step 1 only: no live provider execution",
      "Step 2 requires confirmation checkbox and unchanged plan fingerprint",
    ],
  }


def plan_fingerprint(plan: Mapping[str, Any]) -> str:
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
  }
  digest = hashlib.sha256(repr(payload).encode()).hexdigest()
  return digest[:16]
