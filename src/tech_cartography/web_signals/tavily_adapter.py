"""Tavily Search / Extract adapter for Web Signals (Phase 23.1)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from tech_cartography.web_signals.schema import (
  DEFAULT_CAVEAT,
  apply_validation_rules,
  extract_source_domain,
  new_signal_id,
  utc_now_iso,
)
from tech_cartography.web_signals.signal_classifier import (
  DISCLOSURE_PLATFORM_DOMAINS,
  classify_signal_type,
  infer_disclosure_type_safe,
  looks_like_ir_disclosure,
)
from tech_cartography.web_signals.source_quality import classify_source_quality
from tech_cartography.web_signals.schema import WebSignal

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
TAVILY_EXTRACT_URL = "https://api.tavily.com/extract"


def get_tavily_api_key(env_var: str = "TAVILY_API_KEY") -> str | None:
  value = os.environ.get(env_var, "").strip()
  return value or None


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


def _post_tavily(url: str, payload: dict[str, Any], api_key: str, timeout_sec: int = 60) -> dict[str, Any]:
  body = dict(payload)
  body["api_key"] = api_key
  data = json.dumps(body).encode("utf-8")
  request = urllib.request.Request(
    url,
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST",
  )
  try:
    with urllib.request.urlopen(request, timeout=timeout_sec) as response:
      raw = response.read().decode("utf-8")
      parsed = json.loads(raw)
      if isinstance(parsed, dict):
        return parsed
      return {"error": "unexpected_response_shape", "raw": parsed}
  except urllib.error.HTTPError as exc:
    detail = exc.read().decode("utf-8", errors="replace")
    return {"error": "http_error", "status": exc.code, "detail": detail}
  except urllib.error.URLError as exc:
    return {"error": "url_error", "detail": str(exc.reason)}
  except (json.JSONDecodeError, TimeoutError, OSError) as exc:
    return {"error": "request_failed", "detail": str(exc)}


def run_tavily_search(
  query: str,
  api_key: str,
  max_results: int = 5,
  include_domains: list[str] | None = None,
  exclude_domains: list[str] | None = None,
) -> dict[str, Any]:
  if not str(api_key or "").strip():
    return {"error": "missing_api_key", "detail": "TAVILY_API_KEY is not set"}
  payload = build_tavily_search_payload(
    query=query,
    max_results=max_results,
    include_domains=include_domains,
    exclude_domains=exclude_domains,
  )
  return _post_tavily(TAVILY_SEARCH_URL, payload, api_key)


def run_tavily_extract(urls: list[str], api_key: str) -> dict[str, Any]:
  if not str(api_key or "").strip():
    return {"error": "missing_api_key", "detail": "TAVILY_API_KEY is not set"}
  payload = build_tavily_extract_payload(urls)
  if not payload["urls"]:
    return {"error": "no_urls", "detail": "At least one URL is required for extract"}
  return _post_tavily(TAVILY_EXTRACT_URL, payload, api_key)


def _confidence_for_result(
  *,
  source_url: str,
  source_quality: str,
  signal_type: str,
) -> str:
  if not str(source_url or "").strip():
    return "low"
  if signal_type == "human":
    return "low"
  if source_quality == "high":
    return "medium"
  if source_quality in {"medium_high", "medium"}:
    return "medium"
  return "low"


def _next_action_for_signal(signal_type: str, source_category: str) -> str:
  if signal_type == "human":
    return "Verify identity and role linkage before use."
  if signal_type in {"ir_disclosure", "disclosure"}:
    return "Open source document and verify disclosure type and fiscal period."
  if signal_type in {"money", "national_project", "grant", "funding"}:
    return "Verify funding source page and project linkage."
  if source_category == "disclosure_platform":
    return "Confirm filing document; do not treat search snippet as verified disclosure."
  return "Review source page relevance and entity linkage."


def _build_web_signal_from_hit(
  *,
  title: str,
  source_url: str,
  snippet: str,
  query: str,
  default_signal_type: str,
  query_category: str,
  source_kind: str,
  extracted_text: str | None = None,
  extracted_evidence_sentences: list[str] | None = None,
) -> WebSignal:
  domain = extract_source_domain(source_url)
  quality = classify_source_quality(source_url, title=title, snippet=snippet)
  signal_type = classify_signal_type(
    title=title,
    snippet=snippet,
    source_url=source_url,
    default_signal_type=default_signal_type,
    query_category=query_category,
  )
  disclosure_type = None
  if signal_type in {"ir_disclosure", "disclosure"} or looks_like_ir_disclosure(title, snippet, source_url):
    signal_type = "ir_disclosure" if signal_type != "disclosure" else signal_type
    disclosure_type = infer_disclosure_type_safe(title, snippet)
    if domain in DISCLOSURE_PLATFORM_DOMAINS:
      quality = {
        **quality,
        "source_quality": "high",
        "source_category": "disclosure_platform",
      }

  confidence = _confidence_for_result(
    source_url=source_url,
    source_quality=str(quality.get("source_quality") or "unknown"),
    signal_type=signal_type,
  )
  caveat_parts = [DEFAULT_CAVEAT, str(quality.get("caveat") or "").strip()]
  caveat = " ".join(part for part in caveat_parts if part)

  signal = WebSignal(
    signal_id=new_signal_id(),
    signal_type=signal_type,
    source_title=str(title or "").strip() or "(untitled)",
    source_url=str(source_url or "").strip(),
    source_domain=str(quality.get("source_domain") or domain),
    collected_at=utc_now_iso(),
    query=query,
    raw_snippet=str(snippet or "").strip() or "(no snippet)",
    extracted_text=extracted_text,
    confidence=confidence,
    verification_status="needs_human_review",
    is_synthetic_demo=False,
    caveat=caveat,
    next_verification_action=_next_action_for_signal(signal_type, str(quality.get("source_category") or "")),
    source_kind=source_kind,
    disclosure_type=disclosure_type,
    language=None,
    extracted_evidence_sentences=list(extracted_evidence_sentences or []),
    source_quality=str(quality.get("source_quality") or "unknown"),
    source_category=str(quality.get("source_category") or "search_result"),
  )
  return apply_validation_rules(signal)


def tavily_search_results_to_web_signals(
  results: dict[str, Any],
  query: str,
  default_signal_type: str = "other",
  *,
  query_category: str = "",
) -> list[WebSignal]:
  if not isinstance(results, dict):
    return []
  if results.get("error"):
    return []

  raw_results = results.get("results")
  if not isinstance(raw_results, list):
    return []

  signals: list[WebSignal] = []
  for item in raw_results:
    if not isinstance(item, dict):
      continue
    title = str(item.get("title") or "")
    source_url = str(item.get("url") or item.get("source_url") or "")
    snippet = str(item.get("content") or item.get("snippet") or item.get("raw_content") or "")
    signals.append(
      _build_web_signal_from_hit(
        title=title,
        source_url=source_url,
        snippet=snippet,
        query=query,
        default_signal_type=default_signal_type,
        query_category=query_category,
        source_kind="tavily_search",
      ),
    )
  return signals


def tavily_extract_results_to_web_signals(
  results: dict[str, Any],
  query: str,
  default_signal_type: str = "other",
  *,
  query_category: str = "",
) -> list[WebSignal]:
  if not isinstance(results, dict):
    return []
  if results.get("error"):
    return []

  raw_results = results.get("results")
  if not isinstance(raw_results, list):
    return []

  signals: list[WebSignal] = []
  for item in raw_results:
    if not isinstance(item, dict):
      continue
    source_url = str(item.get("url") or item.get("source_url") or "")
    title = str(item.get("title") or source_url or "(extracted page)")
    extracted_text = str(item.get("raw_content") or item.get("content") or "")
    snippet = extracted_text[:500] if extracted_text else ""
    evidence = [line.strip() for line in extracted_text.splitlines() if line.strip()][:5]
    signals.append(
      _build_web_signal_from_hit(
        title=title,
        source_url=source_url,
        snippet=snippet,
        query=query,
        default_signal_type=default_signal_type,
        query_category=query_category,
        source_kind="tavily_extract",
        extracted_text=extracted_text or None,
        extracted_evidence_sentences=evidence,
      ),
    )
  return signals
