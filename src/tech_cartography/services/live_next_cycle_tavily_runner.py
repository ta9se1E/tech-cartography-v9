"""Manual Tavily runner for admin-selected next cycle queries (Phase 25J)."""

from __future__ import annotations

import csv
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from tech_cartography.runtime.live_artifact_paths import (
  check_directory_writable,
  get_live_next_cycle_web_signals_dir,
)
from tech_cartography.services.live_tavily_search import (
  DEFAULT_SEARCH_DEPTH,
  PROVIDER,
  clamp_max_results,
  live_tavily_block_message,
  run_live_tavily_search_smoke,
)
from tech_cartography.services.live_web_signal_pack import (
  infer_confidence_label,
  infer_live_signal_type,
)

MAX_SELECTED_QUERIES = 3
REVIEW_STATUS = "needs_human_review"
SAFETY_LABEL = "Next cycle Web Signal candidate"
SOURCE_TYPE = "next_cycle_web_signal_pack"

SAFETY_NOTICE = (
  "These are next-cycle Web Signal candidates from manually selected Tavily queries. "
  "They are not confirmed facts and must not be used for FTO, infringement, or validity analysis. "
  "No automatic or scheduled execution occurred."
)

DEFAULT_NEXT_ACTIONS: tuple[str, ...] = (
  "Review each candidate against primary sources.",
  "Link promising signals to patent / claim context in a later phase.",
  "Do not treat results as confirmed market or legal facts.",
)

_SENSITIVE_KEY_PATTERN = re.compile(r"(api[_-]?key|authorization|token|secret|smtp|password)", re.IGNORECASE)


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _timestamp_slug(iso_ts: str) -> str:
  return iso_ts.replace(":", "").replace("-", "")


def clamp_selected_queries(queries: list[dict[str, Any]]) -> list[dict[str, Any]]:
  cleaned: list[dict[str, Any]] = []
  seen: set[str] = set()
  for row in queries:
    if not isinstance(row, dict):
      continue
    query = str(row.get("query") or "").strip()
    normalized = query.lower()
    if not query or normalized in seen:
      continue
    seen.add(normalized)
    cleaned.append(row)
    if len(cleaned) >= MAX_SELECTED_QUERIES:
      break
  return cleaned


def _assert_no_sensitive_material(serialized: str) -> None:
  if _SENSITIVE_KEY_PATTERN.search(serialized):
    raise ValueError("Refusing to save payload containing sensitive material")


def _search_results_to_candidates(
  *,
  query_id: str,
  query: str,
  results: list[dict[str, Any]],
  fetched_at: str,
) -> list[dict[str, Any]]:
  candidates: list[dict[str, Any]] = []
  for item in results:
    title = str(item.get("title") or "").strip()
    url = str(item.get("url") or "").strip()
    snippet = str(item.get("snippet") or item.get("content") or "").strip()
    score = item.get("score")
    candidates.append(
      {
        "signal_id": str(uuid.uuid4()),
        "query_id": query_id,
        "query": query,
        "title": title,
        "url": url,
        "snippet": snippet,
        "score": score,
        "provider": PROVIDER,
        "signal_type": infer_live_signal_type(title=title, snippet=snippet, url=url),
        "confidence_label": infer_confidence_label(score),
        "review_status": REVIEW_STATUS,
        "safety_label": SAFETY_LABEL,
        "fetched_at": fetched_at,
      },
    )
  return candidates


def build_next_cycle_web_signal_pack(
  *,
  theme_name: str,
  source_plan_path: str | None,
  source_watch_profile_draft_path: str | None,
  selected_queries: list[dict[str, Any]],
  query_runs: list[dict[str, Any]],
  candidates: list[dict[str, Any]],
) -> dict[str, Any]:
  return {
    "theme_name": theme_name,
    "source_type": SOURCE_TYPE,
    "source_plan_path": source_plan_path,
    "source_watch_profile_draft_path": source_watch_profile_draft_path,
    "fetched_at": _utc_now_iso(),
    "provider": PROVIDER,
    "search_depth": DEFAULT_SEARCH_DEPTH,
    "selected_queries": selected_queries,
    "query_runs": query_runs,
    "candidates": candidates,
    "safety_notice": SAFETY_NOTICE,
    "next_actions": list(DEFAULT_NEXT_ACTIONS),
  }


def render_next_cycle_web_signal_pack_markdown(pack: dict[str, Any]) -> str:
  lines = [
    "# Next Cycle Web Signal Pack",
    "",
    f"- theme_name: {pack.get('theme_name')}",
    f"- source_type: {pack.get('source_type')}",
    f"- provider: {pack.get('provider')}",
    f"- fetched_at: {pack.get('fetched_at')}",
    f"- candidate_count: {len(pack.get('candidates') or [])}",
    "",
    "## Safety notice",
    "",
    str(pack.get("safety_notice") or SAFETY_NOTICE),
    "",
    "## Candidates",
    "",
  ]
  for item in pack.get("candidates") or []:
    lines.extend(
      [
        f"### {item.get('title') or '(no title)'}",
        "",
        f"- query: {item.get('query')}",
        f"- url: {item.get('url')}",
        f"- signal_type: {item.get('signal_type')}",
        f"- confidence_label: {item.get('confidence_label')}",
        f"- review_status: {item.get('review_status')}",
        f"- safety_label: {item.get('safety_label')}",
        "",
        str(item.get("snippet") or ""),
        "",
      ],
    )
  return "\n".join(lines).strip() + "\n"


