"""Live weekly operation cycle status aggregation (Phase 25K)."""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tech_cartography.runtime.cloud_run_config import (
  is_email_send_disabled,
  is_external_api_disabled,
  is_scheduler_disabled,
)
from tech_cartography.runtime.live_artifact_paths import (
  LIVE_OUTPUTS_ROOT_ENV,
  _count_json_artifacts,
  check_directory_writable,
  get_live_digest_preview_dir,
  get_live_email_send_dir,
  get_live_next_cycle_search_dir,
  get_live_next_cycle_web_signals_dir,
  get_live_operation_status_dir,
  get_live_outputs_root,
  get_live_watch_expansion_dir,
  get_live_watch_profiles_dir,
  get_live_web_signals_dir,
  using_live_outputs_root_env,
)
from tech_cartography.services.live_run_history import (
  attach_user_run_metadata,
  generate_run_id,
  map_result_status,
  record_live_run,
  summarize_run_history_for_console,
)
from tech_cartography.runtime.external_api_operation_config import describe_external_api_collection_runtime
from tech_cartography.services.live_watch_profile_manager import describe_watch_profile_status
from tech_cartography.services.live_web_signal_artifact_reader import describe_latest_web_signal_artifact
from tech_cartography.services.live_web_signal_collector import describe_latest_web_signal_collection
from tech_cartography.services.live_evidence_gap_builder import describe_latest_evidence_gap
from tech_cartography.services.live_strategic_watch_brief import describe_latest_strategic_watch_brief
from tech_cartography.services.watch_profile_draft import (
  find_latest_watch_profile_draft_path,
  load_watch_profile_draft_with_status,
)

STEP_ORDER: tuple[str, ...] = (
  "web_signal_pack",
  "digest_preview",
  "self_only_email",
  "watch_expansion_proposal",
  "watch_profile_draft",
  "next_cycle_search_plan",
  "next_cycle_web_signal_pack",
)

SAFETY_NOTICE = (
  "This operation console summarizes Live artifact status for manual weekly review. "
  "Artifacts are Web Signal candidates — not confirmed facts. "
  "Not for FTO, infringement, or validity analysis. "
  "No automatic execution, scheduler, or broadcast email occurs in this phase."
)

STEP_GUIDANCE: dict[str, str] = {
  "web_signal_pack": "Web Signal Packは入力・実行タブの Live Web Signal Pack から作成してください。",
  "digest_preview": "Digest Previewは Live Digest Mail Preview から作成してください（送信なし）。",
  "self_only_email": "Self-only Email Send Test から自分宛て1通のみ送信できます。",
  "watch_expansion_proposal": "Watch Expansion Proposals から拡張候補を作成してください。",
  "watch_profile_draft": "Watch Expansion Proposals で承認した項目を Watch Profile Draft に保存してください。",
  "next_cycle_search_plan": "Next Cycle Search から次回検索クエリ候補を作成してください。",
  "next_cycle_web_signal_pack": "Next Cycle Search で選択 query のみ Tavily 実行し、Next Cycle Web Signal Pack を作成してください。",
}

_SENSITIVE_PATTERN = re.compile(r"(api[_-]?key|authorization|oauth|jwt|smtp_password)", re.IGNORECASE)

_ARTIFACT_SPECS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
  ("web_signal_pack", "live_web_signals", "live_web_signal_pack_*.json", ("fetched_at", "created_at")),
  ("digest_preview", "live_digest_preview", "live_digest_preview_*.json", ("created_at",)),
  ("self_only_email", "live_email_send", "live_email_send_*.json", ("sent_at", "created_at")),
  (
    "watch_expansion_proposal",
    "live_watch_expansion",
    "live_watch_expansion_proposals_*.json",
    ("created_at",),
  ),
  ("next_cycle_search_plan", "live_next_cycle_search", "next_cycle_search_plan_*.json", ("created_at",)),
  (
    "next_cycle_web_signal_pack",
    "live_next_cycle_web_signals",
    "next_cycle_web_signal_pack_*.json",
    ("fetched_at", "created_at"),
  ),
)

