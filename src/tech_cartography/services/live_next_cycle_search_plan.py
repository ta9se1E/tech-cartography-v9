"""Next cycle search plan from human-approved Watch Profile Draft (Phase 25J)."""

from __future__ import annotations

import csv
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tech_cartography.runtime.live_artifact_paths import (
  check_directory_writable,
  get_live_next_cycle_search_dir,
)
from tech_cartography.services.watch_profile_draft import (
  find_latest_watch_profile_draft_path,
  load_latest_watch_profile_draft,
  load_watch_profile_draft,
)

MAX_QUERY_CANDIDATES = 5
REVIEW_STATUS = "pending_human_selection"
SAFETY_LABEL = "Next cycle search candidate"

SAFETY_NOTICE = (
  "These are next-cycle search query candidates derived from a human-approved Watch Profile Draft. "
  "They are not confirmed facts and must not be used for FTO, infringement, or validity analysis. "
  "Only admin-selected queries may be executed manually. No automatic or scheduled execution."
)

DEFAULT_NEXT_ACTIONS: tuple[str, ...] = (
  "Review each query candidate before selecting for Tavily search.",
  "Select at most three queries for the next manual search cycle.",
  "Treat search results as Web Signal candidates requiring human review.",
  "Do not treat draft-approved items as confirmed market or legal facts.",
)

QUERY_TYPE_SPECS: tuple[tuple[str, str, str, str], ...] = (
  ("keyword_expansion", "approved_keywords", "high", "keyword expansion from approved draft"),
  ("company_watch", "approved_companies", "high", "company watch from approved draft"),
  ("public_project_watch", "approved_public_projects", "medium", "public project watch from approved draft"),
  ("technology_watch", "approved_technology_terms", "high", "technology watch from approved draft"),
  ("market_application_watch", "approved_market_applications", "medium", "market application watch from approved draft"),
)

_SENSITIVE_KEY_PATTERN = re.compile(r"(api[_-]?key|authorization|token|secret|smtp|password)", re.IGNORECASE)


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _timestamp_slug(iso_ts: str) -> str:
  return iso_ts.replace(":", "").replace("-", "")


def _normalize_query(query: str) -> str:
  return re.sub(r"\s+", " ", str(query or "").strip()).lower()


def _assert_no_sensitive_material(serialized: str) -> None:
  if _SENSITIVE_KEY_PATTERN.search(serialized):
    raise ValueError("Refusing to save payload containing sensitive material")


def _build_query_text(*, query_type: str, item: str, theme_name: str) -> str:
  cleaned_item = str(item).strip()
  cleaned_theme = str(theme_name or "monitoring theme").strip()
  if query_type == "keyword_expansion":
    return f"{cleaned_theme} {cleaned_item} patent intelligence"
  if query_type == "company_watch":
    return f"{cleaned_item} carbon fiber technology news"
  if query_type == "public_project_watch":
    return f"{cleaned_item} grant demonstration carbon fiber"
  if query_type == "technology_watch":
    return f"{cleaned_theme} {cleaned_item} research commercialization"
  if query_type == "market_application_watch":
    return f"{cleaned_item} carbon fiber market application"
  return f"{cleaned_theme} {cleaned_item} watch query"


def build_query_candidates_from_draft(
  draft: dict[str, Any],
  *,
  theme_name: str | None = None,
  user_note: str | None = None,
) -> list[dict[str, Any]]:
  """Build up to MAX_QUERY_CANDIDATES unique query candidates. Never auto-executes."""
  created_at = _utc_now_iso()
  resolved_theme = str(theme_name or draft.get("theme_name") or "").strip()
  seen: set[str] = set()
  candidates: list[dict[str, Any]] = []

  for query_type, field_name, priority_label, reason_prefix in QUERY_TYPE_SPECS:
    for item in draft.get(field_name) or []:
      cleaned = str(item).strip()
      if not cleaned:
        continue
      query = _build_query_text(query_type=query_type, item=cleaned, theme_name=resolved_theme)
      normalized = _normalize_query(query)
      if not normalized or normalized in seen:
        continue
      seen.add(normalized)
      candidates.append(
        {
          "query_id": str(uuid.uuid4()),
          "query": query,
          "query_type": query_type,
          "source_approved_items": [cleaned],
          "reason": f"{reason_prefix}: {cleaned}",
          "priority_label": priority_label,
          "review_status": REVIEW_STATUS,
          "safety_label": SAFETY_LABEL,
          "created_at": created_at,
        },
      )
      if len(candidates) >= MAX_QUERY_CANDIDATES:
        return candidates

  if user_note and len(candidates) < MAX_QUERY_CANDIDATES:
    note_query = _normalize_query(user_note)
    if note_query and note_query not in seen:
      candidates.append(
        {
          "query_id": str(uuid.uuid4()),
          "query": str(user_note).strip(),
          "query_type": "keyword_expansion",
          "source_approved_items": [],
          "reason": "Admin user_note supplied for next cycle search.",
          "priority_label": "low",
          "review_status": REVIEW_STATUS,
          "safety_label": SAFETY_LABEL,
          "created_at": created_at,
        },
      )
  return candidates


def build_next_cycle_search_plan(
  *,
  draft: dict[str, Any],
  source_watch_profile_draft_path: str,
  theme_name: str | None = None,
  user_note: str | None = None,
) -> dict[str, Any]:
  resolved_theme = str(theme_name or draft.get("theme_name") or "").strip()
  query_candidates = build_query_candidates_from_draft(
    draft,
    theme_name=resolved_theme,
    user_note=user_note,
  )
  return {
    "plan_id": str(uuid.uuid4()),
    "theme_name": resolved_theme,
    "created_at": _utc_now_iso(),
    "source_watch_profile_draft_path": source_watch_profile_draft_path,
    "query_candidates": query_candidates,
    "next_cycle_search_plan": query_candidates,
    "safety_notice": SAFETY_NOTICE,
    "next_actions": list(DEFAULT_NEXT_ACTIONS),
  }