def save_next_cycle_web_signal_pack(
  pack: dict[str, Any],
  output_root: Path | str,
) -> dict[str, str]:
  out_dir = get_live_next_cycle_web_signals_dir(output_root)
  writable, message = check_directory_writable(out_dir)
  if not writable:
    raise ValueError(message or f"Cannot write next cycle web signal pack to {out_dir}")

  fetched_at = str(pack.get("fetched_at") or _utc_now_iso())
  slug = _timestamp_slug(fetched_at)
  json_path = out_dir / f"next_cycle_web_signal_pack_{slug}.json"
  csv_path = out_dir / f"next_cycle_web_signal_pack_{slug}.csv"
  md_path = out_dir / f"next_cycle_web_signal_pack_{slug}.md"

  serialized = json.dumps(pack, indent=2, ensure_ascii=False)
  _assert_no_sensitive_material(serialized)
  json_path.write_text(serialized + "\n", encoding="utf-8")

  candidates = pack.get("candidates") or []
  if candidates:
    fieldnames = list(candidates[0].keys())
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
      writer = csv.DictWriter(handle, fieldnames=fieldnames)
      writer.writeheader()
      writer.writerows(candidates)
  else:
    csv_path.write_text("", encoding="utf-8")

  md_path.write_text(render_next_cycle_web_signal_pack_markdown(pack), encoding="utf-8")
  return {"json": str(json_path), "csv": str(csv_path), "markdown": str(md_path)}


def find_latest_next_cycle_web_signal_pack_path(output_root: Path | str) -> Path | None:
  out_dir = get_live_next_cycle_web_signals_dir(output_root)
  if not out_dir.exists():
    return None
  files = sorted(
    out_dir.glob("next_cycle_web_signal_pack_*.json"),
    key=lambda path: path.stat().st_mtime,
    reverse=True,
  )
  return files[0] if files else None


def load_next_cycle_web_signal_pack(path: Path | str) -> dict[str, Any] | None:
  target = Path(path)
  if not target.exists():
    return None
  try:
    data = json.loads(target.read_text(encoding="utf-8"))
  except (json.JSONDecodeError, OSError):
    return None
  return data if isinstance(data, dict) else None


def load_latest_next_cycle_web_signal_pack(output_root: Path | str) -> dict[str, Any] | None:
  latest = find_latest_next_cycle_web_signal_pack_path(output_root)
  if latest is None:
    return None
  return load_next_cycle_web_signal_pack(latest)


def run_next_cycle_tavily_searches(
  *,
  selected_query_candidates: list[dict[str, Any]],
  max_results_per_query: int,
  output_root: Path | str,
  theme_name: str,
  source_plan_path: str | None,
  source_watch_profile_draft_path: str | None,
  login_required: bool,
  is_authenticated: bool,
  auth_role: str,
  post_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
  """Run Tavily only for admin-selected queries. Never raises."""
  selected = clamp_selected_queries(selected_query_candidates)
  if not selected:
    return {
      "ok": False,
      "error": "empty_selection",
      "message": "Tavily 実行対象の query を選択してください。",
      "candidates": [],
      "pack": None,
      "saved_paths": {},
    }

  bounded_max = clamp_max_results(max_results_per_query)
  all_candidates: list[dict[str, Any]] = []
  query_runs: list[dict[str, Any]] = []

  for row in selected:
    query_id = str(row.get("query_id") or uuid.uuid4())
    query = str(row.get("query") or "").strip()
    search_result = run_live_tavily_search_smoke(
      query,
      max_results=bounded_max,
      login_required=login_required,
      is_authenticated=is_authenticated,
      auth_role=auth_role,
      post_fn=post_fn,
    )
    query_runs.append(
      {
        "query_id": query_id,
        "query": query,
        "ok": bool(search_result.get("ok")),
        "error": search_result.get("error"),
        "message": search_result.get("message"),
        "result_count": len(search_result.get("results") or []),
      },
    )
    if not search_result.get("ok"):
      continue
    fetched_at = str(search_result.get("fetched_at") or _utc_now_iso())
    all_candidates.extend(
      _search_results_to_candidates(
        query_id=query_id,
        query=query,
        results=search_result.get("results") or [],
        fetched_at=fetched_at,
      ),
    )

  if not any(run.get("ok") for run in query_runs):
    first_error = next((run for run in query_runs if not run.get("ok")), {})
    block_reason = str(first_error.get("error") or "blocked")
    return {
      "ok": False,
      "error": block_reason,
      "message": live_tavily_block_message(block_reason)
      if block_reason in {"disabled_by_env", "missing_keys", "login_required", "admin_required"}
      else str(first_error.get("message") or "Tavily 検索に失敗しました。"),
      "query_runs": query_runs,
      "candidates": [],
      "pack": None,
      "saved_paths": {},
    }

  pack = build_next_cycle_web_signal_pack(
    theme_name=theme_name,
    source_plan_path=source_plan_path,
    source_watch_profile_draft_path=source_watch_profile_draft_path,
    selected_queries=selected,
    query_runs=query_runs,
    candidates=all_candidates,
  )

  try:
    saved_paths = save_next_cycle_web_signal_pack(pack, output_root)
  except (OSError, ValueError) as exc:
    return {
      "ok": False,
      "error": "save_failed",
      "message": str(exc),
      "query_runs": query_runs,
      "candidates": all_candidates,
      "pack": pack,
      "saved_paths": {},
    }

  return {
    "ok": True,
    "error": None,
    "message": f"Next Cycle Web Signal Pack を保存しました（{len(all_candidates)} 件）。",
    "query_runs": query_runs,
    "candidates": all_candidates,
    "pack": pack,
    "saved_paths": saved_paths,
    "max_results_per_query": bounded_max,
  }
