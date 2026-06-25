"""Strategic Watch Brief — weekly 30-minute read format (Phase 25V)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tech_cartography.runtime.evidence_gap_schema import default_safety_flags
from tech_cartography.runtime.live_artifact_paths import (
  check_directory_writable,
  get_live_strategic_watch_brief_dir,
)
from tech_cartography.runtime.user_context import evaluate_live_admin_access, normalize_user_context
from tech_cartography.services.live_digest_preview import load_latest_live_digest_preview
from tech_cartography.services.live_evidence_gap_builder import (
  build_evidence_gap_payload,
  find_latest_evidence_gap_path,
  load_evidence_gap_artifact,
  load_latest_evidence_gap_artifact,
)
from tech_cartography.services.live_run_history import (
  attach_user_run_metadata,
  generate_run_id,
  map_result_status,
  record_live_run,
)
from tech_cartography.services.live_web_signal_artifact_reader import read_latest_web_signal_artifact_summary

ACTION_TYPE = "live_strategic_watch_brief_build"

CANDIDATE_NOTICE = (
  "候補情報であり確定事実ではありません。"
  "FTO、侵害、有効性判断ではありません。"
)

_SENSITIVE_PATTERN = re.compile(
  r"(smtp_password|tavily_api_key|api[_-]?key\s*[:=]|authorization|oauth|jwt)",
  re.IGNORECASE,
)


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _timestamp_slug(iso_ts: str) -> str:
  return iso_ts.replace(":", "").replace("-", "")


def find_latest_strategic_watch_brief_path(output_root: Path | str) -> Path | None:
  out_dir = get_live_strategic_watch_brief_dir(output_root)
  if not out_dir.is_dir():
    return None
  files = sorted(out_dir.glob("live_strategic_watch_brief_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
  return files[0] if files else None


def load_strategic_watch_brief(path: Path | str) -> dict[str, Any] | None:
  target = Path(path)
  if not target.exists():
    return None
  try:
    data = json.loads(target.read_text(encoding="utf-8"))
  except (OSError, json.JSONDecodeError):
    return None
  return data if isinstance(data, dict) else None


def load_latest_strategic_watch_brief(output_root: Path | str) -> dict[str, Any] | None:
  latest = find_latest_strategic_watch_brief_path(output_root)
  if latest is None:
    return None
  return load_strategic_watch_brief(latest)


def describe_latest_strategic_watch_brief(output_root: Path | str) -> dict[str, Any]:
  path = find_latest_strategic_watch_brief_path(output_root)
  artifact = load_strategic_watch_brief(path) if path else None
  actions = list((artifact or {}).get("recommended_next_human_actions") or [])
  return {
    "latest_strategic_watch_brief_exists": bool(path and artifact),
    "latest_strategic_watch_brief_path": str(path) if path else None,
    "latest_next_verification_action_count": len(
      (artifact or {}).get("next_verification_actions") or actions,
    ),
    "theme_name": (artifact or {}).get("theme_name"),
  }


def _priority_actions(next_actions: list[dict[str, Any]], *, limit: int = 3) -> list[dict[str, Any]]:
  return list(next_actions[:limit])


def _conclusion_candidates(digest: dict[str, Any] | None, web_summary: dict[str, Any]) -> list[str]:
  candidates: list[str] = []
  if digest:
    for signal in (digest.get("key_signals") or [])[:3]:
      title = str(signal.get("title") or "").strip()
      if title:
        candidates.append(f"[digest candidate] {title} — review_status=needs_human_review")
  if web_summary.get("artifact_exists"):
    for signal in (web_summary.get("web_signals") or [])[:2]:
      title = str(signal.get("title") or "").strip()
      if title:
        candidates.append(f"[web signal candidate] {title} — confidence=candidate")
  if not candidates:
    candidates.append("今週の結論候補は未整理です。Digest Preview または Web Signal artifact を確認してください。")
  return candidates[:3]


def _weekly_change_candidates(digest: dict[str, Any] | None, web_summary: dict[str, Any]) -> list[str]:
  changes: list[str] = []
  if web_summary.get("artifact_exists"):
    changes.append(
      f"Web Signal collection: {web_summary.get('result_count')} candidate(s) — 原典未確認",
    )
  if digest:
    changes.append(f"Digest Preview updated for theme: {digest.get('theme_name')}")
  if not changes:
    changes.append("今週の変化候補は artifact からは検出されませんでした。")
  return changes[:3]


def build_strategic_watch_brief_payload(
  output_root: Path | str,
  *,
  evidence_gap_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
  gap_payload = evidence_gap_payload or build_evidence_gap_payload(output_root)
  digest = load_latest_live_digest_preview(output_root)
  web_summary = read_latest_web_signal_artifact_summary(output_root)
  theme_name = str(gap_payload.get("theme_name") or (digest or {}).get("theme_name") or "Unknown Theme")
  next_actions = list(gap_payload.get("next_verification_actions") or [])
  priority = _priority_actions(next_actions, limit=3)

  source_paths = list(gap_payload.get("source_artifact_paths") or [])
  gap_path = find_latest_evidence_gap_path(output_root)
  if gap_path:
    source_paths.append(str(gap_path))
  from tech_cartography.services.live_weekly_decision_cockpit import find_latest_weekly_decision_cockpit_path

  cockpit_path = find_latest_weekly_decision_cockpit_path(output_root)

  return {
    "action_type": ACTION_TYPE,
    "status": "success",
    "theme_name": theme_name,
    "source_artifact_paths": source_paths,
    "latest_weekly_decision_cockpit_path": str(cockpit_path) if cockpit_path else None,
    "weekly_conclusion_candidates": _conclusion_candidates(digest, web_summary),
    "weekly_change_candidates": _weekly_change_candidates(digest, web_summary),
    "evidence_gaps": gap_payload.get("evidence_gaps") or [],
    "next_verification_actions": next_actions,
    "source_coverage": gap_payload.get("source_coverage") or {},
    "what_not_to_conclude": gap_payload.get("what_not_to_conclude") or [],
    "recommended_next_human_actions": [
      {
        "priority": index,
        "action": item.get("action"),
        "owner": item.get("recommended_owner"),
        "urgency": item.get("urgency"),
        "primary_source_hint": "Open original URL or patent document — do not rely on snippet alone.",
      }
      for index, item in enumerate(priority, start=1)
    ],
    "candidate_only_notice": CANDIDATE_NOTICE,
    "reading_order": [
      "1. 今週見るべき結論候補（候補のみ）",
      "2. 今週の変化候補",
      "3. Evidence Gap（何が未確認か）",
      "4. Next Verification Actions（優先3件）",
      "5. What Not To Conclude",
    ],
    "safety_flags": default_safety_flags(),
  }


def render_strategic_watch_brief_markdown(payload: dict[str, Any]) -> str:
  lines = [
    "# Strategic Watch Brief",
    "",
    f"> {payload.get('candidate_only_notice')}",
    "",
    f"**theme:** {payload.get('theme_name')}",
    "",
    "## 読む順番",
    "",
  ]
  for step in payload.get("reading_order") or []:
    lines.append(f"- {step}")
  lines.extend(["", "## 今週見るべき結論候補", ""])
  for item in payload.get("weekly_conclusion_candidates") or []:
    lines.append(f"- {item}")
  lines.extend(["", "## 今週の変化候補", ""])
  for item in payload.get("weekly_change_candidates") or []:
    lines.append(f"- {item}")
  lines.extend(["", "## Evidence Gap（上位3件）", ""])
  for gap in (payload.get("evidence_gaps") or [])[:3]:
    lines.append(f"- **{gap.get('gap_id')}** [{gap.get('urgency')}] {gap.get('observation')}")
  lines.extend(["", "## Next Verification Actions（優先3件）", ""])
  for action in (payload.get("recommended_next_human_actions") or [])[:3]:
    lines.append(f"{action.get('priority')}. [{action.get('urgency')}] {action.get('action')} — {action.get('owner')}")
    lines.append(f"   - primary source: {action.get('primary_source_hint')}")
  lines.extend(["", "## What Not To Conclude", ""])
  for item in payload.get("what_not_to_conclude") or []:
    lines.append(f"- {item}")
  lines.extend(["", "## Source Coverage", "", f"```json\n{json.dumps(payload.get('source_coverage') or {}, ensure_ascii=False, indent=2)}\n```"])
  return "\n".join(lines).strip() + "\n"


def _assert_safe_serialized(serialized: str) -> None:
  if _SENSITIVE_PATTERN.search(serialized):
    raise ValueError("Refusing to save strategic watch brief containing sensitive material")


def save_strategic_watch_brief(payload: dict[str, Any], output_root: Path | str) -> dict[str, str]:
  out_dir = get_live_strategic_watch_brief_dir(output_root)
  writable, message = check_directory_writable(out_dir)
  if not writable:
    raise ValueError(message or str(out_dir))

  timestamp = str(payload.get("timestamp") or _utc_now_iso())
  run_id = str(payload.get("run_id") or generate_run_id())
  slug = _timestamp_slug(timestamp)
  json_path = out_dir / f"live_strategic_watch_brief_{slug}_{run_id}.json"
  md_path = out_dir / f"live_strategic_watch_brief_{slug}_{run_id}.md"
  json_text = json.dumps(payload, ensure_ascii=False, indent=2)
  _assert_safe_serialized(json_text)
  json_path.write_text(json_text + "\n", encoding="utf-8")
  md_path.write_text(render_strategic_watch_brief_markdown(payload), encoding="utf-8")
  return {"json": str(json_path), "markdown": str(md_path)}


def run_live_strategic_watch_brief_build(
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
    meta = default_safety_flags()
    meta["gap_count"] = len((payload or {}).get("evidence_gaps") or [])
    meta["next_action_count"] = len((payload or {}).get("next_verification_actions") or [])
    record_live_run(
      action_type=ACTION_TYPE,
      status=map_result_status(ok=result.get("ok"), error=result.get("error")),
      run_id=run_id,
      started_at=started_at,
      user_context=resolved_ctx,
      theme_name=(payload or {}).get("theme_name"),
      input_summary="strategic watch brief",
      output_artifact_paths=result.get("saved_paths") or {},
      source_artifact_paths=list((payload or {}).get("source_artifact_paths") or []),
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
    gap_artifact = load_latest_evidence_gap_artifact(output_root)
    gap_payload = gap_artifact if gap_artifact else build_evidence_gap_payload(output_root)
    payload = build_strategic_watch_brief_payload(output_root, evidence_gap_payload=gap_payload)
    payload["run_id"] = run_id
    payload["timestamp"] = started_at
    payload = attach_user_run_metadata(payload, user_context=resolved_ctx, run_id=run_id)
    saved_paths = save_strategic_watch_brief(payload, output_root)
  except (OSError, ValueError) as exc:
    return _finalize({"ok": False, "error": "save_failed", "message": str(exc)})

  return _finalize(
    {
      "ok": True,
      "message": "Strategic Watch Brief を生成しました。",
      "payload": payload,
      "saved_paths": saved_paths,
    },
    payload=payload,
  )
