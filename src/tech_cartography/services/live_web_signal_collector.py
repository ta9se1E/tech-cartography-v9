"""Controlled manual Web Signal collection from active Watch Profile (Phase 25T)."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from tech_cartography.runtime.external_api_operation_config import (
  evaluate_manual_web_signal_collection,
  get_web_signal_allowlist_domains,
  get_web_signal_blocklist_domains,
  get_web_signal_max_queries,
  get_web_signal_max_results_per_query,
  skipped_reason_message,
)
from tech_cartography.runtime.live_artifact_paths import (
  check_directory_writable,
  get_live_web_signals_dir,
)
from tech_cartography.services.live_run_history import (
  attach_user_run_metadata,
  generate_run_id,
  record_live_run,
)
from tech_cartography.services.live_tavily_search import (
  PROVIDER,
  _default_post_tavily,
  normalize_tavily_search_response,
)
from tech_cartography.services.live_watch_profile_manager import get_active_watch_profile
from tech_cartography.web_signals.schema import extract_source_domain

ACTION_TYPE = "live_web_signal_collection"

SAFETY_NOTICE = (
  "Web Signal candidates for human review only. "
  "Not confirmed facts. No legal, FTO, infringement, or validity judgement."
)

NEXT_ACTION_SUCCESS = (
  "Review saved Web Signal candidates against primary sources. "
  "Create Digest Preview manually when ready (no auto email or scheduler)."
)
NEXT_ACTION_SKIPPED = "Resolve skipped reason, then retry with confirmation text when allowed."

_SENSITIVE_PATTERN = re.compile(
  r"(smtp_password|tavily_api_key|api[_-]?key|authorization|oauth|jwt|secret)",
  re.IGNORECASE,
)


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _timestamp_slug(iso_ts: str) -> str:
  return iso_ts.replace(":", "").replace("-", "")


def _safety_flags(*, manual_only: bool = True) -> dict[str, bool]:
  return {
    "manual_only": manual_only,
    "admin_required": True,
    "no_email_send": True,
    "no_scheduler_start": True,
    "legal_judgement": False,
    "fto_judgement": False,
    "infringement_judgement": False,
    "validity_judgement": False,
    "candidate_information_only": True,
  }


def _domain_allowed(url: str) -> bool:
  domain = extract_source_domain(url).lower()
  blocklist = get_web_signal_blocklist_domains()
  allowlist = get_web_signal_allowlist_domains()
  if blocklist and any(domain == blocked or domain.endswith(f".{blocked}") for blocked in blocklist):
    return False
  if allowlist:
    return any(domain == allowed or domain.endswith(f".{allowed}") for allowed in allowlist)
  return bool(domain)


def _queries_from_profile(profile: dict[str, Any]) -> list[str]:
  queries = [str(q).strip() for q in (profile.get("search_queries") or []) if str(q).strip()]
  if not queries:
    queries = [str(k).strip() for k in (profile.get("search_keywords") or []) if str(k).strip()]
  return queries[: get_web_signal_max_queries()]


def _normalize_web_signal(item: dict[str, Any], *, query: str) -> dict[str, Any]:
  url = str(item.get("url") or "").strip()
  return {
    "title": str(item.get("title") or "").strip(),
    "url": url,
    "domain": extract_source_domain(url),
    "snippet": str(item.get("snippet") or item.get("content") or "").strip(),
    "published_date": item.get("published_date") or item.get("publishedDate"),
    "source": PROVIDER,
    "query": query,
    "confidence_label": "candidate",
  }


def _assert_safe_serialized(serialized: str) -> None:
  scrubbed = re.sub(
    r"(TAVILY_API_KEY|OPENAI_API_KEY|GEMINI_API_KEY|GOOGLE_API_KEY|SMTP_PASSWORD)",
    "[env-name-redacted]",
    serialized,
    flags=re.IGNORECASE,
  )
  if _SENSITIVE_PATTERN.search(scrubbed):
    raise ValueError("Refusing to save web signal collection containing sensitive material")


def _render_markdown(payload: dict[str, Any]) -> str:
  lines = [
    "# Live Web Signal Collection",
    "",
    f"- status: {payload.get('status')}",
    f"- theme_name: {payload.get('theme_name')}",
    f"- active_watch_profile_path: {payload.get('active_watch_profile_path')}",
    f"- queries_used: {payload.get('queries_used')}",
    f"- result_count: {payload.get('result_count')}",
    "",
    "## Safety notice",
    "",
    str(payload.get("safety_notice") or SAFETY_NOTICE),
    "",
  ]
  if payload.get("skipped_reason"):
    lines.extend(["## Skipped reason", "", str(payload.get("skipped_reason")), ""])
  if payload.get("error_summary"):
    lines.extend(["## Error", "", str(payload.get("error_summary")), ""])
  lines.extend(["## Web signals", ""])
  signals = payload.get("web_signals") or []
  if not signals:
    lines.append("_No signals._")
  for index, signal in enumerate(signals, start=1):
    lines.extend(
      [
        f"### {index}. {signal.get('title') or '(no title)'}",
        "",
        f"- url: {signal.get('url')}",
        f"- domain: {signal.get('domain')}",
        f"- query: {signal.get('query')}",
        f"- confidence_label: {signal.get('confidence_label')}",
        "",
        str(signal.get("snippet") or ""),
        "",
      ],
    )
  return "\n".join(lines).strip() + "\n"


def _save_collection_artifact(
  payload: dict[str, Any],
  *,
  output_root: Path | str,
  run_id: str,
) -> dict[str, str]:
  out_dir = get_live_web_signals_dir(output_root)
  writable, message = check_directory_writable(out_dir)
  if not writable:
    raise ValueError(message or f"Cannot write web signal collection to {out_dir}")

  status = str(payload.get("status") or "skipped")
  created_at = str(payload.get("timestamp") or _utc_now_iso())
  slug = _timestamp_slug(created_at)
  json_path = out_dir / f"live_web_signal_collection_{status}_{slug}_{run_id}.json"
  md_path = out_dir / f"live_web_signal_collection_{status}_{slug}_{run_id}.md"
  serialized = json.dumps(payload, indent=2, ensure_ascii=False)
  _assert_safe_serialized(serialized)
  json_path.write_text(serialized + "\n", encoding="utf-8")
  md_path.write_text(_render_markdown(payload), encoding="utf-8")
  return {"json": str(json_path), "markdown": str(md_path)}


def find_latest_web_signal_collection_path(output_root: Path | str) -> Path | None:
  out_dir = get_live_web_signals_dir(output_root)
  if not out_dir.is_dir():
    return None
  files = sorted(
    out_dir.glob("live_web_signal_collection_*.json"),
    key=lambda path: path.stat().st_mtime if path.exists() else 0,
    reverse=True,
  )
  return files[0] if files else None


def load_web_signal_collection(path: Path | str) -> dict[str, Any] | None:
  target = Path(path)
  if not target.exists():
    return None
  try:
    data = json.loads(target.read_text(encoding="utf-8"))
  except (OSError, json.JSONDecodeError):
    return None
  return data if isinstance(data, dict) else None


def load_latest_web_signal_collection(output_root: Path | str) -> dict[str, Any] | None:
  latest = find_latest_web_signal_collection_path(output_root)
  if latest is None:
    return None
  return load_web_signal_collection(latest)


def describe_latest_web_signal_collection(output_root: Path | str) -> dict[str, Any]:
  path = find_latest_web_signal_collection_path(output_root)
  if path is None:
    return {
      "latest_web_signal_collection_artifact": None,
      "latest_web_signal_collection_status": None,
      "latest_web_signal_result_count": 0,
    }
  data = load_web_signal_collection(path) or {}
  return {
    "latest_web_signal_collection_artifact": str(path),
    "latest_web_signal_collection_status": data.get("status"),
    "latest_web_signal_result_count": int(data.get("result_count") or 0),
  }


def _run_tavily_query(
  query: str,
  *,
  max_results: int,
  post_fn: Callable[..., dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
  api_key = os.environ.get("TAVILY_API_KEY", "").strip()
  if not api_key:
    return [], "missing_tavily_key"
  fetched_at = _utc_now_iso()
  payload = {
    "query": query,
    "search_depth": "basic",
    "max_results": max_results,
    "include_answer": False,
    "include_raw_content": False,
  }
  poster = post_fn or _default_post_tavily
  raw = poster(
    url="https://api.tavily.com/search",
    payload=payload,
    api_key=api_key,
    timeout_sec=20,
  )
  if raw.get("error"):
    return [], str(raw.get("error"))
  hits = normalize_tavily_search_response(raw, query=query, fetched_at=fetched_at)
  signals: list[dict[str, Any]] = []
  for hit in hits:
    normalized = _normalize_web_signal(hit, query=query)
    if normalized.get("url") and _domain_allowed(normalized["url"]):
      signals.append(normalized)
    if len(signals) >= max_results:
      break
  return signals[:max_results], None


def collect_live_web_signals(
  *,
  output_root: Path | str,
  confirm_text: str,
  login_required: bool,
  is_authenticated: bool,
  auth_role: str,
  user_context: dict[str, Any] | None = None,
  post_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
  run_id = generate_run_id()
  started_at = _utc_now_iso()
  active, active_path = get_active_watch_profile(output_root)
  allowed, skipped_reason, confirmation_matched = evaluate_manual_web_signal_collection(
    login_required=login_required,
    is_authenticated=is_authenticated,
    auth_role=auth_role,
    confirm_text=confirm_text,
    has_active_watch_profile=bool(active),
  )

  max_queries = get_web_signal_max_queries()
  max_results = get_web_signal_max_results_per_query()
  queries_used: list[str] = []
  web_signals: list[dict[str, Any]] = []
  error_summary: str | None = None
  status = "skipped"

  if allowed and active:
    queries_used = _queries_from_profile(active)
    if not queries_used:
      allowed = False
      skipped_reason = "no_queries"

  if allowed and active:
    for query in queries_used:
      batch, error = _run_tavily_query(query, max_results=max_results, post_fn=post_fn)
      if error and not batch:
        error_summary = error
        status = "failure"
        break
      web_signals.extend(batch)
    if status != "failure":
      status = "success"
  elif skipped_reason:
    status = "skipped"

  payload: dict[str, Any] = {
    "timestamp": started_at,
    "run_id": run_id,
    "action_type": ACTION_TYPE,
    "status": status,
    "active_watch_profile_path": active_path,
    "active_watch_profile_id": (active or {}).get("profile_id"),
    "theme_name": (active or {}).get("theme_name"),
    "queries_used": queries_used,
    "max_queries": max_queries,
    "max_results_per_query": max_results,
    "result_count": len(web_signals),
    "web_signals": web_signals,
    "skipped_reason": skipped_reason,
    "error_summary": error_summary,
    "safety_notice": SAFETY_NOTICE,
    "safety_flags": _safety_flags(manual_only=True),
    "next_recommended_action": NEXT_ACTION_SUCCESS if status == "success" else NEXT_ACTION_SKIPPED,
    "confirmation_matched": confirmation_matched,
  }
  payload = attach_user_run_metadata(payload, user_context=user_context, run_id=run_id)

  try:
    saved_paths = _save_collection_artifact(payload, output_root=output_root, run_id=run_id)
  except (OSError, ValueError) as exc:
    record_live_run(
      action_type=ACTION_TYPE,
      status="failed",
      run_id=run_id,
      started_at=started_at,
      user_context=user_context,
      theme_name=(active or {}).get("theme_name"),
      input_summary=f"confirmation_matched={confirmation_matched}",
      error_summary=str(exc),
      project_root=output_root,
    )
    return {
      "ok": False,
      "error": "save_failed",
      "message": str(exc),
      "status": "failure",
      "run_id": run_id,
    }

  history_status = {"success": "success", "skipped": "skipped", "failure": "failed"}.get(status, "blocked")
  record_live_run(
    action_type=ACTION_TYPE,
    status=history_status,
    run_id=run_id,
    started_at=started_at,
    user_context=user_context,
    theme_name=(active or {}).get("theme_name"),
    input_summary=(
      f"queries={len(queries_used)} result_count={len(web_signals)} "
      f"confirmation_matched={confirmation_matched}"
    ),
    output_artifact_paths=saved_paths,
    source_artifact_paths=[active_path] if active_path else [],
    error_summary=error_summary or (skipped_reason_message(skipped_reason) if skipped_reason else None),
    operation_metadata={
      "active_watch_profile_id": (active or {}).get("profile_id"),
      "result_count": len(web_signals),
      "confirmation_matched": confirmation_matched,
      "manual_only": True,
      "no_email_send": True,
      "no_scheduler_start": True,
      "candidate_information_only": True,
    },
    project_root=output_root,
  )

  ok = status == "success"
  return {
    "ok": ok,
    "status": status,
    "skipped_reason": skipped_reason,
    "message": (
      f"Web Signal候補を {len(web_signals)} 件保存しました。"
      if ok
      else skipped_reason_message(skipped_reason) if skipped_reason else str(error_summary or "収集に失敗しました。")
    ),
    "payload": payload,
    "saved_paths": saved_paths,
    "result_count": len(web_signals),
    "run_id": run_id,
  }
