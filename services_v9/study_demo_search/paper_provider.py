"""OpenAlex paper provider wrapper for study demo keyword search."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from services_v9.paper_openalex_retrieval import (
  build_openalex_paper_preview,
  build_openalex_search_url,
  execute_openalex_paper_retrieval,
)
from services_v9.study_demo_config import get_study_demo_openalex_api_key

from .request import StudyDemoSearchRequest


def _search_plan_from_request(request: StudyDemoSearchRequest) -> dict[str, Any]:
  terms = []
  for chunk in (request.keywords_en, request.keywords_ja, request.exact_phrase, request.theme):
    for part in str(chunk or "").replace(",", " ").split():
      token = part.strip()
      if token:
        terms.append(token)
  return {
    "plans": {
      "paper": {
        "limit": request.paper_display_limit,
        "exclude_terms": [p.strip() for p in request.exclude_keywords.replace(",", " ").split() if p.strip()],
        "queries": [
          {
            "query_id": "study_demo_paper_q01",
            "strategy": "keyword",
            "language": "mixed",
            "terms": terms,
          }
        ],
      }
    }
  }


def _watch_profile_from_request(request: StudyDemoSearchRequest) -> dict[str, Any]:
  return {"theme_name": request.theme or "study-demo-search", "countries": [], "target_companies": []}


def _query_fingerprint(request: StudyDemoSearchRequest) -> str:
  digest = hashlib.sha256(json.dumps(_search_plan_from_request(request), sort_keys=True).encode()).hexdigest()
  return digest[:16]


def build_study_demo_paper_plan(
  request: StudyDemoSearchRequest,
  *,
  environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
  preview = build_openalex_paper_preview(
    _search_plan_from_request(request),
    _watch_profile_from_request(request),
    selected_query_id="study_demo_paper_q01",
    time_range="all",
    max_results=request.paper_display_limit,
    per_page=min(request.paper_display_limit, 200),
  )
  req = dict(preview.get("request", {}) or {})
  if request.year_start:
    req["publication_date_from"] = f"{request.year_start}-01-01"
  if request.year_end:
    req["publication_date_to"] = f"{request.year_end}-12-31"
  if request.paper_open_access_only:
    req["open_access_only"] = True
  req["sort"] = request.paper_sort
  url_preview = build_openalex_search_url(req, cursor="*")
  request_count_hint = max(1, (request.paper_display_limit + int(req.get("per_page", 25)) - 1) // int(req.get("per_page", 25)))
  ok = all(str(row.get("status", "")) != "error" for row in list(preview.get("validation_rows", []) or []))
  api_key_configured = bool(get_study_demo_openalex_api_key(environ))
  return {
    "status": "ready" if ok and api_key_configured else "blocked",
    "provider": "paper",
    "query_fingerprint": _query_fingerprint(request),
    "url_length": len(url_preview),
    "request_count_hint": request_count_hint,
    "validation_rows": preview.get("validation_rows", []),
    "request_summary": {
      "max_results": request.paper_display_limit,
      "open_access_only": request.paper_open_access_only,
      "sort": request.paper_sort,
      "api_key_configured": api_key_configured,
    },
    "split_required": len(url_preview) > 1800,
  }


def run_study_demo_paper_execute(
  request: StudyDemoSearchRequest,
  *,
  environ: Mapping[str, str] | None = None,
  open_url=None,
  sleep_fn=None,
) -> dict[str, Any]:
  preview = build_openalex_paper_preview(
    _search_plan_from_request(request),
    _watch_profile_from_request(request),
    selected_query_id="study_demo_paper_q01",
    time_range="all",
    max_results=request.paper_display_limit,
    per_page=min(request.paper_display_limit, 200),
    retry_limit=0,
  )
  req = dict(preview.get("request", {}) or {})
  api_key = get_study_demo_openalex_api_key(environ)
  if api_key:
    req["api_key"] = api_key
  preview["request"] = req
  req["retry_limit"] = 0
  return execute_openalex_paper_retrieval(preview, opener=open_url, sleeper=sleep_fn)