def render_next_cycle_search_plan_markdown(plan: dict[str, Any]) -> str:
  lines = [
    "# Next Cycle Search Plan",
    "",
    f"- plan_id: {plan.get('plan_id')}",
    f"- theme_name: {plan.get('theme_name')}",
    f"- created_at: {plan.get('created_at')}",
    f"- source_watch_profile_draft_path: {plan.get('source_watch_profile_draft_path')}",
    f"- query_candidate_count: {len(plan.get('query_candidates') or [])}",
    "",
    "## Safety notice",
    "",
    str(plan.get("safety_notice") or SAFETY_NOTICE),
    "",
    "## Query candidates",
    "",
  ]
  for item in plan.get("query_candidates") or []:
    lines.extend(
      [
        f"### {item.get('query_type')}: {item.get('query')}",
        "",
        f"- query_id: {item.get('query_id')}",
        f"- priority_label: {item.get('priority_label')}",
        f"- review_status: {item.get('review_status')}",
        f"- safety_label: {item.get('safety_label')}",
        f"- reason: {item.get('reason')}",
        f"- source_approved_items: {', '.join(item.get('source_approved_items') or [])}",
        "",
      ],
    )
  return "\n".join(lines).strip() + "\n"


def save_next_cycle_search_plan(
  plan: dict[str, Any],
  output_root: Path | str,
) -> dict[str, str]:
  out_dir = get_live_next_cycle_search_dir(output_root)
  writable, message = check_directory_writable(out_dir)
  if not writable:
    raise ValueError(message or f"Cannot write next cycle search plan to {out_dir}")

  created_at = str(plan.get("created_at") or _utc_now_iso())
  slug = _timestamp_slug(created_at)
  json_path = out_dir / f"next_cycle_search_plan_{slug}.json"
  csv_path = out_dir / f"next_cycle_search_plan_{slug}.csv"
  md_path = out_dir / f"next_cycle_search_plan_{slug}.md"

  serialized = json.dumps(plan, indent=2, ensure_ascii=False)
  _assert_no_sensitive_material(serialized)
  json_path.write_text(serialized + "\n", encoding="utf-8")

  rows = plan.get("query_candidates") or []
  if rows:
    fieldnames = list(rows[0].keys())
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
      writer = csv.DictWriter(handle, fieldnames=fieldnames)
      writer.writeheader()
      writer.writerows(rows)
  else:
    csv_path.write_text("", encoding="utf-8")

  md_path.write_text(render_next_cycle_search_plan_markdown(plan), encoding="utf-8")
  return {"json": str(json_path), "csv": str(csv_path), "markdown": str(md_path)}


def find_latest_next_cycle_search_plan_path(output_root: Path | str) -> Path | None:
  out_dir = get_live_next_cycle_search_dir(output_root)
  if not out_dir.exists():
    return None
  files = sorted(
    out_dir.glob("next_cycle_search_plan_*.json"),
    key=lambda path: path.stat().st_mtime,
    reverse=True,
  )
  return files[0] if files else None


def load_next_cycle_search_plan(path: Path | str) -> dict[str, Any] | None:
  target = Path(path)
  if not target.exists():
    return None
  try:
    data = json.loads(target.read_text(encoding="utf-8"))
  except (json.JSONDecodeError, OSError):
    return None
  return data if isinstance(data, dict) else None


def load_latest_next_cycle_search_plan(output_root: Path | str) -> dict[str, Any] | None:
  latest = find_latest_next_cycle_search_plan_path(output_root)
  if latest is None:
    return None
  return load_next_cycle_search_plan(latest)


def create_next_cycle_search_plan_from_latest_draft(
  *,
  output_root: Path | str,
  theme_name: str | None = None,
  user_note: str | None = None,
  login_required: bool,
  is_authenticated: bool,
  auth_role: str,
) -> dict[str, Any]:
  if login_required and not is_authenticated:
    return {"ok": False, "error": "login_required", "message": "ログイン後に実行できます。"}
  if login_required and str(auth_role or "member") != "admin":
    return {"ok": False, "error": "admin_required", "message": "管理者のみ実行できます。"}

  draft_path = find_latest_watch_profile_draft_path(output_root)
  if draft_path is None:
    return {
      "ok": False,
      "error": "missing_watch_profile_draft",
      "message": "latest watch_profile_draft がありません。先に Watch Expansion を承認してください。",
    }

  draft = load_watch_profile_draft(draft_path)
  if not draft:
    return {
      "ok": False,
      "error": "invalid_watch_profile_draft",
      "message": "watch_profile_draft の読み込みに失敗しました。",
    }

  plan = build_next_cycle_search_plan(
    draft=draft,
    source_watch_profile_draft_path=str(draft_path),
    theme_name=theme_name,
    user_note=user_note,
  )
  if not plan.get("query_candidates"):
    return {
      "ok": False,
      "error": "empty_approved_items",
      "message": "approved item が空のため query 候補を作成できません。",
    }

  try:
    saved_paths = save_next_cycle_search_plan(plan, output_root)
  except (OSError, ValueError) as exc:
    return {"ok": False, "error": "save_failed", "message": str(exc)}

  return {
    "ok": True,
    "error": None,
    "message": f"次回検索クエリ候補を {len(plan['query_candidates'])} 件作成しました（選択前）。",
    "plan": plan,
    "saved_paths": saved_paths,
    "source_watch_profile_draft_path": str(draft_path),
  }
