"""Weekly Decision Cockpit — aggregate existing artifacts for weekly review (Phase 25W)."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tech_cartography.runtime.evidence_gap_schema import default_safety_flags
from tech_cartography.runtime.live_artifact_paths import (
  check_directory_writable,
  get_live_weekly_decision_cockpit_dir,
)
from tech_cartography.runtime.user_context import evaluate_live_admin_access, normalize_user_context
from tech_cartography.services.live_digest_preview import (
  find_latest_live_digest_preview_path,
  load_latest_live_digest_preview,
)
from tech_cartography.services.live_evidence_gap_builder import (
  find_latest_evidence_gap_path,
  find_latest_scheduler_dry_run_path,
  load_evidence_gap_artifact,
  load_latest_evidence_gap_artifact,
  load_scheduler_dry_run,
)
from tech_cartography.services.live_run_history import (
  attach_user_run_metadata,
  generate_run_id,
  map_result_status,
  record_live_run,
  summarize_run_history_for_console,
)
from tech_cartography.services.live_strategic_watch_brief import (
  find_latest_strategic_watch_brief_path,
  load_latest_strategic_watch_brief,
  load_strategic_watch_brief,
)
from tech_cartography.services.live_web_signal_artifact_reader import read_latest_web_signal_artifact_summary
from tech_cartography.services.live_watch_profile_manager import get_active_watch_profile

ACTION_TYPE = "live_weekly_decision_cockpit_build"

READINESS_LEVELS: tuple[str, ...] = (
  "no_active_profile",
  "data_collected",
  "evidence_gap_ready",
  "brief_ready",
  "ready_for_human_review",
)

COCKPIT_NOTICE_JA = (
  "候補情報であり確定事実ではありません。"
  "FTO、侵害、有効性判断ではありません。"
)

READING_ORDER: tuple[str, ...] = (
  "1. 今週の確認対象テーマを確認",
  "2. 今週の変化候補（候補のみ）を確認",
  "3. Evidence Gap Top 3 で未確認事項を把握",
  "4. Next Verification Actions Top 3 を実行",
  "5. What Not To Conclude を再確認",
  "6. 必要なら詳細タブ（Digest / Web Signal / Run History）へ",
)

_SENSITIVE_PATTERN = re.compile(
  r"(smtp_password|tavily_api_key|api[_-]?key\s*[:=]|authorization|oauth|jwt)",
  re.IGNORECASE,
)

_URGENCY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _timestamp_slug(iso_ts: str) -> str:
  return iso_ts.replace(":", "").replace("-", "")


def new_cockpit_id() -> str:
  return f"cockpit-{uuid.uuid4().hex[:10]}"


def find_latest_weekly_decision_cockpit_path(output_root: Path | str) -> Path | None:
  out_dir = get_live_weekly_decision_cockpit_dir(output_root)
  if not out_dir.is_dir():
    return None
  files = sorted(out_dir.glob("live_weekly_decision_cockpit_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
  return files[0] if files else None


def load_weekly_decision_cockpit(path: Path | str) -> dict[str, Any] | None:
  target = Path(path)
  if not target.exists():
    return None
  try:
    data = json.loads(target.read_text(encoding="utf-8"))
  except (OSError, json.JSONDecodeError):
    return None
  return data if isinstance(data, dict) else None


def load_latest_weekly_decision_cockpit(output_root: Path | str) -> dict[str, Any] | None:
  latest = find_latest_weekly_decision_cockpit_path(output_root)
  if latest is None:
    return None
  return load_weekly_decision_cockpit(latest)


def describe_latest_weekly_decision_cockpit(output_root: Path | str) -> dict[str, Any]:
  path = find_latest_weekly_decision_cockpit_path(output_root)
  artifact = load_weekly_decision_cockpit(path) if path else None
  return {
    "latest_weekly_decision_cockpit_exists": bool(path and artifact),
    "latest_weekly_decision_cockpit_path": str(path) if path else None,
    "latest_readiness_level": (artifact or {}).get("readiness_level"),
    "latest_next_recommended_action": (artifact or {}).get("next_recommended_action"),
    "theme_name": (artifact or {}).get("theme_name"),
  }


def _top_gaps(gaps: list[dict[str, Any]], *, limit: int = 3) -> list[dict[str, Any]]:
  ranked = sorted(
    gaps,
    key=lambda g: (_URGENCY_ORDER.get(str(g.get("urgency")), 9), str(g.get("gap_id"))),
  )
  return ranked[:limit]


def _top_actions(actions: list[dict[str, Any]], *, limit: int = 3) -> list[dict[str, Any]]:
  ranked = sorted(
    actions,
    key=lambda a: (_URGENCY_ORDER.get(str(a.get("urgency")), 9), str(a.get("gap_id") or a.get("action"))),
  )
  return ranked[:limit]


def _weekly_change_candidates(
  digest: dict[str, Any] | None,
  web_summary: dict[str, Any],
  brief: dict[str, Any] | None,
) -> list[str]:
  if brief and brief.get("weekly_change_candidates"):
    return list(brief.get("weekly_change_candidates") or [])[:3]
  changes: list[str] = []
  if web_summary.get("artifact_exists"):
    changes.append(f"Web Signal: {web_summary.get('result_count')} candidate(s) — 原典未確認")
  if digest:
    changes.append(f"Digest Preview: theme={digest.get('theme_name')}")
  if not changes:
    changes.append("今週の変化候補は artifact からは未検出です。")
  return changes[:3]


def _derive_readiness_level(
  *,
  has_profile: bool,
  has_data: bool,
  has_gap: bool,
  has_brief: bool,
) -> str:
  if not has_profile:
    return "no_active_profile"
  if has_brief and has_gap:
    return "ready_for_human_review"
  if has_brief:
    return "brief_ready"
  if has_gap:
    return "evidence_gap_ready"
  if has_data:
    return "data_collected"
  return "no_active_profile"


def _next_recommended_action(readiness: str) -> str:
  mapping = {
    "no_active_profile": "Watch Profile を active 化してから週次サイクルを開始してください。",
    "data_collected": "Evidence Gap を生成し、未確認事項を構造化してください。",
    "evidence_gap_ready": "Strategic Watch Brief を生成し、優先確認事項（3件）を確認してください。",
    "brief_ready": "Weekly Decision Cockpit を保存し、人間レビューを開始してください。",
    "ready_for_human_review": "Next Verification Actions Top 3 を実行し、Run History に記録を残してください。",
  }
  return mapping.get(readiness, "Live Operation Console で週次サイクルを確認してください。")


def build_weekly_decision_cockpit_payload(
  output_root: Path | str,
  *,
  user_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
  """Aggregate existing artifacts. Never calls external APIs."""
  active, active_path = get_active_watch_profile(output_root)
  theme_name = str((active or {}).get("theme_name") or "").strip() or "Unknown Theme"

  web_summary = read_latest_web_signal_artifact_summary(output_root)
  digest = load_latest_live_digest_preview(output_root)
  digest_path_obj = find_latest_live_digest_preview_path(output_root)
  gap_artifact = load_latest_evidence_gap_artifact(output_root)
  brief = load_latest_strategic_watch_brief(output_root)
  dry_run_path = find_latest_scheduler_dry_run_path(output_root)
  dry_run = load_scheduler_dry_run(dry_run_path) if dry_run_path else None

  gap_path = find_latest_evidence_gap_path(output_root)
  brief_path = find_latest_strategic_watch_brief_path(output_root)

  if digest and not theme_name:
    theme_name = str(digest.get("theme_name") or theme_name)

  gaps = list((gap_artifact or {}).get("evidence_gaps") or [])
  if not gaps and brief:
    gaps = list(brief.get("evidence_gaps") or [])

  next_actions = list((gap_artifact or {}).get("next_verification_actions") or [])
  if not next_actions and brief:
    next_actions = list(brief.get("next_verification_actions") or [])
    if not next_actions:
      next_actions = [
        {
          "action": item.get("action"),
          "recommended_owner": item.get("owner"),
          "urgency": item.get("urgency"),
        }
        for item in (brief.get("recommended_next_human_actions") or [])
      ]

  what_not = list((gap_artifact or {}).get("what_not_to_conclude") or [])
  if not what_not and brief:
    what_not = list(brief.get("what_not_to_conclude") or [])

  source_coverage = (gap_artifact or {}).get("source_coverage") or (brief or {}).get("source_coverage") or {}

  latest_paths = {
    "active_watch_profile": active_path,
    "web_signal_collection": web_summary.get("artifact_path"),
    "digest_preview": str(digest_path_obj) if digest_path_obj else None,
    "evidence_gap": str(gap_path) if gap_path else None,
    "strategic_watch_brief": str(brief_path) if brief_path else None,
    "scheduler_dry_run": str(dry_run_path) if dry_run_path else None,
  }

  run_summary = summarize_run_history_for_console(output_root, viewer_user_context=user_context)
  recent_refs = [
    {
      "run_id": item.get("run_id"),
      "action_type": item.get("action_type"),
      "status": item.get("status"),
      "theme_name": item.get("theme_name"),
    }
    for item in (run_summary.get("recent_entries") or [])[:5]
  ]

  has_data = bool(web_summary.get("artifact_exists") or digest)
  has_gap = bool(gap_path and gap_artifact)
  has_brief = bool(brief_path and brief)
  readiness = _derive_readiness_level(
    has_profile=bool(active),
    has_data=has_data,
    has_gap=has_gap,
    has_brief=has_brief,
  )

  return {
    "cockpit_id": new_cockpit_id(),
    "action_type": ACTION_TYPE,
    "theme_name": theme_name,
    "generated_at": _utc_now_iso(),
    "active_watch_profile_summary": {
      "exists": bool(active),
      "path": active_path,
      "theme_name": (active or {}).get("theme_name"),
      "search_queries": list((active or {}).get("search_queries") or [])[:5],
    },
    "weekly_signal_summary": {
      "web_signal_artifact_exists": bool(web_summary.get("artifact_exists")),
      "web_signal_result_count": int(web_summary.get("result_count") or 0),
      "digest_preview_exists": bool(digest),
      "digest_uses_web_signals": bool((digest or {}).get("uses_web_signals")),
      "scheduler_dry_run_warnings": list((dry_run or {}).get("warnings") or [])[:3],
    },
    "weekly_change_candidates": _weekly_change_candidates(digest, web_summary, brief),
    "top_evidence_gaps": _top_gaps(gaps),
    "next_verification_actions": _top_actions(next_actions),
    "what_not_to_conclude": what_not,
    "source_coverage": source_coverage,
    "latest_artifact_paths": latest_paths,
    "latest_run_history_refs": recent_refs,
    "readiness_level": readiness,
    "next_recommended_action": _next_recommended_action(readiness),
    "reading_order": list(READING_ORDER),
    "candidate_only_notice": COCKPIT_NOTICE_JA,
    "safety_flags": default_safety_flags(),
  }


def render_weekly_decision_cockpit_markdown(payload: dict[str, Any]) -> str:
  lines = [
    "# Weekly Decision Cockpit",
    "",
    f"> {payload.get('candidate_only_notice')}",
    "",
    f"- theme: {payload.get('theme_name')}",
    f"- readiness: {payload.get('readiness_level')}",
    f"- generated_at: {payload.get('generated_at')}",
    "",
    "## 週30分で見る順番",
    "",
  ]
  for step in payload.get("reading_order") or []:
    lines.append(f"- {step}")
  lines.extend(["", "## 今週の変化候補", ""])
  for item in payload.get("weekly_change_candidates") or []:
    lines.append(f"- {item}")
  lines.extend(["", "## Evidence Gap Top 3", ""])
  for gap in payload.get("top_evidence_gaps") or []:
    lines.append(f"- [{gap.get('urgency')}] {gap.get('observation')}")
  lines.extend(["", "## Next Verification Actions Top 3", ""])
  for index, action in enumerate(payload.get("next_verification_actions") or [], start=1):
    lines.append(f"{index}. [{action.get('urgency')}] {action.get('action')} ({action.get('recommended_owner')})")
  lines.extend(["", "## What Not To Conclude", ""])
  for item in payload.get("what_not_to_conclude") or []:
    lines.append(f"- {item}")
  lines.extend(["", "## Next recommended action", "", str(payload.get("next_recommended_action") or "")])
  return "\n".join(lines).strip() + "\n"


def _assert_safe_serialized(serialized: str) -> None:
  if _SENSITIVE_PATTERN.search(serialized):
    raise ValueError("Refusing to save cockpit artifact containing sensitive material")


def save_weekly_decision_cockpit(payload: dict[str, Any], output_root: Path | str) -> dict[str, str]:
  out_dir = get_live_weekly_decision_cockpit_dir(output_root)
  writable, message = check_directory_writable(out_dir)
  if not writable:
    raise ValueError(message or str(out_dir))

  timestamp = str(payload.get("generated_at") or _utc_now_iso())
  run_id = str(payload.get("run_id") or generate_run_id())
  slug = _timestamp_slug(timestamp)
  json_path = out_dir / f"live_weekly_decision_cockpit_{slug}_{run_id}.json"
  md_path = out_dir / f"live_weekly_decision_cockpit_{slug}_{run_id}.md"
  json_text = json.dumps(payload, ensure_ascii=False, indent=2)
  _assert_safe_serialized(json_text)
  json_path.write_text(json_text + "\n", encoding="utf-8")
  md_path.write_text(render_weekly_decision_cockpit_markdown(payload), encoding="utf-8")
  return {"json": str(json_path), "markdown": str(md_path)}


def run_live_weekly_decision_cockpit_build(
  *,
  output_root: Path | str,
  login_required: bool,
  is_authenticated: bool,
  auth_role: str,
  user_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
  run_id = generate_run_id()
  started_at = _utc_now_iso()
  resolved_ctx = normalize_user_context(user_context)

  def _finalize(result: dict[str, Any], *, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    meta = dict(default_safety_flags())
    if payload:
      meta["readiness_level"] = payload.get("readiness_level")
      meta["evidence_gap_count"] = len(payload.get("top_evidence_gaps") or [])
      meta["next_action_count"] = len(payload.get("next_verification_actions") or [])
    record_live_run(
      action_type=ACTION_TYPE,
      status=map_result_status(ok=result.get("ok"), error=result.get("error")),
      run_id=run_id,
      started_at=started_at,
      user_context=resolved_ctx,
      theme_name=(payload or {}).get("theme_name"),
      input_summary=str((payload or {}).get("readiness_level") or ""),
      output_artifact_paths=result.get("saved_paths") or {},
      source_artifact_paths=[
        p for p in ((payload or {}).get("latest_artifact_paths") or {}).values() if p
      ],
      error_summary=None if result.get("ok") else str(result.get("message") or ""),
      operation_metadata=meta,
      project_root=output_root,
    )
    result["run_id"] = run_id
    return result

  access_ok, access_error, _ = evaluate_live_admin_access(
    login_required=login_required,
    is_authenticated=is_authenticated,
    auth_role=auth_role,
    user_context=resolved_ctx,
  )
  if not access_ok:
    message = "ログイン後に実行できます。" if access_error == "login_required" else "admin権限が必要です。"
    return _finalize({"ok": False, "error": access_error, "message": message})

  try:
    payload = build_weekly_decision_cockpit_payload(output_root, user_context=resolved_ctx)
    payload["run_id"] = run_id
    payload = attach_user_run_metadata(payload, user_context=resolved_ctx, run_id=run_id)
    saved_paths = save_weekly_decision_cockpit(payload, output_root)
  except (OSError, ValueError) as exc:
    return _finalize({"ok": False, "error": "save_failed", "message": str(exc)})

  return _finalize(
    {
      "ok": True,
      "message": "Weekly Decision Cockpit を保存しました。",
      "payload": payload,
      "saved_paths": saved_paths,
      "readiness_level": payload.get("readiness_level"),
    },
    payload=payload,
  )