_DIR_GETTERS = {
  "live_web_signals": get_live_web_signals_dir,
  "live_digest_preview": get_live_digest_preview_dir,
  "live_email_send": get_live_email_send_dir,
  "live_watch_expansion": get_live_watch_expansion_dir,
  "live_watch_profiles": get_live_watch_profiles_dir,
  "live_next_cycle_search": get_live_next_cycle_search_dir,
  "live_next_cycle_web_signals": get_live_next_cycle_web_signals_dir,
}


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _timestamp_slug(iso_ts: str) -> str:
  return iso_ts.replace(":", "").replace("-", "")


def _path_sort_key(path: Path) -> tuple[str, float]:
  slug = path.stem
  try:
    mtime = float(path.stat().st_mtime)
  except OSError:
    mtime = 0.0
  return slug, mtime


def _extract_created_at(payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
  for key in keys:
    value = payload.get(key)
    if value:
      return str(value)
  return None


def _load_json_safe(path: Path) -> dict[str, Any] | None:
  try:
    data = json.loads(path.read_text(encoding="utf-8"))
  except (OSError, json.JSONDecodeError):
    return None
  return data if isinstance(data, dict) else None


def _assert_no_sensitive_material(serialized: str) -> None:
  if _SENSITIVE_PATTERN.search(serialized):
    raise ValueError("Refusing to save operation status containing sensitive material")


def _scan_directory_artifact(
  *,
  project_root: Path | str | None,
  dir_key: str,
  pattern: str,
  created_at_keys: tuple[str, ...],
) -> dict[str, Any]:
  getter = _DIR_GETTERS[dir_key]
  directory = getter(project_root)
  count = _count_json_artifacts(directory, pattern)
  latest_path: Path | None = None
  latest_created_at: str | None = None
  if directory.is_dir():
    files = sorted(directory.glob(pattern), key=_path_sort_key, reverse=True)
    if files:
      latest_path = files[0]
      payload = _load_json_safe(latest_path)
      if payload:
        latest_created_at = _extract_created_at(payload, created_at_keys)
  return {
    "latest_path": str(latest_path) if latest_path else None,
    "latest_created_at": latest_created_at,
    "count": count,
  }


def _scan_watch_profile_draft(project_root: Path | str | None) -> dict[str, Any]:
  latest_path = find_latest_watch_profile_draft_path(project_root)
  count = len(list_watch_profile_draft_json_paths_safe(project_root))
  latest_created_at: str | None = None
  if latest_path is not None:
    draft, status, _message = load_watch_profile_draft_with_status(latest_path)
    if status == "ok" and draft:
      latest_created_at = str(draft.get("approved_at") or draft.get("created_at") or "") or None
  return {
    "latest_path": str(latest_path) if latest_path else None,
    "latest_created_at": latest_created_at,
    "count": count,
  }


def list_watch_profile_draft_json_paths_safe(project_root: Path | str | None) -> list[Path]:
  from tech_cartography.services.watch_profile_draft import list_watch_profile_draft_json_paths

  return list_watch_profile_draft_json_paths(project_root)


def _build_step(
  *,
  step_name: str,
  artifact: dict[str, Any],
  status: str,
  next_action: str,
) -> dict[str, Any]:
  return {
    "status": status,
    "latest_path": artifact.get("latest_path"),
    "latest_created_at": artifact.get("latest_created_at"),
    "count": artifact.get("count", 0),
    "next_action": next_action,
    "guidance": STEP_GUIDANCE.get(step_name, ""),
  }


def _web_signal_digest_next_action(
  artifact_info: dict[str, Any],
  digest_uses_web_signals: bool,
) -> str:
  if not artifact_info.get("latest_web_signal_artifact_exists"):
    return "Web Signal 手動収集後、Digest Preview に候補セクションを統合してください。"
  if not digest_uses_web_signals:
    return "最新 Web Signal artifact を確認し、Digest Preview を手動作成してください。"
  return "Digest Preview の Web Signal候補セクションを人間が確認してください（候補情報のみ）。"


def _digest_preview_uses_web_signals(project_root: Path | str | None) -> bool:
  from tech_cartography.services.live_digest_preview import load_latest_live_digest_preview

  preview = load_latest_live_digest_preview(project_root or Path.cwd())
  if not preview:
    return False
  if preview.get("uses_web_signals"):
    return True
  return bool(preview.get("source_web_signal_artifact") or preview.get("web_signal_review_id"))


def _evidence_gap_brief_next_action(
  gap_info: dict[str, Any],
  brief_info: dict[str, Any],
) -> str:
  if not gap_info.get("latest_evidence_gap_artifact_exists"):
    return "Evidence Gap を手動生成し、未確認事項を構造化してください。"
  if not brief_info.get("latest_strategic_watch_brief_exists"):
    return "Strategic Watch Brief を手動生成し、週30分で読める優先確認事項を確認してください。"
  return "Strategic Watch Brief の Next Verification Actions（優先3件）を人間が確認してください。"


def _web_signal_collection_next_action(
  external_api_info: dict[str, object],
  watch_profile_info: dict[str, Any],
  collection_info: dict[str, Any],
) -> str:
  if external_api_info.get("disable_external_api"):
    return "外部APIは停止中です。手動収集する場合は DISABLE_EXTERNAL_API=false と ENABLE_MANUAL_WEB_SIGNAL_COLLECTION=true を設定してください。"
  if not external_api_info.get("enable_manual_web_signal_collection"):
    return "手動 Web Signal 収集は無効です。ENABLE_MANUAL_WEB_SIGNAL_COLLECTION=true で有効化してください。"
  if not watch_profile_info.get("active_watch_profile_exists"):
    return "active Watch Profile を用意してから Web Signal 手動収集を実行してください。"
  if not external_api_info.get("tavily_secret_configured"):
    return "TAVILY_API_KEY を設定してから Web Signal 手動収集を実行してください。"
  if collection_info.get("latest_web_signal_collection_status") == "success":
    return "最新 Web Signal collection を確認し、Digest Preview を手動作成してください。"
  return "Web Signal 手動収集（確認文付き）を実行してください。"


def build_operation_cycle_status(
  project_root: Path | str | None = None,
  *,
  user_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
  """Aggregate live artifact step status. Never raises; no secrets."""
  checked_at = _utc_now_iso()
  active_storage_root = str(get_live_outputs_root(project_root))
  run_history_summary = summarize_run_history_for_console(
    project_root,
    viewer_user_context=user_context,
  )

  artifacts: dict[str, dict[str, Any]] = {}
  for step_name, dir_key, pattern, created_at_keys in _ARTIFACT_SPECS:
    artifacts[step_name] = _scan_directory_artifact(
      project_root=project_root,
      dir_key=dir_key,
      pattern=pattern,
      created_at_keys=created_at_keys,
    )
  artifacts["watch_profile_draft"] = _scan_watch_profile_draft(project_root)

  step_statuses: dict[str, dict[str, Any]] = {}
  warnings: list[str] = []

  if is_external_api_disabled():
    warnings.append("DISABLE_EXTERNAL_API=true — Tavily 実行はブロックされます。")
  if is_email_send_disabled():
    warnings.append("DISABLE_EMAIL_SEND=true — メール送信はブロックされます。")
  if is_scheduler_disabled():
    warnings.append("DISABLE_SCHEDULER=true — scheduler は OFF です（手動運用）。")

  def has_artifact(step: str) -> bool:
    return bool(artifacts.get(step, {}).get("latest_path"))

  # web_signal_pack
  if has_artifact("web_signal_pack"):
    step_statuses["web_signal_pack"] = _build_step(
      step_name="web_signal_pack",
      artifact=artifacts["web_signal_pack"],
      status="done",
      next_action="Digest Preview を作成してください。",
    )
  else:
    step_statuses["web_signal_pack"] = _build_step(
      step_name="web_signal_pack",
      artifact=artifacts["web_signal_pack"],
      status="missing",
      next_action="Live Web Signal Pack を作成してください。",
    )

  # digest_preview
  if has_artifact("digest_preview"):
    step_statuses["digest_preview"] = _build_step(
      step_name="digest_preview",
      artifact=artifacts["digest_preview"],
      status="done",
      next_action="必要なら Self-only Email Send Test を実行してください。",
    )
  elif has_artifact("web_signal_pack"):
    step_statuses["digest_preview"] = _build_step(
      step_name="digest_preview",
      artifact=artifacts["digest_preview"],
      status="ready",
      next_action="Live Digest Mail Preview から下書きを作成してください。",
    )
  else:
    step_statuses["digest_preview"] = _build_step(
      step_name="digest_preview",
      artifact=artifacts["digest_preview"],
      status="missing",
      next_action="先に Web Signal Pack を作成してください。",
    )

  # self_only_email
  if has_artifact("self_only_email"):
    step_statuses["self_only_email"] = _build_step(
      step_name="self_only_email",
      artifact=artifacts["self_only_email"],
      status="done",
      next_action="Watch Expansion Proposals を作成してください。",
    )
  elif is_email_send_disabled():
    step_statuses["self_only_email"] = _build_step(
      step_name="self_only_email",
      artifact=artifacts["self_only_email"],
      status="blocked",
      next_action="DISABLE_EMAIL_SEND=false にして Self-only Email Send Test を実行できます。",
    )
  elif has_artifact("digest_preview"):
    step_statuses["self_only_email"] = _build_step(
      step_name="self_only_email",
      artifact=artifacts["self_only_email"],
      status="ready",
      next_action="Self-only Email Send Test から自分宛て1通のみ送信してください。",
    )
  else:
    step_statuses["self_only_email"] = _build_step(
      step_name="self_only_email",
      artifact=artifacts["self_only_email"],
      status="missing",
      next_action="先に Digest Preview を作成してください。",
    )

  # watch_expansion_proposal
  if has_artifact("watch_expansion_proposal"):
    step_statuses["watch_expansion_proposal"] = _build_step(
      step_name="watch_expansion_proposal",
      artifact=artifacts["watch_expansion_proposal"],
      status="done",
      next_action="Watch Expansion Proposals で承認し Watch Profile Draft を保存してください。",
    )
  else:
    step_statuses["watch_expansion_proposal"] = _build_step(
      step_name="watch_expansion_proposal",
      artifact=artifacts["watch_expansion_proposal"],
      status="missing",
      next_action="Watch Expansion Proposals から拡張候補を作成してください。",
    )

  # watch_profile_draft
  if has_artifact("watch_profile_draft"):
    step_statuses["watch_profile_draft"] = _build_step(
      step_name="watch_profile_draft",
      artifact=artifacts["watch_profile_draft"],
      status="done",
      next_action="Next Cycle Search で次回 query 候補を作成してください。",
    )
  else:
    step_statuses["watch_profile_draft"] = _build_step(
      step_name="watch_profile_draft",
      artifact=artifacts["watch_profile_draft"],
      status="missing",
      next_action="Watch Expansion Proposals で承認済み Draft を保存してください。",
    )

  # next_cycle_search_plan
  if has_artifact("next_cycle_search_plan"):
    step_statuses["next_cycle_search_plan"] = _build_step(
      step_name="next_cycle_search_plan",
      artifact=artifacts["next_cycle_search_plan"],
      status="done",
      next_action="Next Cycle Search で選択 query を実行してください。",
    )
  elif has_artifact("watch_profile_draft"):
    step_statuses["next_cycle_search_plan"] = _build_step(
      step_name="next_cycle_search_plan",
      artifact=artifacts["next_cycle_search_plan"],
      status="ready",
      next_action="Next Cycle Search から次回検索クエリ候補を作成してください。",
    )
  else:
    step_statuses["next_cycle_search_plan"] = _build_step(
      step_name="next_cycle_search_plan",
      artifact=artifacts["next_cycle_search_plan"],
      status="missing",
      next_action="先に Watch Profile Draft を承認保存してください。",
    )

  # next_cycle_web_signal_pack
  if has_artifact("next_cycle_web_signal_pack"):
    step_statuses["next_cycle_web_signal_pack"] = _build_step(
      step_name="next_cycle_web_signal_pack",
      artifact=artifacts["next_cycle_web_signal_pack"],
      status="done",
      next_action="週次サイクルの手動確認を完了し、必要なら Digest Preview を更新してください。",
    )
  elif has_artifact("next_cycle_search_plan"):
    if is_external_api_disabled():
      step_statuses["next_cycle_web_signal_pack"] = _build_step(
        step_name="next_cycle_web_signal_pack",
        artifact=artifacts["next_cycle_web_signal_pack"],
        status="ready",
        next_action=(
          "外部APIを一時的にONにして、Next Cycle Search から選択 query のみ実行してください。"
        ),
      )
    else:
      step_statuses["next_cycle_web_signal_pack"] = _build_step(
        step_name="next_cycle_web_signal_pack",
        artifact=artifacts["next_cycle_web_signal_pack"],
        status="ready",
        next_action="Next Cycle Search で選択 query を1件だけ実行し、Next Cycle Web Signal Pack を作成してください。",
      )
  else:
    step_statuses["next_cycle_web_signal_pack"] = _build_step(
      step_name="next_cycle_web_signal_pack",
      artifact=artifacts["next_cycle_web_signal_pack"],
      status="missing",
      next_action="先に Next Cycle Search Plan を作成してください。",
    )

  next_recommended_action = _derive_next_recommended_action(step_statuses)
  watch_profile_info = describe_watch_profile_status(project_root or Path.cwd())
  external_api_info = describe_external_api_collection_runtime()
  web_signal_collection_info = describe_latest_web_signal_collection(project_root or Path.cwd())
  web_signal_artifact_info = describe_latest_web_signal_artifact(project_root or Path.cwd())
  evidence_gap_info = describe_latest_evidence_gap(project_root or Path.cwd())
  strategic_brief_info = describe_latest_strategic_watch_brief(project_root or Path.cwd())
  digest_uses_web_signals = _digest_preview_uses_web_signals(project_root)
  if watch_profile_info.get("watch_profile_status") == "no_active_profile":
    warnings.append("active Watch Profile がありません。週次監視条件を draft 作成後に active 化してください。")
  elif watch_profile_info.get("watch_profile_status") == "draft_waiting_approval":
    warnings.append("Watch Profile draft が承認待ちです。admin が確認文付きで active 化してください。")
  elif watch_profile_info.get("watch_profile_status") == "profile_misconfigured":
    warnings.append("Watch Profile draft の検索条件が未設定です。search_keywords または search_queries を設定してください。")
  latest_failed = run_history_summary.get("latest_failed_or_blocked")
  if latest_failed:
    warnings.append(
      "直近の失敗/ブロック実行: "
      f"{latest_failed.get('action_type')} ({latest_failed.get('status')}) — "
      f"{latest_failed.get('error_summary') or '詳細は Run History を確認してください。'}"
    )
  latest_artifact_paths = {
    step: (artifacts.get(step) or {}).get("latest_path")
    for step in STEP_ORDER
    if (artifacts.get(step) or {}).get("latest_path")
  }

  env_value = str(os.environ.get(LIVE_OUTPUTS_ROOT_ENV, "") or "").strip()
  return {
    "cycle_id": str(uuid.uuid4()),
    "checked_at": checked_at,
    "active_storage_root": active_storage_root,
    "live_outputs_root_env": env_value or "(unset — local outputs fallback)",
    "using_env_override": using_live_outputs_root_env(),
    "latest_artifacts": artifacts,
    "step_statuses": step_statuses,
    "next_recommended_action": next_recommended_action,
    "warnings": warnings,
    "safety_notice": SAFETY_NOTICE,
    "runtime_flags": {
      "external_api_disabled": is_external_api_disabled(),
      "email_send_disabled": is_email_send_disabled(),
      "scheduler_disabled": is_scheduler_disabled(),
    },
    "watch_profile": watch_profile_info,
    "active_watch_profile_exists": watch_profile_info.get("active_watch_profile_exists"),
    "active_watch_profile_path": watch_profile_info.get("active_watch_profile_path"),
    "active_watch_profile_theme": watch_profile_info.get("active_watch_profile_theme"),
    "latest_draft_exists": watch_profile_info.get("latest_draft_exists"),
    "latest_draft_path": watch_profile_info.get("latest_draft_path"),
    "latest_draft_theme": watch_profile_info.get("latest_draft_theme"),
    "watch_profile_status": watch_profile_info.get("watch_profile_status"),
    "watch_profile_next_recommended_action": watch_profile_info.get("next_recommended_action"),
    "external_api_collection": external_api_info,
    "disable_external_api": external_api_info.get("disable_external_api"),
    "enable_manual_web_signal_collection": external_api_info.get("enable_manual_web_signal_collection"),
    "tavily_secret_configured": external_api_info.get("tavily_secret_configured"),
    "latest_web_signal_collection_artifact": web_signal_collection_info.get("latest_web_signal_collection_artifact"),
    "latest_web_signal_collection_status": web_signal_collection_info.get("latest_web_signal_collection_status"),
    "latest_web_signal_result_count": web_signal_collection_info.get("latest_web_signal_result_count"),
    "web_signal_collection_next_recommended_action": _web_signal_collection_next_action(
      external_api_info,
      watch_profile_info,
      web_signal_collection_info,
    ),
    "latest_web_signal_artifact_exists": web_signal_artifact_info.get("latest_web_signal_artifact_exists"),
    "latest_web_signal_artifact_path": web_signal_artifact_info.get("latest_web_signal_artifact_path"),
    "latest_digest_preview_uses_web_signals": digest_uses_web_signals,
    "web_signal_digest_next_recommended_action": _web_signal_digest_next_action(
      web_signal_artifact_info,
      digest_uses_web_signals,
    ),
    "latest_evidence_gap_artifact_exists": evidence_gap_info.get("latest_evidence_gap_artifact_exists"),
    "latest_evidence_gap_artifact_path": evidence_gap_info.get("latest_evidence_gap_artifact_path"),
    "latest_evidence_gap_count": evidence_gap_info.get("latest_evidence_gap_count"),
    "latest_strategic_watch_brief_exists": strategic_brief_info.get("latest_strategic_watch_brief_exists"),
    "latest_strategic_watch_brief_path": strategic_brief_info.get("latest_strategic_watch_brief_path"),
    "latest_next_verification_action_count": max(
      int(evidence_gap_info.get("latest_next_verification_action_count") or 0),
      int(strategic_brief_info.get("latest_next_verification_action_count") or 0),
    ),
    "evidence_gap_brief_next_recommended_action": _evidence_gap_brief_next_action(
      evidence_gap_info,
      strategic_brief_info,
    ),
    "latest_artifact_paths": latest_artifact_paths,
    "operation_cycle_status": step_statuses,
    "run_history_summary": run_history_summary,
  }


def _derive_next_recommended_action(step_statuses: dict[str, dict[str, Any]]) -> str:
  for step in STEP_ORDER:
    info = step_statuses.get(step) or {}
    status = str(info.get("status") or "missing")
    if status in {"missing", "ready", "blocked", "needs_review"}:
      return str(info.get("next_action") or STEP_GUIDANCE.get(step) or "手動で週次サイクルを確認してください。")
  return "週次サイクルの手動確認を完了しました。必要に応じて各 expander から更新してください。"


def render_operation_status_markdown(status: dict[str, Any]) -> str:
  lines = [
    "# Live Operation Status",
    "",
    f"- cycle_id: {status.get('cycle_id')}",
    f"- checked_at: {status.get('checked_at')}",
    f"- active_storage_root: {status.get('active_storage_root')}",
    "",
    "## Next recommended action",
    "",
    str(status.get("next_recommended_action") or ""),
    "",
    "## Step statuses",
    "",
  ]
  for index, step in enumerate(STEP_ORDER, start=1):
    info = (status.get("step_statuses") or {}).get(step) or {}
    lines.extend(
      [
        f"{index}. {step}: {info.get('status')}",
        f"   - latest_path: {info.get('latest_path')}",
        f"   - count: {info.get('count')}",
        f"   - next_action: {info.get('next_action')}",
        "",
      ],
    )
  if status.get("warnings"):
    lines.extend(["## Warnings", ""])
    for warning in status["warnings"]:
      lines.append(f"- {warning}")
    lines.append("")
  lines.extend(["## Safety notice", "", str(status.get("safety_notice") or SAFETY_NOTICE), ""])
  return "\n".join(lines).strip() + "\n"


def save_operation_cycle_status(
  status: dict[str, Any],
  project_root: Path | str | None = None,
) -> dict[str, str]:
  out_dir = get_live_operation_status_dir(project_root)
  writable, message = check_directory_writable(out_dir)
  if not writable:
    raise ValueError(message or f"Cannot write operation status to {out_dir}")

  checked_at = str(status.get("checked_at") or _utc_now_iso())
  slug = _timestamp_slug(checked_at)
  json_path = out_dir / f"live_operation_status_{slug}.json"
  md_path = out_dir / f"live_operation_status_{slug}.md"

  payload = {
    "cycle_id": status.get("cycle_id"),
    "checked_at": checked_at,
    "active_storage_root": status.get("active_storage_root"),
    "step_statuses": status.get("step_statuses"),
    "next_recommended_action": status.get("next_recommended_action"),
    "latest_artifact_paths": status.get("latest_artifact_paths"),
    "warnings": status.get("warnings"),
    "safety_notice": status.get("safety_notice"),
    "runtime_flags": status.get("runtime_flags"),
    "watch_profile": status.get("watch_profile"),
    "watch_profile_status": status.get("watch_profile_status"),
    "active_watch_profile_path": status.get("active_watch_profile_path"),
    "external_api_collection": status.get("external_api_collection"),
    "latest_web_signal_collection_artifact": status.get("latest_web_signal_collection_artifact"),
  }
  serialized = json.dumps(payload, indent=2, ensure_ascii=False)
  _assert_no_sensitive_material(serialized)
  json_path.write_text(serialized + "\n", encoding="utf-8")
  md_path.write_text(render_operation_status_markdown(status), encoding="utf-8")
  return {"json": str(json_path), "markdown": str(md_path)}


def find_latest_operation_status_path(project_root: Path | str | None = None) -> Path | None:
  directory = get_live_operation_status_dir(project_root)
  if not directory.is_dir():
    return None
  files = sorted(directory.glob("live_operation_status_*.json"), key=_path_sort_key, reverse=True)
  return files[0] if files else None


def load_latest_operation_status(project_root: Path | str | None = None) -> dict[str, Any] | None:
  latest = find_latest_operation_status_path(project_root)
  if latest is None:
    return None
  return _load_json_safe(latest)


def build_and_save_operation_cycle_status(
  project_root: Path | str | None = None,
  *,
  user_context: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, str] | None, str | None]:
  """Build status and persist snapshot. Returns (status, saved_paths, error_message)."""
  run_id = generate_run_id()
  started_at = _utc_now_iso()
  status = build_operation_cycle_status(project_root, user_context=user_context)
  status = attach_user_run_metadata(status, user_context=user_context, run_id=run_id)
  try:
    saved_paths = save_operation_cycle_status(status, project_root)
    record_live_run(
      action_type="live_operation_status",
      status="success",
      run_id=run_id,
      started_at=started_at,
      user_context=user_context,
      input_summary="operation cycle status snapshot",
      output_artifact_paths=saved_paths,
      project_root=project_root,
    )
  except (OSError, ValueError) as exc:
    record_live_run(
      action_type="live_operation_status",
      status="failed",
      run_id=run_id,
      started_at=started_at,
      user_context=user_context,
      input_summary="operation cycle status snapshot",
      error_summary=str(exc),
      project_root=project_root,
    )
    return status, None, str(exc)
  return status, saved_paths, None
