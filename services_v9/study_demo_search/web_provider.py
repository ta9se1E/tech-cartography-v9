"""Tavily web provider wrapper for study demo keyword search."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from services_v9.study_demo_config import get_study_demo_tavily_api_key
from services_v9.web_company_retrieval import build_global_web_retrieval_preview, execute_global_web_retrieval

from .request import StudyDemoSearchRequest


def _search_plan_from_request(request: StudyDemoSearchRequest) -> dict[str, Any]:
  query_parts = [request.theme, request.keywords_ja, request.keywords_en, request.exact_phrase]
  query_text = " ".join(part.strip() for part in query_parts if str(part or "").strip())
  return {
    "plans": {
      "web_company": {
        "limit": request.web_max_results,
        "query_text": query_text,
        "exclude_terms": [p.strip() for p in request.exclude_keywords.replace(",", " ").split() if p.strip()],
      }
    }
  }


def _query_fingerprint(request: StudyDemoSearchRequest) -> str:
  digest = hashlib.sha256(json.dumps(_search_plan_from_request(request), sort_keys=True).encode()).hexdigest()
  return digest[:16]


def build_study_demo_web_plan(
  request: StudyDemoSearchRequest,
  *,
  environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
  preview = build_global_web_retrieval_preview(_search_plan_from_request(request))
  api_key_configured = bool(get_study_demo_tavily_api_key(environ))
  credit_hint = request.web_max_results if request.web_search_depth == "basic" else request.web_max_results * 2
  ok = all(str(row.get("status", "")) != "error" for row in list(preview.get("validation_rows", []) or []))
  return {
    "status": "ready" if ok and api_key_configured else "blocked",
    "provider": "web",
    "query_fingerprint": _query_fingerprint(request),
    "validation_rows": preview.get("validation_rows", []),
    "request_summary": {
      "topic": request.web_topic,
      "search_depth": request.web_search_depth,
      "max_results": request.web_max_results,
      "time_range": request.web_time_range,
      "exact_match": request.web_exact_match,
      "include_raw_content": request.web_include_raw_content,
      "api_key_configured": api_key_configured,
    },
    "credit_hint": credit_hint,
    "defaults": {
      "include_answer": False,
      "include_images": False,
      "include_usage": True,
      "include_raw_content": False,
      "auto_parameters": False,
    },
  }


def run_study_demo_web_execute(
  request: StudyDemoSearchRequest,
  *,
  environ: Mapping[str, str] | None = None,
  json_post_fn=None,
  sleep_fn=None,
) -> dict[str, Any]:
  plan = _search_plan_from_request(request)
  preview = build_global_web_retrieval_preview(plan)
  req = dict(preview.get("request", {}) or {})
  req.update(
    {
      "topic": request.web_topic,
      "search_depth": request.web_search_depth,
      "max_results": request.web_max_results,
      "time_range": request.web_time_range,
      "include_answer": False,
      "include_images": False,
      "include_usage": True,
      "include_raw_content": request.web_include_raw_content,
      "auto_parameters": False,
      "exact_match": request.web_exact_match,
      "tavily_api_key": get_study_demo_tavily_api_key(environ),
    }
  )
  preview["request"] = req
  return execute_global_web_retrieval(
    preview,
    tavily_search_post_fn=json_post_fn,
    allow_google_grounding=False,
    sleeper=sleep_fn,
  )
