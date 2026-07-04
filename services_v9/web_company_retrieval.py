"""Global Web / company retrieval helpers for v9."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from .persistence import ensure_v9_run_dirs
from .study_demo_guard import assert_external_execution_allowed

JsonPostFn = Callable[..., dict[str, Any]]
GoogleGroundingFn = Callable[[dict[str, Any]], dict[str, Any]]
SleepFn = Callable[[float], None]

PROVIDER_TAVILY = "tavily"
PROVIDER_GOOGLE_GROUNDING = "google_search_grounding"
DISCOVERY_SHORTAGE_THRESHOLD = 2
DEFAULT_VERIFICATION_LIMIT = 40
DEFAULT_SUMMARY_TOP_N = 8
MAX_VERIFICATION_LIMIT = 50
CONTENT_ACCESS_VALUES = {"full", "partial", "unavailable", "human_review_required"}
TAVILY_SEARCH_URL = "https://api.tavily.com/search"
TAVILY_EXTRACT_URL = "https://api.tavily.com/extract"
_TRACKING_QUERY_KEYS = {
  "utm_source",
  "utm_medium",
  "utm_campaign",
  "utm_term",
  "utm_content",
  "fbclid",
  "gclid",
  "mc_cid",
  "mc_eid",
}
_JP_CHAR_PATTERN = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
_WORD_PATTERN = re.compile(r"[A-Za-z0-9\u3040-\u30ff\u3400-\u9fff]+")
_SENSITIVE_KEY_PATTERN = re.compile(r"(api[_-]?key|authorization|token|secret)", re.IGNORECASE)
HIGH_QUALITY_DOMAINS: frozenset[str] = frozenset(
  {
    "jst.go.jp",
    "nedo.go.jp",
    "meti.go.jp",
    "mext.go.jp",
    "grants.jst.go.jp",
    "kaken.nii.ac.jp",
    "amed.go.jp",
    "fsa.go.jp",
    "edinet-fsa.go.jp",
    "disclosure2.edinet-fsa.go.jp",
    "jpx.co.jp",
  },
)
DISCLOSURE_PLATFORM_DOMAINS: frozenset[str] = frozenset(
  {
    "fsa.go.jp",
    "edinet-fsa.go.jp",
    "disclosure2.edinet-fsa.go.jp",
    "jpx.co.jp",
  },
)
PUBLIC_FUNDING_DOMAINS: frozenset[str] = frozenset(
  {
    "jst.go.jp",
    "nedo.go.jp",
    "grants.jst.go.jp",
    "kaken.nii.ac.jp",
    "amed.go.jp",
  },
)
NATIONAL_PROJECT_DOMAINS: frozenset[str] = frozenset(
  {
    "jst.go.jp",
    "nedo.go.jp",
    "meti.go.jp",
    "mext.go.jp",
    "grants.jst.go.jp",
    "kaken.nii.ac.jp",
    "amed.go.jp",
  },
)
LOW_QUALITY_HINTS: tuple[str, ...] = (
  "linkedin.com",
  "twitter.com",
  "x.com",
  "facebook.com",
  "instagram.com",
  "tiktok.com",
  "reddit.com",
  "medium.com",
  "note.com",
  "qiita.com",
  "wantedly.com",
  "indeed.com",
  "rikunabi.com",
  "mynavi.jp",
  "blogspot.",
  "wordpress.com",
)
JOB_BOARD_HINTS: tuple[str, ...] = (
  "indeed",
  "rikunabi",
  "mynavi",
  "wantedly",
  "doda",
  "en-japan",
)
LOCAL_NEWS_HINTS: tuple[str, ...] = (
  "local",
  "pref.",
  "city.",
  "news.co.jp",
  "shimbun",
)
LOCAL_GOVERNMENT_HINTS: tuple[str, ...] = (
  "pref.",
  "city.",
  "lg.jp",
  "go.jp",
)
IR_PATH_HINTS: tuple[str, ...] = (
  "/ir/",
  "/investor",
  "/investors/",
  "/ir-library",
  "/english/ir/",
)


def extract_source_domain(source_url: str) -> str:
  text = str(source_url or "").strip()
  if not text:
    return ""
  parsed = urlparse(text if "://" in text else f"https://{text}")
  host = (parsed.netloc or parsed.path or "").lower().strip()
  if host.startswith("www."):
    host = host[4:]
  return host


def build_tavily_search_payload(
  query: str,
  max_results: int = 5,
  include_domains: list[str] | None = None,
  exclude_domains: list[str] | None = None,
) -> dict[str, Any]:
  payload: dict[str, Any] = {
    "query": str(query or "").strip(),
    "max_results": int(max_results),
    "search_depth": "basic",
    "include_answer": False,
    "include_raw_content": False,
  }
  if include_domains:
    payload["include_domains"] = list(include_domains)
  if exclude_domains:
    payload["exclude_domains"] = list(exclude_domains)
  return payload


def build_tavily_extract_payload(urls: list[str]) -> dict[str, Any]:
  return {
    "urls": [str(url).strip() for url in urls if str(url).strip()],
  }


def _scrub_sensitive_value(key: str, value: Any) -> Any:
  if _SENSITIVE_KEY_PATTERN.search(key):
    return "[redacted]"
  if isinstance(value, dict):
    return scrub_sensitive_payload(value)
  if isinstance(value, list):
    return [scrub_sensitive_payload(item) if isinstance(item, dict) else item for item in value]
  return value


def scrub_sensitive_payload(payload: dict[str, Any]) -> dict[str, Any]:
  cleaned: dict[str, Any] = {}
  for key, value in payload.items():
    cleaned[key] = _scrub_sensitive_value(key, value)
  return cleaned


def normalize_tavily_search_response(
  raw: dict[str, Any],
  *,
  query: str,
  fetched_at: str,
) -> list[dict[str, Any]]:
  normalized: list[dict[str, Any]] = []
  for item in raw.get("results") or []:
    if not isinstance(item, dict):
      continue
    normalized.append(
      {
        "title": str(item.get("title") or "").strip(),
        "url": str(item.get("url") or "").strip(),
        "snippet": str(item.get("content") or item.get("snippet") or "").strip(),
        "score": item.get("score"),
        "provider": PROVIDER_TAVILY,
        "fetched_at": fetched_at,
        "query": query,
      },
    )
  return normalized


def _match_domain(domain: str, suffix: str) -> bool:
  return domain == suffix or domain.endswith(f".{suffix}")


def _looks_like_ir_official(source_url: str, domain: str) -> bool:
  lower_url = str(source_url or "").lower()
  if any(hint in lower_url for hint in IR_PATH_HINTS):
    return True
  if domain.endswith(".co.jp") or domain.endswith(".com"):
    if any(part in lower_url for part in ("/ir/", "/investor", "investor-relations")):
      return True
  return False


def classify_source_quality(source_url: str, *, title: str = "", snippet: str = "") -> dict[str, str]:
  domain = extract_source_domain(source_url)
  if not domain:
    return {
      "source_domain": "",
      "source_quality": "unknown",
      "source_category": "search_result",
      "caveat": "source_url is missing; treat as unverified signal candidate.",
    }

  if domain in DISCLOSURE_PLATFORM_DOMAINS or any(_match_domain(domain, item) for item in DISCLOSURE_PLATFORM_DOMAINS):
    return {
      "source_domain": domain,
      "source_quality": "high",
      "source_category": "disclosure_platform",
      "caveat": "Disclosure platform domain candidate; document-level verification required.",
    }

  if domain in HIGH_QUALITY_DOMAINS or any(_match_domain(domain, item) for item in HIGH_QUALITY_DOMAINS):
    if domain in PUBLIC_FUNDING_DOMAINS:
      category = "public_funding"
    elif domain in NATIONAL_PROJECT_DOMAINS:
      category = "national_project"
    else:
      category = "government"
    return {
      "source_domain": domain,
      "source_quality": "high",
      "source_category": category,
      "caveat": "Public or government source domain; still requires human review for linkage.",
    }

  if domain.endswith(".go.jp") or _match_domain(domain, "go.jp"):
    category = "local_government" if any(h in domain for h in LOCAL_GOVERNMENT_HINTS) else "government"
    return {
      "source_domain": domain,
      "source_quality": "high",
      "source_category": category,
      "caveat": "Government domain; verify page relevance before use.",
    }

  if domain.endswith(".ac.jp") or domain.endswith(".edu"):
    return {
      "source_domain": domain,
      "source_quality": "medium_high",
      "source_category": "university",
      "caveat": "University official domain candidate; confirm publication context.",
    }

  if _looks_like_ir_official(source_url, domain):
    return {
      "source_domain": domain,
      "source_quality": "medium_high",
      "source_category": "ir_official",
      "caveat": "Company IR page candidate; verify document type and fiscal period.",
    }

  if domain.endswith(".co.jp") or domain.endswith(".com") or domain.endswith(".corp"):
    if not any(hint in domain for hint in LOW_QUALITY_HINTS):
      return {
        "source_domain": domain,
        "source_quality": "medium_high",
        "source_category": "ir_official" if "news" in str(source_url).lower() else "company_official",
        "caveat": "Company domain candidate; verify official press release or IR page.",
      }

  if any(hint in domain for hint in LOW_QUALITY_HINTS):
    category = "job_board" if any(j in domain for j in JOB_BOARD_HINTS) else "social"
    if "blog" in domain or "medium.com" in domain or "note.com" in domain:
      category = "blog"
    return {
      "source_domain": domain,
      "source_quality": "low",
      "source_category": category,
      "caveat": "Low-trust domain; use only as weak signal candidate.",
    }

  if any(hint in domain for hint in LOCAL_NEWS_HINTS):
    return {
      "source_domain": domain,
      "source_quality": "medium",
      "source_category": "local_news",
      "caveat": "Local or regional news candidate; verify date and entity linkage.",
    }

  return {
    "source_domain": domain,
    "source_quality": "medium",
    "source_category": "industry_media",
    "caveat": "Third-party media candidate; prefer official or primary source verification.",
  }


def build_global_web_retrieval_preview(
  search_plan: dict[str, Any],
  *,
  max_query_count: int | None = None,
  verification_limit: int = DEFAULT_VERIFICATION_LIMIT,
  summary_top_n: int = DEFAULT_SUMMARY_TOP_N,
) -> dict[str, Any]:
  global_web_plan = dict(search_plan.get("global_web_plan", {}) or {})
  countries = list(global_web_plan.get("countries", []) or [])
  country_map = {
    str(country.get("country_region_code", "") or "").strip().upper(): dict(country)
    for country in countries
    if isinstance(country, dict)
  }
  enabled_queries = [
    dict(query)
    for query in list(global_web_plan.get("queries", []) or [])
    if isinstance(query, dict) and query.get("enabled") and not str(query.get("duplicate_of", "") or "").strip()
  ]
  enabled_queries.sort(key=lambda item: (str(item.get("priority", "") or ""), str(item.get("query_id", "") or "")))
  query_cap = _normalize_positive_int(max_query_count, len(enabled_queries) or 1)
  selected_queries: list[dict[str, Any]] = []
  for query in enabled_queries[:query_cap]:
    country_code = str(query.get("country_region_code", "") or "").strip().upper()
    country = country_map.get(country_code, {})
    selected_queries.append(
      {
        **query,
        "preferred_domains": list(country.get("preferred_domains", []) or []),
        "excluded_domains": list(country.get("excluded_domains", []) or []),
        "official_source_priority": bool(country.get("official_source_priority", False)),
        "english_fallback_enabled": bool(country.get("english_fallback_enabled", False)),
      }
    )

  request = {
    "provider_primary": PROVIDER_TAVILY,
    "provider_fallback": PROVIDER_GOOGLE_GROUNDING,
    "queries": selected_queries,
    "verification_limit": min(_normalize_positive_int(verification_limit, DEFAULT_VERIFICATION_LIMIT), MAX_VERIFICATION_LIMIT),
    "summary_top_n": min(_normalize_positive_int(summary_top_n, DEFAULT_SUMMARY_TOP_N), MAX_VERIFICATION_LIMIT),
    "target_companies": list(global_web_plan.get("target_companies", []) or []),
    "time_range": str(global_web_plan.get("time_range", "12m") or "12m"),
    "record_stage": "staged",
    "retrieval_mode": "real",
    "execution_enabled": True,
  }
  validation_rows = validate_global_web_retrieval_request(request)
  return {
    "request": request,
    "selected_query_ids": [str(query.get("query_id", "") or "") for query in selected_queries],
    "validation_rows": validation_rows,
    "query_count": len(selected_queries),
    "verification_limit": request["verification_limit"],
    "summary_top_n": request["summary_top_n"],
  }


def validate_global_web_retrieval_request(request: dict[str, Any]) -> list[dict[str, str]]:
  rows: list[dict[str, str]] = []
  queries = list(request.get("queries", []) or [])
  if not queries:
    rows.append({"status": "error", "message": "実行対象の Global Web query がありません。"})
  if int(request.get("verification_limit", 0) or 0) <= 0:
    rows.append({"status": "error", "message": "verification_limit は 1 以上である必要があります。"})
  if int(request.get("summary_top_n", 0) or 0) <= 0:
    rows.append({"status": "error", "message": "summary_top_n は 1 以上である必要があります。"})
  for query in queries:
    query_id = str(query.get("query_id", "") or "").strip()
    if not query_id:
      rows.append({"status": "error", "message": "Global Web query に query_id がありません。"})
    if not str(query.get("query_local", "") or "").strip():
      rows.append({"status": "error", "message": f"{query_id or 'unknown'} の query_local が空です。"})
    if int(query.get("max_results", 0) or 0) <= 0:
      rows.append({"status": "error", "message": f"{query_id or 'unknown'} の max_results が不正です。"})
  if not rows:
    rows.append({"status": "ok", "message": "validation passed"})
  return rows


def execute_global_web_retrieval(
  preview: dict[str, Any],
  *,
  tavily_search_post_fn: JsonPostFn | None = None,
  tavily_extract_post_fn: JsonPostFn | None = None,
  google_grounding_fn: GoogleGroundingFn | None = None,
  allow_google_grounding: bool = True,
  sleeper: SleepFn | None = None,
  discovery_timeout_sec: int = 30,
  extract_timeout_sec: int = 60,
  rate_limit_sleep_sec: float = 0.2,
) -> dict[str, Any]:
  assert_external_execution_allowed("tavily_execute")
  request = dict(preview.get("request", {}) or {})
  validation_rows = list(preview.get("validation_rows", []) or [])
  retrieval_run_id = _build_retrieval_run_id()
  if any(str(row.get("status", "") or "") == "error" for row in validation_rows):
    return _blocked_web_result(
      request,
      retrieval_run_id,
      validation_rows,
      provider_status="validation_error",
      error_message="global web retrieval validation error",
    )

  sleep_fn = sleeper or time.sleep
  discovery_rows: list[dict[str, Any]] = []
  provider_log: list[dict[str, Any]] = []
  discovery_errors: list[str] = []
  search_post = tavily_search_post_fn or _default_tavily_json_post
  extract_post = tavily_extract_post_fn or _default_tavily_json_post
  grounding_post = google_grounding_fn or _default_google_grounding_verify

  for query in list(request.get("queries", []) or []):
    discovery_pack = _run_discovery_for_query(
      dict(query),
      retrieval_run_id=retrieval_run_id,
      search_post=search_post,
      timeout_sec=discovery_timeout_sec,
      provider_log=provider_log,
    )
    discovery_rows.extend(discovery_pack["rows"])
    discovery_errors.extend(discovery_pack["errors"])
    if rate_limit_sleep_sec > 0:
      sleep_fn(rate_limit_sleep_sec)

  deduped_discovery_rows = _dedupe_discovery_rows(discovery_rows)
  verification_limit = min(int(request.get("verification_limit", DEFAULT_VERIFICATION_LIMIT) or DEFAULT_VERIFICATION_LIMIT), MAX_VERIFICATION_LIMIT)
  verification_candidates = _select_verification_candidates(deduped_discovery_rows, verification_limit)
  verification_rows: list[dict[str, Any]] = []
  verification_errors: list[str] = []

  for candidate in verification_candidates:
    verification = _verify_candidate(
      dict(candidate),
      extract_post=extract_post,
      grounding_post=grounding_post,
      allow_google_grounding=allow_google_grounding,
      timeout_sec=extract_timeout_sec,
      provider_log=provider_log,
    )
    verification_rows.append(verification)
    if verification.get("error"):
      verification_errors.append(str(verification.get("error")))
    if rate_limit_sleep_sec > 0:
      sleep_fn(rate_limit_sleep_sec)

  verification_map = {
    _candidate_key(row): row
    for row in verification_rows
  }
  normalized_rows = [
    _normalize_final_candidate(
      row,
      verification_map.get(_candidate_key(row), {}),
      target_companies=list(request.get("target_companies", []) or []),
      retrieval_run_id=retrieval_run_id,
      record_stage=str(request.get("record_stage", "staged") or "staged"),
      retrieval_mode=str(request.get("retrieval_mode", "real") or "real"),
    )
    for row in deduped_discovery_rows
  ]
  normalized_rows = _apply_same_story_groups(normalized_rows)
  normalized_rows = _apply_japanese_summaries(normalized_rows, top_n=int(request.get("summary_top_n", DEFAULT_SUMMARY_TOP_N) or DEFAULT_SUMMARY_TOP_N))

  errors = discovery_errors + verification_errors
  provider_status = "success"
  if errors and normalized_rows:
    provider_status = "partial_success"
  elif errors:
    provider_status = "error"

  return {
    "provider": PROVIDER_TAVILY,
    "query_count": len(list(request.get("queries", []) or [])),
    "retrieval_run_id": retrieval_run_id,
    "provider_status": provider_status,
    "retrieval_mode": str(request.get("retrieval_mode", "real") or "real"),
    "record_stage": str(request.get("record_stage", "staged") or "staged"),
    "rows_retrieved": len(normalized_rows),
    "rows": normalized_rows,
    "discovery_rows": deduped_discovery_rows,
    "verification_rows": verification_rows,
    "provider_log": provider_log,
    "verification_limit": verification_limit,
    "summary_top_n": int(request.get("summary_top_n", DEFAULT_SUMMARY_TOP_N) or DEFAULT_SUMMARY_TOP_N),
    "error": errors[0] if errors else None,
    "validation_rows": validation_rows,
  }


def save_global_web_retrieval_artifacts(
  preview: dict[str, Any],
  retrieval_result: dict[str, Any],
  *,
  base_dir: Path | None = None,
) -> dict[str, Path]:
  dirs = ensure_v9_run_dirs(base_dir)
  runs_dir = dirs["root"] / "web_company_retrieval_runs"
  runs_dir.mkdir(parents=True, exist_ok=True)
  run_id = str(retrieval_result.get("retrieval_run_id", "") or "").strip() or _build_retrieval_run_id()
  target_dir = runs_dir / run_id
  target_dir.mkdir(parents=True, exist_ok=True)

  plan_path = target_dir / "global_web_query_plan.json"
  discovery_path = target_dir / "global_web_discovery.json"
  verification_path = target_dir / "global_web_verification.json"
  staged_json_path = target_dir / "web_company_candidates_staged.json"
  staged_csv_path = target_dir / "web_company_candidates_staged.csv"
  provider_log_path = target_dir / "global_web_provider_log.json"
  validation_path = target_dir / "global_web_query_validation.csv"

  plan_path.write_text(json.dumps(preview.get("request", {}), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  discovery_path.write_text(json.dumps(retrieval_result.get("discovery_rows", []), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  verification_path.write_text(json.dumps(retrieval_result.get("verification_rows", []), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  staged_json_path.write_text(json.dumps({
    "retrieval_run_id": retrieval_result.get("retrieval_run_id", ""),
    "provider_status": retrieval_result.get("provider_status", ""),
    "rows": retrieval_result.get("rows", []),
  }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  staged_csv_path.write_text(build_web_company_candidates_csv(list(retrieval_result.get("rows", []) or [])), encoding="utf-8")
  provider_log_path.write_text(json.dumps({
    "retrieval_run_id": retrieval_result.get("retrieval_run_id", ""),
    "provider_status": retrieval_result.get("provider_status", ""),
    "provider_log": retrieval_result.get("provider_log", []),
    "error": retrieval_result.get("error"),
  }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  validation_path.write_text(build_global_web_validation_csv(list(preview.get("validation_rows", []) or [])), encoding="utf-8")
  return {
    "run_dir": target_dir,
    "plan_json": plan_path,
    "discovery_json": discovery_path,
    "verification_json": verification_path,
    "staged_json": staged_json_path,
    "staged_csv": staged_csv_path,
    "provider_log_json": provider_log_path,
    "validation_csv": validation_path,
  }


def build_web_company_candidates_csv(rows: list[dict[str, Any]]) -> str:
  fieldnames = [
    "candidate_id",
    "query_id",
    "country_region",
    "web_intent",
    "result_bucket",
    "original_title",
    "original_snippet",
    "original_language",
    "source_url",
    "canonical_url",
    "event_type",
    "organization",
    "source_quality",
    "content_access",
    "content_hash",
    "same_story_group",
    "summary_ja",
    "retrieval_run_id",
    "provider_status",
    "record_stage",
    "retrieval_mode",
  ]
  buffer = StringIO()
  writer = csv.DictWriter(buffer, fieldnames=fieldnames)
  writer.writeheader()
  for row in rows:
    writer.writerow({field: row.get(field, "") for field in fieldnames})
  return buffer.getvalue()


def build_global_web_validation_csv(rows: list[dict[str, str]]) -> str:
  buffer = StringIO()
  writer = csv.DictWriter(buffer, fieldnames=["status", "message"])
  writer.writeheader()
  for row in rows:
    writer.writerow({
      "status": str(row.get("status", "") or ""),
      "message": str(row.get("message", "") or ""),
    })
  return buffer.getvalue()


def _run_discovery_for_query(
  query: dict[str, Any],
  *,
  retrieval_run_id: str,
  search_post: JsonPostFn,
  timeout_sec: int,
  provider_log: list[dict[str, Any]],
) -> dict[str, Any]:
  rows: list[dict[str, Any]] = []
  errors: list[str] = []
  query_id = str(query.get("query_id", "") or "")
  local_query = str(query.get("query_local", "") or "").strip()
  fallback_query = str(query.get("query_english_fallback", "") or "").strip()
  preferred_domains = list(query.get("preferred_domains", []) or [])
  excluded_domains = list(query.get("excluded_domains", []) or [])

  local_result = _run_tavily_discovery(
    local_query,
    include_domains=preferred_domains if bool(query.get("official_source_priority")) else None,
    exclude_domains=excluded_domains,
    max_results=int(query.get("max_results", 5) or 5),
    timeout_sec=timeout_sec,
    search_post=search_post,
  )
  provider_log.append({
    "stage": "discovery",
    "query_id": query_id,
    "variant": "local",
    "provider": PROVIDER_TAVILY,
    "status": local_result.get("status"),
    "result_count": len(list(local_result.get("rows", []) or [])),
    "error": local_result.get("error"),
  })
  rows.extend(_attach_discovery_metadata(local_result.get("rows", []), query, retrieval_run_id, "local"))
  if local_result.get("error"):
    errors.append(f"{query_id}: {local_result.get('error')}")

  should_fallback = (
    bool(query.get("english_fallback_enabled"))
    and str(query.get("fallback_execution_mode", "") or "") == "result_shortage_only"
    and bool(fallback_query)
    and (len(list(local_result.get("rows", []) or [])) < DISCOVERY_SHORTAGE_THRESHOLD or local_result.get("error"))
  )
  if should_fallback:
    fallback_result = _run_tavily_discovery(
      fallback_query,
      include_domains=preferred_domains if bool(query.get("official_source_priority")) else None,
      exclude_domains=excluded_domains,
      max_results=int(query.get("max_results", 5) or 5),
      timeout_sec=timeout_sec,
      search_post=search_post,
    )
    provider_log.append({
      "stage": "discovery",
      "query_id": query_id,
      "variant": "english_fallback",
      "provider": PROVIDER_TAVILY,
      "status": fallback_result.get("status"),
      "result_count": len(list(fallback_result.get("rows", []) or [])),
      "error": fallback_result.get("error"),
    })
    rows.extend(_attach_discovery_metadata(fallback_result.get("rows", []), query, retrieval_run_id, "english_fallback"))
    if fallback_result.get("error"):
      errors.append(f"{query_id} fallback: {fallback_result.get('error')}")

  return {"rows": rows, "errors": errors}


def _run_tavily_discovery(
  query_text: str,
  *,
  include_domains: list[str] | None,
  exclude_domains: list[str] | None,
  max_results: int,
  timeout_sec: int,
  search_post: JsonPostFn,
) -> dict[str, Any]:
  if not query_text.strip():
    return {"status": "error", "rows": [], "error": "empty_query"}
  payload = build_tavily_search_payload(
    query=query_text,
    max_results=max(max_results, 1),
    include_domains=include_domains,
    exclude_domains=exclude_domains,
  )
  raw = search_post(
    url=TAVILY_SEARCH_URL,
    payload=payload,
    api_key_env="TAVILY_API_KEY",
    timeout_sec=timeout_sec,
  )
  if raw.get("error"):
    return {"status": "error", "rows": [], "error": str(raw.get("error"))}
  rows = normalize_tavily_search_response(
    raw,
    query=query_text,
    fetched_at=datetime.now().astimezone().isoformat(timespec="seconds"),
  )
  return {"status": "ok", "rows": rows, "error": None}


def _attach_discovery_metadata(
  rows: list[dict[str, Any]],
  query: dict[str, Any],
  retrieval_run_id: str,
  variant: str,
) -> list[dict[str, Any]]:
  attached: list[dict[str, Any]] = []
  for row in rows:
    source_url = str(row.get("url", "") or "").strip()
    title = str(row.get("title", "") or "").strip()
    snippet = str(row.get("snippet", "") or "").strip()
    quality = classify_source_quality(source_url, title=title, snippet=snippet)
    attached.append(
      {
        "candidate_id": _candidate_id(
          str(query.get("query_id", "") or ""),
          canonical_url=_canonicalize_url(source_url),
          title=title,
        ),
        "query_id": str(query.get("query_id", "") or ""),
        "query_text": str(row.get("query", "") or ""),
        "country_region": str(query.get("country_region_code", "") or ""),
        "web_intent": str(query.get("web_intent", "") or ""),
        "result_bucket": str(query.get("result_bucket", "") or ""),
        "priority": str(query.get("priority", "") or ""),
        "source_url": source_url,
        "original_title": title,
        "original_snippet": snippet,
        "original_language": _detect_language(title + "\n" + snippet),
        "provider": PROVIDER_TAVILY,
        "provider_status": "success",
        "score": row.get("score"),
        "retrieval_run_id": retrieval_run_id,
        "discovery_variant": variant,
        "source_quality": str(quality.get("source_quality", "") or "unknown"),
        "source_category": str(quality.get("source_category", "") or "search_result"),
        "official_source_priority": bool(query.get("official_source_priority", False)),
      }
    )
  return attached


def _select_verification_candidates(rows: list[dict[str, Any]], verification_limit: int) -> list[dict[str, Any]]:
  quality_rank = {"high": 0, "medium_high": 1, "medium": 2, "unknown": 3, "low": 4}
  return sorted(
    rows,
    key=lambda row: (
      0 if bool(row.get("official_source_priority")) else 1,
      quality_rank.get(str(row.get("source_quality", "") or "unknown"), 3),
      -_safe_float(row.get("score")),
      str(row.get("query_id", "") or ""),
    ),
  )[:max(verification_limit, 0)]


def _verify_candidate(
  candidate: dict[str, Any],
  *,
  extract_post: JsonPostFn,
  grounding_post: GoogleGroundingFn,
  allow_google_grounding: bool,
  timeout_sec: int,
  provider_log: list[dict[str, Any]],
) -> dict[str, Any]:
  url = str(candidate.get("source_url", "") or "").strip()
  if not url:
    return {
      "candidate_id": candidate.get("candidate_id"),
      "content_access": "unavailable",
      "verification_provider": "",
      "error": "missing_url",
      "summary_ja": "",
    }

  if _is_wechat_url(url):
    provider_log.append({
      "stage": "verification",
      "candidate_id": candidate.get("candidate_id"),
      "provider": PROVIDER_TAVILY,
      "status": "human_review_required",
      "url": url,
      "error": "wechat_best_effort",
    })
    return {
      "candidate_id": candidate.get("candidate_id"),
      "content_access": "human_review_required",
      "verification_provider": PROVIDER_TAVILY,
      "verified_text": "",
      "canonical_url": _canonicalize_url(url),
      "error": "wechat_best_effort",
      "grounding_summary_ja": "",
    }

  extract_payload = build_tavily_extract_payload([url])
  extract_raw = extract_post(
    url=TAVILY_EXTRACT_URL,
    payload=extract_payload,
    api_key_env="TAVILY_API_KEY",
    timeout_sec=timeout_sec,
  )
  verified_text, content_access, extract_error = _extract_verified_text(extract_raw)
  provider_log.append({
    "stage": "verification",
    "candidate_id": candidate.get("candidate_id"),
    "provider": PROVIDER_TAVILY,
    "status": "ok" if not extract_error else "error",
    "url": url,
    "content_access": content_access,
    "error": extract_error,
  })

  grounding_summary = ""
  verification_provider = PROVIDER_TAVILY
  final_error = extract_error
  if allow_google_grounding and content_access in {"partial", "unavailable"}:
    grounding_result = grounding_post({
      "source_url": url,
      "title": candidate.get("original_title", ""),
      "snippet": candidate.get("original_snippet", ""),
      "country_region": candidate.get("country_region", ""),
      "web_intent": candidate.get("web_intent", ""),
    })
    provider_log.append({
      "stage": "verification",
      "candidate_id": candidate.get("candidate_id"),
      "provider": PROVIDER_GOOGLE_GROUNDING,
      "status": "ok" if not grounding_result.get("error") else "error",
      "url": url,
      "error": grounding_result.get("error"),
    })
    if not grounding_result.get("error"):
      grounding_summary = str(grounding_result.get("summary_ja", "") or "")
      verification_provider = f"{PROVIDER_TAVILY}+{PROVIDER_GOOGLE_GROUNDING}"
      final_error = None
      if content_access == "unavailable":
        content_access = str(grounding_result.get("content_access", "partial") or "partial")
    else:
      final_error = final_error or str(grounding_result.get("error"))

  return {
    "candidate_id": candidate.get("candidate_id"),
    "content_access": content_access if content_access in CONTENT_ACCESS_VALUES else "unavailable",
    "verification_provider": verification_provider,
    "verified_text": verified_text,
    "canonical_url": _canonicalize_url(url),
    "error": final_error,
    "grounding_summary_ja": grounding_summary,
  }


def _normalize_final_candidate(
  discovery_row: dict[str, Any],
  verification_row: dict[str, Any],
  *,
  target_companies: list[str],
  retrieval_run_id: str,
  record_stage: str,
  retrieval_mode: str,
) -> dict[str, Any]:
  title = str(discovery_row.get("original_title", "") or "").strip()
  snippet = str(discovery_row.get("original_snippet", "") or "").strip()
  source_url = str(discovery_row.get("source_url", "") or "").strip()
  canonical_url = str(verification_row.get("canonical_url", "") or _canonicalize_url(source_url))
  verified_text = str(verification_row.get("verified_text", "") or "")
  language = str(discovery_row.get("original_language", "") or _detect_language(title + "\n" + snippet))
  source_quality = str(discovery_row.get("source_quality", "") or "unknown")
  event_type = _infer_event_type(
    web_intent=str(discovery_row.get("web_intent", "") or ""),
    title=title,
    snippet=snippet,
  )
  organization = _infer_organization(title, snippet, canonical_url, target_companies)
  summary_seed = str(verification_row.get("grounding_summary_ja", "") or "")
  normalized_text = "\n".join(part for part in [title, snippet, verified_text] if part)
  content_hash = hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()
  content_access = str(verification_row.get("content_access", "unavailable") or "unavailable")
  provider_status = "success" if not verification_row.get("error") else ("partial_success" if verified_text or summary_seed else "unavailable")
  return {
    "candidate_id": str(discovery_row.get("candidate_id", "") or ""),
    "query_id": str(discovery_row.get("query_id", "") or ""),
    "country_region": str(discovery_row.get("country_region", "") or ""),
    "web_intent": str(discovery_row.get("web_intent", "") or ""),
    "result_bucket": str(discovery_row.get("result_bucket", "") or ""),
    "original_title": title,
    "original_snippet": snippet,
    "original_language": language,
    "source_url": source_url,
    "canonical_url": canonical_url,
    "event_type": event_type,
    "organization": organization,
    "source_quality": source_quality,
    "source_category": str(discovery_row.get("source_category", "") or ""),
    "content_access": content_access,
    "content_hash": content_hash,
    "same_story_group": "",
    "summary_ja": summary_seed,
    "query_score": _safe_float(discovery_row.get("score")),
    "verification_provider": str(verification_row.get("verification_provider", "") or ""),
    "verified_text": verified_text,
    "retrieval_run_id": retrieval_run_id,
    "provider_status": provider_status,
    "record_stage": record_stage,
    "retrieval_mode": retrieval_mode,
  }


def _apply_same_story_groups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
  group_map: dict[str, str] = {}
  story_index = 0
  for row in rows:
    key = _story_group_key(row)
    if key not in group_map:
      story_index += 1
      group_map[key] = f"story_{story_index:03d}"
    row["same_story_group"] = group_map[key]
  return rows


def _apply_japanese_summaries(rows: list[dict[str, Any]], *, top_n: int) -> list[dict[str, Any]]:
  quality_rank = {"high": 0, "medium_high": 1, "medium": 2, "unknown": 3, "low": 4}
  ordered = sorted(
    rows,
    key=lambda row: (
      quality_rank.get(str(row.get("source_quality", "") or "unknown"), 3),
      0 if str(row.get("content_access", "") or "") == "full" else 1,
      -_safe_float(row.get("query_score")),
    ),
  )
  selected_ids = {
    str(row.get("candidate_id", "") or "")
    for row in ordered[:max(top_n, 0)]
  }
  for row in rows:
    if str(row.get("candidate_id", "") or "") in selected_ids:
      if not str(row.get("summary_ja", "") or "").strip():
        row["summary_ja"] = _build_summary_ja(row)
    else:
      row["summary_ja"] = ""
  return rows


def _build_summary_ja(row: dict[str, Any]) -> str:
  title = str(row.get("original_title", "") or "").strip()
  org = str(row.get("organization", "") or "").strip() or "組織不明"
  country = str(row.get("country_region", "") or "").strip() or "地域不明"
  event_type = str(row.get("event_type", "") or "").strip() or "web_signal"
  snippet = str(row.get("original_snippet", "") or "").strip()
  if _detect_language(title + "\n" + snippet) == "ja":
    body = snippet[:90] if snippet else "要原典確認"
    return f"{org} / {country} / {event_type}: {title}。{body}"
  body = snippet[:90] if snippet else "要原典確認"
  return f"{org} に関する {event_type} 候補（{country}）。原題: {title}。{body}"


def _dedupe_discovery_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
  deduped: list[dict[str, Any]] = []
  seen: set[str] = set()
  for row in rows:
    key = _candidate_key(row)
    if key in seen:
      continue
    seen.add(key)
    deduped.append(row)
  return deduped


def _candidate_key(row: dict[str, Any]) -> str:
  return str(row.get("candidate_id", "") or _candidate_id(str(row.get("query_id", "") or ""), canonical_url=str(row.get("canonical_url", "") or _canonicalize_url(str(row.get("source_url", "") or ""))), title=str(row.get("original_title", "") or "")))


def _candidate_id(query_id: str, *, canonical_url: str, title: str) -> str:
  base = f"{query_id}|{canonical_url}|{title.strip().lower()}"
  return "wcc_" + hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def _canonicalize_url(url: str) -> str:
  text = str(url or "").strip()
  if not text:
    return ""
  parsed = urllib.parse.urlparse(text if "://" in text else f"https://{text}")
  scheme = (parsed.scheme or "https").lower()
  host = (parsed.netloc or parsed.path or "").lower()
  path = parsed.path if parsed.netloc else ""
  if host.startswith("www."):
    host = host[4:]
  clean_query_pairs = []
  for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=False):
    if key.lower() in _TRACKING_QUERY_KEYS:
      continue
    clean_query_pairs.append((key, value))
  clean_query = urllib.parse.urlencode(clean_query_pairs)
  normalized_path = path or "/"
  if normalized_path != "/" and normalized_path.endswith("/"):
    normalized_path = normalized_path[:-1]
  return urllib.parse.urlunparse((scheme, host, normalized_path, "", clean_query, ""))


def _extract_verified_text(raw: dict[str, Any]) -> tuple[str, str, str | None]:
  if raw.get("error"):
    return "", "unavailable", str(raw.get("error"))
  results = list(raw.get("results", []) or [])
  if not results:
    return "", "unavailable", "no_extract_results"
  first = dict(results[0] or {})
  text = str(first.get("raw_content") or first.get("content") or first.get("snippet") or "").strip()
  if len(text) >= 600:
    return text, "full", None
  if text:
    return text, "partial", None
  return "", "unavailable", "empty_extract_text"


def _infer_event_type(*, web_intent: str, title: str, snippet: str) -> str:
  text = (title + "\n" + snippet).lower()
  if web_intent:
    return web_intent
  if any(token in text for token in ("investment", "設備投資", "factory", "production")):
    return "investment_production"
  if any(token in text for token in ("joint", "partnership", "共同研究", "alliance")):
    return "partnership_project"
  if any(token in text for token in ("regulation", "standard", "規制", "標準")):
    return "regulation_standard"
  if any(token in text for token in ("recruit", "hiring", "採用")):
    return "organization_recruitment"
  if any(token in text for token in ("launch", "product", "commercial", "製品")):
    return "product_commercialization"
  return "research_development"


def _infer_organization(title: str, snippet: str, canonical_url: str, target_companies: list[str]) -> str:
  body = f"{title}\n{snippet}"
  for company in target_companies:
    company_text = str(company or "").strip()
    if company_text and company_text.lower() in body.lower():
      return company_text
  domain = extract_source_domain(canonical_url)
  if not domain:
    return ""
  parts = [part for part in domain.split(".") if part and part not in {"com", "co", "jp", "org", "net", "go", "ac", "www"}]
  if not parts:
    return domain
  return parts[0].replace("-", " ").replace("_", " ").title()


def _story_group_key(row: dict[str, Any]) -> str:
  title_tokens = _normalize_story_text(str(row.get("original_title", "") or ""))
  return "|".join([
    str(row.get("country_region", "") or ""),
    str(row.get("organization", "") or "").lower(),
    str(row.get("event_type", "") or ""),
    title_tokens,
  ])


def _normalize_story_text(text: str) -> str:
  tokens = [match.group(0).lower() for match in _WORD_PATTERN.finditer(str(text or ""))]
  return " ".join(tokens[:12])


def _detect_language(text: str) -> str:
  value = str(text or "")
  if _JP_CHAR_PATTERN.search(value):
    return "ja"
  if any("a" <= char.lower() <= "z" for char in value):
    return "en"
  return "unknown"


def _is_wechat_url(url: str) -> bool:
  domain = extract_source_domain(url)
  return "wechat" in domain or "weixin" in domain or "mp.weixin.qq.com" in url


def _default_tavily_json_post(
  *,
  url: str,
  payload: dict[str, Any],
  api_key_env: str,
  timeout_sec: int,
) -> dict[str, Any]:
  api_key = os.environ.get(api_key_env, "").strip()
  if not api_key:
    return {"error": "missing_api_key"}
  data = json.dumps(payload).encode("utf-8")
  request = urllib.request.Request(
    url,
    data=data,
    headers={
      "Content-Type": "application/json",
      "Authorization": f"Bearer {api_key}",
    },
    method="POST",
  )
  try:
    with urllib.request.urlopen(request, timeout=timeout_sec) as response:
      parsed = json.loads(response.read().decode("utf-8"))
      return scrub_sensitive_payload(parsed) if isinstance(parsed, dict) else {"error": "unexpected_response_shape"}
  except urllib.error.HTTPError as exc:
    detail = exc.read().decode("utf-8", errors="replace")
    if api_key and api_key in detail:
      detail = detail.replace(api_key, "[redacted]")
    return {"error": f"http_{exc.code}", "detail": detail[:500]}
  except urllib.error.URLError as exc:
    return {"error": "url_error", "detail": str(exc.reason)}
  except (json.JSONDecodeError, TimeoutError, OSError) as exc:
    return {"error": "request_failed", "detail": str(exc)}


def _default_google_grounding_verify(target: dict[str, Any]) -> dict[str, Any]:
  api_key = (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()
  if not api_key:
    return {"error": "missing_google_api_key"}
  try:
    from google import genai
    from google.genai import types
  except ImportError:
    return {"error": "google_genai_not_installed"}

  prompt = (
    "You are verifying a web/company signal candidate. "
    "Use Google Search grounding if available and return strict JSON with keys: "
    "summary_ja, content_access, official_hint. "
    f"Target URL: {target.get('source_url', '')}\n"
    f"Title: {target.get('title', '')}\n"
    f"Snippet: {target.get('snippet', '')}\n"
  )
  try:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
      model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
      contents=prompt,
      config=types.GenerateContentConfig(
        response_mime_type="application/json",
        tools=[types.Tool(google_search=types.GoogleSearch())],
      ),
    )
    text = getattr(response, "text", None) or ""
    if not text and getattr(response, "candidates", None):
      parts = response.candidates[0].content.parts
      text = "".join(getattr(part, "text", "") for part in parts)
    payload = json.loads(text) if text.strip() else {}
    content_access = str(payload.get("content_access", "partial") or "partial")
    if content_access not in CONTENT_ACCESS_VALUES:
      content_access = "partial"
    return {
      "summary_ja": str(payload.get("summary_ja", "") or ""),
      "content_access": content_access,
      "official_hint": str(payload.get("official_hint", "") or ""),
    }
  except Exception as exc:  # noqa: BLE001
    return {"error": str(exc)}


def _blocked_web_result(
  request: dict[str, Any],
  retrieval_run_id: str,
  validation_rows: list[dict[str, str]],
  *,
  provider_status: str,
  error_message: str,
) -> dict[str, Any]:
  return {
    "provider": PROVIDER_TAVILY,
    "query_count": len(list(request.get("queries", []) or [])),
    "retrieval_run_id": retrieval_run_id,
    "provider_status": provider_status,
    "retrieval_mode": str(request.get("retrieval_mode", "real") or "real"),
    "record_stage": str(request.get("record_stage", "staged") or "staged"),
    "rows_retrieved": 0,
    "rows": [],
    "discovery_rows": [],
    "verification_rows": [],
    "provider_log": [],
    "verification_limit": int(request.get("verification_limit", DEFAULT_VERIFICATION_LIMIT) or DEFAULT_VERIFICATION_LIMIT),
    "summary_top_n": int(request.get("summary_top_n", DEFAULT_SUMMARY_TOP_N) or DEFAULT_SUMMARY_TOP_N),
    "error": error_message,
    "validation_rows": validation_rows,
  }


def _build_retrieval_run_id() -> str:
  return "web_company_retrieval_" + datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")


def _normalize_positive_int(value: Any, default: int) -> int:
  try:
    normalized = int(value)
  except (TypeError, ValueError):
    normalized = int(default)
  return max(normalized, 1)


def _safe_float(value: Any) -> float:
  try:
    return float(value)
  except (TypeError, ValueError):
    return 0.0


__all__ = [
  "CONTENT_ACCESS_VALUES",
  "DEFAULT_SUMMARY_TOP_N",
  "DEFAULT_VERIFICATION_LIMIT",
  "DISCOVERY_SHORTAGE_THRESHOLD",
  "PROVIDER_GOOGLE_GROUNDING",
  "PROVIDER_TAVILY",
  "build_global_web_retrieval_preview",
  "build_global_web_validation_csv",
  "build_web_company_candidates_csv",
  "execute_global_web_retrieval",
  "save_global_web_retrieval_artifacts",
  "validate_global_web_retrieval_request",
]
