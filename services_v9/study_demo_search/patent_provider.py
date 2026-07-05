"""Patent BigQuery provider wrapper for study demo keyword search."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from services_v9.patent_bigquery_query import (
  build_patent_bigquery_preview,
  build_patent_bigquery_sql,
  execute_patent_bigquery_retrieval,
  run_patent_bigquery_dry_run,
)
from services_v9.patent_bigquery_safety import BigQuerySafetyConfig
from services_v9.study_demo_config import (
  get_study_demo_bigquery_max_bytes_billed,
  get_study_demo_bigquery_price_per_tib_usd,
)

from .request import StudyDemoSearchRequest


def _terms_from_request(request: StudyDemoSearchRequest) -> list[str]:
  terms: list[str] = []
  for chunk in (request.keywords_ja, request.keywords_en, request.exact_phrase, request.theme):
    for part in str(chunk or "").replace(",", " ").split():
      token = part.strip()
      if token:
        terms.append(token)
  return terms


def _exclude_terms(request: StudyDemoSearchRequest) -> list[str]:
  return [part.strip() for part in str(request.exclude_keywords or "").replace(",", " ").split() if part.strip()]


def _watch_profile_from_request(request: StudyDemoSearchRequest) -> dict[str, Any]:
  return {
    "theme_name": request.theme or "study-demo-search",
    "countries": [],
    "target_companies": [],
  }


def _search_plan_from_request(request: StudyDemoSearchRequest) -> dict[str, Any]:
  seed = [request.seed_patent] if request.seed_patent else []
  return {
    "plans": {
      "patent": {
        "limit": request.patent_display_limit,
        "exclude_terms": _exclude_terms(request),
        "seed_publications": seed,
        "queries": [
          {
            "query_id": "study_demo_patent_q01",
            "strategy": "keyword",
            "language": "mixed",
            "terms": _terms_from_request(request),
          }
        ],
      }
    }
  }


def _time_range_from_years(request: StudyDemoSearchRequest) -> str:
  if request.year_start and request.year_end:
    return "custom"
  return "all"


def _query_fingerprint(request: StudyDemoSearchRequest) -> str:
  digest = hashlib.sha256(json.dumps(_search_plan_from_request(request), sort_keys=True).encode()).hexdigest()
  return digest[:16]


def build_study_demo_patent_plan(
  request: StudyDemoSearchRequest,
  *,
  environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
  cfg = BigQuerySafetyConfig.from_env()
  max_bytes = get_study_demo_bigquery_max_bytes_billed(environ) or cfg.bigquery_max_bytes_billed
  preview = build_patent_bigquery_preview(
    _search_plan_from_request(request),
    _watch_profile_from_request(request),
    selected_query_id="study_demo_patent_q01",
    time_range=_time_range_from_years(request),
    max_results=request.patent_display_limit,
    config=cfg,
  )
  sql_fingerprint = ""
  req = dict(preview.get("request", {}) or {})
  if req:
    sql_fingerprint = hashlib.sha256(build_patent_bigquery_sql(req).encode()).hexdigest()[:16]
  estimated_bytes = 0
  validation_rows = list(preview.get("validation_rows", []) or [])
  ok = all(str(row.get("status", "")) != "error" for row in validation_rows)
  return {
    "status": "ready" if ok else "blocked",
    "provider": "patent",
    "query_fingerprint": _query_fingerprint(request),
    "sql_fingerprint": sql_fingerprint,
    "validation_rows": validation_rows,
    "request_summary": {
      "query_id": req.get("query_id"),
      "max_results": request.patent_display_limit,
      "year_start": request.year_start,
      "year_end": request.year_end,
      "seed_patent": request.seed_patent,
    },
    "estimated_bytes": estimated_bytes,
    "dry_run_required": True,
    "maximum_bytes_billed": max_bytes,
    "price_per_tib_usd": get_study_demo_bigquery_price_per_tib_usd(environ),
  }


def run_study_demo_patent_dry_run(
  request: StudyDemoSearchRequest,
  *,
  environ: Mapping[str, str] | None = None,
  client_factory=None,
) -> dict[str, Any]:
  preview = build_patent_bigquery_preview(
    _search_plan_from_request(request),
    _watch_profile_from_request(request),
    selected_query_id="study_demo_patent_q01",
    time_range=_time_range_from_years(request),
    max_results=request.patent_display_limit,
  )
  return run_patent_bigquery_dry_run(preview, client_factory=client_factory)


def run_study_demo_patent_execute(
  request: StudyDemoSearchRequest,
  *,
  dry_run_result: dict[str, Any],
  environ: Mapping[str, str] | None = None,
  client_factory=None,
) -> dict[str, Any]:
  preview = build_patent_bigquery_preview(
    _search_plan_from_request(request),
    _watch_profile_from_request(request),
    selected_query_id="study_demo_patent_q01",
    time_range=_time_range_from_years(request),
    max_results=request.patent_display_limit,
  )
  preview["dry_run"] = dry_run_result
  return execute_patent_bigquery_retrieval(preview, client_factory=client_factory)
