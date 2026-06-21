"""Minimal Tavily web search for live smoke test (Phase 25D)."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from tech_cartography.runtime.api_secret_config import is_secret_present
from tech_cartography.runtime.external_api_guard import check_live_tavily_smoke_allowed

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
DEFAULT_SEARCH_DEPTH = "basic"
DEFAULT_MAX_RESULTS = 3
DEFAULT_TIMEOUT_SEC = 20
MIN_MAX_RESULTS = 1
MAX_MAX_RESULTS = 3
PROVIDER = "tavily"

SAFETY_NOTICE = (
  "結果は Web Signal candidate です。事実認定・FTO・侵害・有効性判断ではありません。"
  "原典確認が必要です。"
)

_SENSITIVE_KEY_PATTERN = re.compile(r"(api[_-]?key|authorization|token|secret)", re.IGNORECASE)


def clamp_max_results(value: int | str | None) -> int:
  try:
    parsed = int(value)  # type: ignore[arg-type]
  except (TypeError, ValueError):
    parsed = DEFAULT_MAX_RESULTS
  return max(MIN_MAX_RESULTS, min(MAX_MAX_RESULTS, parsed))


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _timestamp_slug(iso_ts: str) -> str:
  return iso_ts.replace(":", "").replace("-", "")


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
  """Map Tavily API response to safe display/save records."""
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
        "provider": PROVIDER,
        "fetched_at": fetched_at,
        "query": query,
      },
    )
  return normalized


def _default_post_tavily(
  *,
  url: str,
  payload: dict[str, Any],
  api_key: str,
  timeout_sec: int,
) -> dict[str, Any]:
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
      if isinstance(parsed, dict):
        return scrub_sensitive_payload(parsed)
      return {"error": "unexpected_response_shape"}
  except urllib.error.HTTPError as exc:
    detail = exc.read().decode("utf-8", errors="replace")
    if api_key and api_key in detail:
      detail = detail.replace(api_key, "[redacted]")
    return {"error": "http_error", "status": exc.code, "detail": detail[:500]}
  except urllib.error.URLError as exc:
    return {"error": "url_error", "detail": str(exc.reason)}
  except (json.JSONDecodeError, TimeoutError, OSError) as exc:
    return {"error": "request_failed", "detail": str(exc)}


def _block_result(*, query: str, block_reason: str, message: str) -> dict[str, Any]:
  fetched_at = _utc_now_iso()
  return {
    "ok": False,
    "error": block_reason,
    "message": message,
    "query": query,
    "provider": PROVIDER,
    "fetched_at": fetched_at,
    "max_results": DEFAULT_MAX_RESULTS,
    "search_depth": DEFAULT_SEARCH_DEPTH,
    "results": [],
    "safety_notice": SAFETY_NOTICE,
    "saved_paths": {},
  }


def run_live_tavily_search_smoke(
  query: str,
  *,
  max_results: int = DEFAULT_MAX_RESULTS,
  search_depth: str = DEFAULT_SEARCH_DEPTH,
  timeout_sec: int = DEFAULT_TIMEOUT_SEC,
  login_required: bool,
  is_authenticated: bool,
  auth_role: str,
  post_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
  """Execute one small Tavily search. Never raises; never returns API keys."""
  cleaned_query = str(query or "").strip()
  if not cleaned_query:
    return _block_result(
      query="",
      block_reason="empty_query",
      message="検索クエリを入力してください。",
    )

  allowed, block_reason = check_live_tavily_smoke_allowed(
    login_required=login_required,
    is_authenticated=is_authenticated,
    auth_role=auth_role,
  )
  if not allowed:
    return _block_result(
      query=cleaned_query,
      block_reason=block_reason or "blocked",
      message=live_tavily_block_message(block_reason),
    )

  if not is_secret_present("TAVILY_API_KEY"):
    return _block_result(
      query=cleaned_query,
      block_reason="missing_keys",
      message="TAVILY_API_KEY が未設定です。",
    )

  api_key = os.environ.get("TAVILY_API_KEY", "").strip()
  bounded_max_results = clamp_max_results(max_results)
  fetched_at = _utc_now_iso()
  payload = {
    "query": cleaned_query,
    "search_depth": search_depth,
    "max_results": bounded_max_results,
    "include_answer": False,
    "include_raw_content": False,
  }

  poster = post_fn or _default_post_tavily
  raw = poster(
    url=TAVILY_SEARCH_URL,
    payload=payload,
    api_key=api_key,
    timeout_sec=timeout_sec,
  )

  if raw.get("error"):
    detail = raw.get("detail")
    if isinstance(detail, str) and api_key and api_key in detail:
      detail = detail.replace(api_key, "[redacted]")
    return {
      "ok": False,
      "error": str(raw.get("error")),
      "message": f"Tavily API エラー: {raw.get('error')}",
      "query": cleaned_query,
      "provider": PROVIDER,
      "fetched_at": fetched_at,
      "max_results": bounded_max_results,
      "search_depth": search_depth,
      "results": [],
      "safety_notice": SAFETY_NOTICE,
      "saved_paths": {},
      "detail": detail if not isinstance(detail, str) else detail[:500],
    }

  results = normalize_tavily_search_response(raw, query=cleaned_query, fetched_at=fetched_at)
  return {
    "ok": True,
    "error": None,
    "message": f"Tavily 検索完了（{len(results)} 件）",
    "query": cleaned_query,
    "provider": PROVIDER,
    "fetched_at": fetched_at,
    "max_results": bounded_max_results,
    "search_depth": search_depth,
    "results": results,
    "safety_notice": SAFETY_NOTICE,
    "saved_paths": {},
  }


def build_live_search_save_payload(result: dict[str, Any]) -> dict[str, Any]:
  return {
    "query": result.get("query"),
    "provider": result.get("provider"),
    "fetched_at": result.get("fetched_at"),
    "max_results": result.get("max_results"),
    "search_depth": result.get("search_depth"),
    "results": result.get("results") or [],
    "safety_notice": result.get("safety_notice") or SAFETY_NOTICE,
    "ok": result.get("ok"),
    "error": result.get("error"),
  }


def render_live_search_markdown(result: dict[str, Any]) -> str:
  lines = [
    "# Tavily Live Search Smoke Test",
    "",
    f"- query: {result.get('query')}",
    f"- provider: {result.get('provider')}",
    f"- fetched_at: {result.get('fetched_at')}",
    f"- max_results: {result.get('max_results')}",
    f"- search_depth: {result.get('search_depth')}",
    f"- ok: {result.get('ok')}",
    "",
    "## Safety notice",
    "",
    str(result.get("safety_notice") or SAFETY_NOTICE),
    "",
    "## Results",
    "",
  ]
  results = result.get("results") or []
  if not results:
    lines.append("_No results._")
  for index, item in enumerate(results, start=1):
    lines.extend(
      [
        f"### {index}. {item.get('title') or '(no title)'}",
        "",
        f"- url: {item.get('url')}",
        f"- score: {item.get('score')}",
        f"- provider: {item.get('provider')}",
        f"- fetched_at: {item.get('fetched_at')}",
        "",
        str(item.get("snippet") or ""),
        "",
      ],
    )
  return "\n".join(lines).strip() + "\n"


def save_live_tavily_search_result(
  result: dict[str, Any],
  output_root: Path | str,
) -> dict[str, str]:
  """Save json/md under outputs/live_search/. Never writes API keys."""
  root = Path(output_root)
  out_dir = root / "outputs" / "live_search"
  out_dir.mkdir(parents=True, exist_ok=True)

  fetched_at = str(result.get("fetched_at") or _utc_now_iso())
  slug = _timestamp_slug(fetched_at)
  json_path = out_dir / f"tavily_smoke_{slug}.json"
  md_path = out_dir / f"tavily_smoke_{slug}.md"

  payload = build_live_search_save_payload(result)
  serialized = json.dumps(payload, indent=2, ensure_ascii=False)
  if "TAVILY_API_KEY" in serialized or "api_key" in serialized.lower():
    raise ValueError("Refusing to save payload containing API key material")

  json_path.write_text(serialized + "\n", encoding="utf-8")
  md_path.write_text(render_live_search_markdown(result), encoding="utf-8")
  return {"json": str(json_path), "markdown": str(md_path)}


def live_tavily_block_message(block_reason: str | None) -> str:
  mapping = {
    "login_required": "ログイン後に実行できます。",
    "admin_required": "管理者のみ実行できます。",
    "disabled_by_env": "外部API無効化中（DISABLE_EXTERNAL_API=true）です。",
    "missing_keys": "TAVILY_API_KEY が未設定です。",
    "empty_query": "検索クエリを入力してください。",
  }
  return mapping.get(str(block_reason or ""), "外部API実行条件を満たしていません。")
