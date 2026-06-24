"""Evidence Gap builder — read existing artifacts only (Phase 25V)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tech_cartography.runtime.evidence_gap_schema import build_evidence_gap, default_safety_flags, validate_evidence_gap
from tech_cartography.runtime.live_artifact_paths import (
  check_directory_writable,
  get_live_evidence_gaps_dir,
  get_live_scheduler_dry_run_dir,
)
from tech_cartography.runtime.user_context import evaluate_live_admin_access, normalize_user_context
from tech_cartography.services.live_digest_preview import (
  find_latest_live_digest_preview_path,
  load_live_digest_preview,
)
from tech_cartography.services.live_run_history import (
  attach_user_run_metadata,
  generate_run_id,
  map_result_status,
  record_live_run,
)
from tech_cartography.services.live_web_signal_artifact_reader import read_latest_web_signal_artifact_summary
from tech_cartography.services.live_web_signal_review import build_web_signal_review
from tech_cartography.services.live_watch_profile_manager import get_active_watch_profile

ACTION_TYPE = "live_evidence_gap_build"

WHAT_NOT_TO_CONCLUDE: tuple[str, ...] = (
  "Web Signal entries are candidate information only — not confirmed market or legal facts.",
  "Digest Preview key signals are review candidates — not infringement, validity, or FTO conclusions.",
  "Absence of a gap in this artifact does not mean absence of risk in the real world.",
  "This build does not perform legal, FTO, infringement, or validity judgement.",
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


def find_latest_scheduler_dry_run_path(output_root: Path | str) -> Path | None:
  out_dir = get_live_scheduler_dry_run_dir(output_root)
  if not out_dir.is_dir():
    return None
  files = sorted(out_dir.glob("live_scheduler_dry_run_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
  return files[0] if files else None


def load_scheduler_dry_run(path: Path | str) -> dict[str, Any] | None:
  target = Path(path)
  if not target.exists():
    return None
  try:
    data = json.loads(target.read_text(encoding="utf-8"))
  except (OSError, json.JSONDecodeError):
    return None
  return data if isinstance(data, dict) else None


def find_latest_evidence_gap_path(output_root: Path | str) -> Path | None:
  out_dir = get_live_evidence_gaps_dir(output_root)
  if not out_dir.is_dir():
    return None
  files = sorted(out_dir.glob("live_evidence_gap_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
  return files[0] if files else None


def load_evidence_gap_artifact(path: Path | str) -> dict[str, Any] | None:
  target = Path(path)
  if not target.exists():
    return None
  try:
    data = json.loads(target.read_text(encoding="utf-8"))
  except (OSError, json.JSONDecodeError):
    return None
  return data if isinstance(data, dict) else None


def load_latest_evidence_gap_artifact(output_root: Path | str) -> dict[str, Any] | None:
  latest = find_latest_evidence_gap_path(output_root)
  if latest is None:
    return None
  return load_evidence_gap_artifact(latest)


def describe_latest_evidence_gap(output_root: Path | str) -> dict[str, Any]:
  path = find_latest_evidence_gap_path(output_root)
  artifact = load_evidence_gap_artifact(path) if path else None
  gaps = list((artifact or {}).get("evidence_gaps") or [])
  actions = list((artifact or {}).get("next_verification_actions") or [])
  return {
    "latest_evidence_gap_artifact_exists": bool(path and artifact),
    "latest_evidence_gap_artifact_path": str(path) if path else None,
    "latest_evidence_gap_count": len(gaps),
    "latest_next_verification_action_count": len(actions),
    "theme_name": (artifact or {}).get("theme_name"),
  }


def _assert_safe_serialized(serialized: str) -> None:
  if _SENSITIVE_PATTERN.search(serialized):
    raise ValueError("Refusing to save evidence gap artifact containing sensitive material")


def _source_coverage(source_paths: list[str], *, has_web: bool, has_digest: bool, has_profile: bool) -> dict[str, Any]:
  return {
    "watch_profile": has_profile,
    "digest_preview": has_digest,
    "web_signal": has_web,
    "scheduler_dry_run": any("scheduler_dry_run" in p for p in source_paths),
    "patent": False,
    "paper": False,
    "artifact_paths": source_paths,
  }


def _build_gaps_from_inputs(
  *,
  theme_name: str,
  active_profile: dict[str, Any] | None,
  active_path: str | None,
  digest: dict[str, Any] | None,
  digest_path: str | None,
  web_summary: dict[str, Any],
  web_review: dict[str, Any],
  dry_run: dict[str, Any] | None,
  dry_run_path: str | None,
) -> list[dict[str, Any]]:
  gaps: list[dict[str, Any]] = []
  source_paths_base = [p for p in (active_path, digest_path, web_summary.get("artifact_path"), dry_run_path) if p]

  if not active_profile:
    gaps.append(
      build_evidence_gap(
        theme_name=theme_name or "(unset)",
        observation="Active Watch Profile is missing.",
        source_types=["watch_profile"],
        support_level="no_direct_evidence",
        what_is_known="No active watch scope is saved for this cycle.",
        what_is_unknown="Which companies, queries, and technology axes to monitor this week.",
        missing_evidence="Active Watch Profile artifact",
        why_it_matters="Without a watch scope, weekly signals cannot be prioritized consistently.",
        next_verification_action="Save and activate a Watch Profile before interpreting signals.",
        recommended_owner="human_reviewer",
        urgency="high",
        confidence_label="needs_review",
        source_artifact_paths=source_paths_base,
      ),
    )

  if digest:
    for item in digest.get("evidence_gaps") or []:
      text = str(item).strip()
      if not text:
        continue
      gaps.append(
        build_evidence_gap(
          theme_name=theme_name,
          observation=f"Digest Preview notes an evidence gap: {text[:120]}",
          source_types=["digest_preview"],
          support_level="source_supported_but_unverified",
          what_is_known="Digest Preview lists this as a known limitation.",
          what_is_unknown="Whether primary sources close this gap.",
          missing_evidence=text,
          why_it_matters="Digest gaps highlight what the weekly pack does not prove.",
          next_verification_action="Open cited URLs or patents and verify against primary sources.",
          recommended_owner="researcher",
          urgency="medium",
          confidence_label="needs_review",
          source_artifact_paths=[digest_path] if digest_path else [],
        ),
      )

  if web_summary.get("artifact_exists"):
    signal_count = int(web_summary.get("result_count") or 0)
    gaps.append(
      build_evidence_gap(
        theme_name=theme_name,
        observation=f"{signal_count} Web Signal candidate(s) collected — none verified as facts.",
        source_types=["web_signal", "digest_preview"],
        support_level="multiple_candidate_sources" if signal_count > 1 else "single_candidate_source",
        what_is_known="Candidate titles, URLs, and domains from latest collection artifact.",
        what_is_unknown="Whether each candidate reflects verified market or technology change.",
        missing_evidence="Human primary-source verification for each candidate URL",
        why_it_matters="Web Signals are inputs to review — not conclusions.",
        next_verification_action="Review top candidate URLs and mark review_status after human check.",
        recommended_owner="human_reviewer",
        urgency="high" if signal_count else "medium",
        confidence_label="candidate",
        source_artifact_paths=[str(web_summary.get("artifact_path"))] if web_summary.get("artifact_path") else [],
      ),
    )
    if web_review.get("duplicate_url_count", 0) > 0:
      gaps.append(
        build_evidence_gap(
          theme_name=theme_name,
          observation="Duplicate URLs detected in Web Signal candidates.",
          source_types=["web_signal"],
          support_level="single_candidate_source",
          what_is_known=f"duplicate_url_count={web_review.get('duplicate_url_count')}",
          what_is_unknown="Which duplicate entries represent the same underlying event.",
          missing_evidence="Deduplicated candidate list after human review",
          why_it_matters="Duplicates can inflate perceived activity.",
          next_verification_action="Merge duplicate URLs before sharing weekly brief.",
          recommended_owner="researcher",
          urgency="low",
          confidence_label="weak_signal",
          source_artifact_paths=[str(web_summary.get("artifact_path"))] if web_summary.get("artifact_path") else [],
        ),
      )
  elif active_profile:
    gaps.append(
      build_evidence_gap(
        theme_name=theme_name,
        observation="Watch Profile is active but no Web Signal collection artifact exists.",
        source_types=["watch_profile"],
        support_level="no_direct_evidence",
        what_is_known=f"Active profile theme: {theme_name}",
        what_is_unknown="This week's external candidate signals for the watch scope.",
        missing_evidence="live_web_signal_collection artifact",
        why_it_matters="Weekly change detection needs candidate signals or an explicit no-signal note.",
        next_verification_action="Run manual Web Signal collection when approved, or document no external search this week.",
        recommended_owner="researcher",
        urgency="medium",
        confidence_label="needs_review",
        source_artifact_paths=[active_path] if active_path else [],
      ),
    )

  gaps.append(
    build_evidence_gap(
      theme_name=theme_name,
      observation="Patent / claim linkage is not included in live weekly artifacts.",
      source_types=["digest_preview", "watch_profile"],
      support_level="no_direct_evidence",
      what_is_known="Theme and watch scope from profile and digest.",
      what_is_unknown="Which patents or claims relate to each candidate signal.",
      missing_evidence="Patent-family mapping and claim excerpts",
      why_it_matters="Strategic watch without patent context risks missing IP relevance.",
      next_verification_action="Link promising signals to seed publications or patent search in a later step.",
      recommended_owner="patent_reader",
      urgency="medium",
      confidence_label="needs_review",
      source_artifact_paths=source_paths_base,
    ),
  )

  if dry_run and (dry_run.get("warnings") or []):
    gaps.append(
      build_evidence_gap(
        theme_name=theme_name,
        observation="Scheduler dry-run reported warnings for the weekly cycle.",
        source_types=["watch_profile", "web_signal"],
        support_level="source_supported_but_unverified",
        what_is_known="; ".join(str(w) for w in (dry_run.get("warnings") or [])[:3]),
        what_is_unknown="Whether the weekly cycle is ready for automated steps (none run in this phase).",
        missing_evidence="Resolved warnings from dry-run checklist",
        why_it_matters="Dry-run warnings highlight missing prerequisites.",
        next_verification_action="Resolve dry-run warnings manually before any future scheduler enablement.",
        recommended_owner="human_reviewer",
        urgency="medium",
        confidence_label="needs_review",
        source_artifact_paths=[dry_run_path] if dry_run_path else [],
      ),
    )

  if not gaps:
    gaps.append(
      build_evidence_gap(
        theme_name=theme_name or "(unset)",
        observation="Insufficient source artifacts to derive specific gaps.",
        source_types=["digest_preview"],
        support_level="no_direct_evidence",
        what_is_known="Builder ran without external API calls.",
        what_is_unknown="Weekly technology changes for the theme.",
        missing_evidence="Watch Profile, Digest Preview, or Web Signal artifacts",
        why_it_matters="Evidence gaps cannot be inferred without inputs.",
        next_verification_action="Create Watch Profile and Digest Preview, then rebuild evidence gaps.",
        recommended_owner="human_reviewer",
        urgency="medium",
        confidence_label="needs_review",
        source_artifact_paths=[],
      ),
    )

  return gaps


def _derive_next_verification_actions(gaps: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
  ranked = sorted(gaps, key=lambda g: (_URGENCY_ORDER.get(str(g.get("urgency")), 9), str(g.get("gap_id"))))
  actions: list[dict[str, Any]] = []
  for gap in ranked[:limit]:
    actions.append(
      {
        "gap_id": gap.get("gap_id"),
        "action": gap.get("next_verification_action"),
        "recommended_owner": gap.get("recommended_owner"),
        "urgency": gap.get("urgency"),
        "confidence_label": gap.get("confidence_label"),
        "theme_name": gap.get("theme_name"),
      },
    )
  return actions


def _weekly_decision_summary(gaps: list[dict[str, Any]], theme_name: str) -> str:
  high = sum(1 for g in gaps if g.get("urgency") == "high")
  return (
    f"Theme '{theme_name}': {len(gaps)} evidence gap(s), {high} high-urgency. "
    "Treat all inputs as candidates — confirm primary sources before decisions."
  )


def render_evidence_gap_markdown(payload: dict[str, Any]) -> str:
  lines = [
    "# Evidence Gap Build",
    "",
    f"- theme: {payload.get('theme_name')}",
    f"- status: {payload.get('status')}",
    f"- gap_count: {len(payload.get('evidence_gaps') or [])}",
    "",
    "> Candidate information only. Not legal / FTO / infringement / validity judgement.",
    "",
    "## What Not To Conclude",
    "",
  ]
  for item in payload.get("what_not_to_conclude") or []:
    lines.append(f"- {item}")
  lines.extend(["", "## Evidence Gaps", ""])
  for gap in payload.get("evidence_gaps") or []:
    lines.extend(
      [
        f"### {gap.get('gap_id')}",
        f"- observation: {gap.get('observation')}",
        f"- support_level: {gap.get('support_level')}",
        f"- urgency: {gap.get('urgency')}",
        f"- next: {gap.get('next_verification_action')}",
        "",
      ],
    )
  lines.extend(["## Next Verification Actions", ""])
  for index, action in enumerate(payload.get("next_verification_actions") or [], start=1):
    lines.append(f"{index}. [{action.get('urgency')}] {action.get('action')} ({action.get('recommended_owner')})")
  return "\n".join(lines).strip() + "\n"


def build_evidence_gap_payload(output_root: Path | str) -> dict[str, Any]:
  """Assemble evidence gap payload from existing artifacts. No external API."""
  active, active_path = get_active_watch_profile(output_root)
  theme_name = str((active or {}).get("theme_name") or "").strip() or "Unknown Theme"

  digest_path_obj = find_latest_live_digest_preview_path(output_root)
  digest_path = str(digest_path_obj) if digest_path_obj else None
  digest = load_live_digest_preview(digest_path_obj) if digest_path_obj else None
  if digest and not theme_name:
    theme_name = str(digest.get("theme_name") or theme_name)

  web_summary = read_latest_web_signal_artifact_summary(output_root)
  web_review = build_web_signal_review(output_root, source_summary=web_summary)

  dry_run_path_obj = find_latest_scheduler_dry_run_path(output_root)
  dry_run_path = str(dry_run_path_obj) if dry_run_path_obj else None
  dry_run = load_scheduler_dry_run(dry_run_path_obj) if dry_run_path_obj else None

  source_paths = [p for p in (active_path, digest_path, web_summary.get("artifact_path"), dry_run_path) if p]
  gaps = _build_gaps_from_inputs(
    theme_name=theme_name,
    active_profile=active,
    active_path=active_path,
    digest=digest,
    digest_path=digest_path,
    web_summary=web_summary,
    web_review=web_review,
    dry_run=dry_run,
    dry_run_path=dry_run_path,
  )
  for gap in gaps:
    errors = validate_evidence_gap(gap)
    if errors:
      raise ValueError(f"Invalid gap {gap.get('gap_id')}: {errors[0]}")

  next_actions = _derive_next_verification_actions(gaps)
  status = "skipped" if not active else "success"
  return {
    "action_type": ACTION_TYPE,
    "status": status,
    "theme_name": theme_name,
    "source_artifact_paths": source_paths,
    "evidence_gaps": gaps,
    "next_verification_actions": next_actions,
    "source_coverage": _source_coverage(
      source_paths,
      has_web=bool(web_summary.get("artifact_exists")),
      has_digest=bool(digest),
      has_profile=bool(active),
    ),
    "what_not_to_conclude": list(WHAT_NOT_TO_CONCLUDE),
    "weekly_decision_summary": _weekly_decision_summary(gaps, theme_name),
    "caution_summary": "All gaps are candidate-review boundaries — not confirmed facts or legal conclusions.",
    "safety_flags": default_safety_flags(),
    "warnings": [] if active else ["active Watch Profile がありません — skipped 扱いで gap を生成しました。"],
  }


def save_evidence_gap_artifact(payload: dict[str, Any], output_root: Path | str) -> dict[str, str]:
  out_dir = get_live_evidence_gaps_dir(output_root)
  writable, message = check_directory_writable(out_dir)
  if not writable:
    raise ValueError(message or str(out_dir))

  timestamp = str(payload.get("timestamp") or _utc_now_iso())
  run_id = str(payload.get("run_id") or generate_run_id())
  slug = _timestamp_slug(timestamp)
  json_path = out_dir / f"live_evidence_gap_{slug}_{run_id}.json"
  md_path = out_dir / f"live_evidence_gap_{slug}_{run_id}.md"
  json_text = json.dumps(payload, ensure_ascii=False, indent=2)
  _assert_safe_serialized(json_text)
  json_path.write_text(json_text + "\n", encoding="utf-8")
  md_path.write_text(render_evidence_gap_markdown(payload), encoding="utf-8")
  return {"json": str(json_path), "markdown": str(md_path)}


def run_live_evidence_gap_build(
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
      input_summary=(payload or {}).get("weekly_decision_summary"),
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
    payload = build_evidence_gap_payload(output_root)
    payload["run_id"] = run_id
    payload["timestamp"] = started_at
    payload = attach_user_run_metadata(payload, user_context=resolved_ctx, run_id=run_id)
    saved_paths = save_evidence_gap_artifact(payload, output_root)
  except (OSError, ValueError) as exc:
    return _finalize({"ok": False, "error": "save_failed", "message": str(exc)})

  skipped = payload.get("status") == "skipped"
  return _finalize(
    {
      "ok": True,
      "skipped": skipped,
      "message": "Evidence Gap を生成しました（skipped: active profile なし）。" if skipped else "Evidence Gap を生成しました。",
      "payload": payload,
      "saved_paths": saved_paths,
      "gap_count": len(payload.get("evidence_gaps") or []),
    },
    payload=payload,
  )
