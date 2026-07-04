"""Weekly signal watch scheduler for v9."""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from .digest_export import build_weekly_digest_markdown
from .email_delivery import (
  EmailDeliveryConfig,
  build_digest_email_preview,
  load_email_delivery_config,
  run_email_delivery_dry_run,
  save_email_delivery_log,
  send_digest_email_self_only,
)
from .paper_openalex_retrieval import build_openalex_paper_preview, execute_openalex_paper_retrieval
from .patent_bigquery_query import (
  build_patent_bigquery_preview,
  execute_patent_bigquery_retrieval,
  run_patent_bigquery_dry_run,
)
from .patent_bigquery_safety import BigQuerySafetyConfig
from .persistence import PROJECT_ROOT, ensure_v9_run_dirs, get_v9_runs_dir
from .retrieval_run_store import (
  build_retrieval_run_manifest,
  find_latest_compatible_manifest,
  load_candidates_from_manifest,
  save_retrieval_run_manifest,
  stable_payload_signature,
)
from .search_plan import build_unified_search_plan
from .signal_integration import apply_signal_change_tracking, integrate_multi_source_signals
from .signal_models import Signal, WatchProfile
from .snapshot_diff import compare_snapshots
from .watch_profile_schema import migrate_watch_profile
from .web_company_retrieval import build_global_web_retrieval_preview, execute_global_web_retrieval
from .weekly_run_config import (
  sanitize_weekly_run_config,
  validate_weekly_run_config,
)

WEEKLY_SCHEDULER_SCHEMA_VERSION = "v9.6b"
WEEKLY_STAGE_SEQUENCE = [
  "load_config",
  "load_watch_profile",
  "build_search_plan",
  "retrieve_patent",
  "retrieve_paper",
  "retrieve_web_company",
  "save_retrieval_manifest",
  "integrate_signals",
  "load_previous_success",
  "calculate_weekly_diff",
  "build_digest",
  "build_email_preview",
  "send_email",
  "finalize",
]
TERMINAL_WEEKLY_STATUSES = {"success", "partial_success", "blocked", "failed"}
SUCCESSFUL_WEEKLY_STATUSES = {"success", "partial_success"}
_LOCK_SIGNATURE_PATTERN = set("0123456789abcdef")
_SOURCE_TO_STAGE = {
  "patent": "retrieve_patent",
  "paper": "retrieve_paper",
  "web_company": "retrieve_web_company",
}
_SOURCE_RUN_SUBDIRS = {
  "patent": "patent_retrieval_runs",
  "paper": "paper_retrieval_runs",
  "web_company": "web_company_retrieval_runs",
}
_SOURCE_STAGED_FILENAMES = {
  "patent": "patent_candidates_staged.json",
  "paper": "paper_candidates_staged.json",
  "web_company": "web_company_candidates_staged.json",
}
_SOURCE_PLAN_FILENAMES = {
  "patent": "patent_query_plan.json",
  "paper": "paper_query_plan.json",
  "web_company": "global_web_query_plan.json",
}
_SOURCE_PROVIDER_LOG_FILENAMES = {
  "patent": "patent_retrieval_log.json",
  "paper": "paper_provider_log.json",
  "web_company": "global_web_provider_log.json",
}


def load_weekly_run_config(path) -> dict:
  from .weekly_run_config import load_weekly_run_config as _load

  return _load(path)


def validate_weekly_run_config(config: dict) -> dict:
  from .weekly_run_config import validate_weekly_run_config as _validate

  return _validate(config)


def acquire_weekly_run_lock(
  watch_profile_signature: str,
  run_id: str,
  lock_root,
  *,
  stale_timeout_seconds: int = 21600,
) -> dict:
  signature = str(watch_profile_signature or "").strip().lower()
  if len(signature) != 64 or any(char not in _LOCK_SIGNATURE_PATTERN for char in signature):
    raise ValueError("watch_profile_signature が不正です。")
  root = Path(lock_root)
  root.mkdir(parents=True, exist_ok=True)
  lock_path = (root / f"{signature}.lock").resolve()
  if root.resolve() not in {lock_path, *lock_path.parents}:
    raise ValueError("lock path が許可範囲外です。")
  now = datetime.now().astimezone()
  payload = {
    "schema_version": WEEKLY_SCHEDULER_SCHEMA_VERSION,
    "watch_profile_signature": signature,
    "run_id": str(run_id or "").strip(),
    "started_at": now.isoformat(timespec="seconds"),
    "stale_timeout_seconds": int(max(stale_timeout_seconds, 60)),
  }
  if lock_path.exists():
    existing = _read_lock_payload(lock_path)
    if _is_stale_lock(existing, stale_timeout_seconds=int(max(stale_timeout_seconds, 60)), now=now):
      try:
        lock_path.unlink()
      except OSError as exc:
        return {
          "acquired": False,
          "status": "blocked",
          "message": f"stale lock を削除できませんでした: {type(exc).__name__}",
          "path": str(lock_path),
          "payload": existing,
        }
    else:
      return {
        "acquired": False,
        "status": "blocked",
        "message": "同じ Watch Profile の実行中 lock が存在します。",
        "path": str(lock_path),
        "payload": existing,
      }
  flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
  try:
    fd = os.open(str(lock_path), flags)
  except FileExistsError:
    return {
      "acquired": False,
      "status": "blocked",
      "message": "同じ Watch Profile の実行中 lock が存在します。",
      "path": str(lock_path),
      "payload": _read_lock_payload(lock_path),
    }
  try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
      json.dump(payload, handle, ensure_ascii=False, indent=2)
      handle.write("\n")
  except Exception:
    try:
      lock_path.unlink()
    except OSError:
      pass
    raise
  return {
    "acquired": True,
    "status": "success",
    "message": "lock acquired",
    "path": str(lock_path),
    "payload": payload,
  }


def release_weekly_run_lock(lock_info: dict) -> None:
  path_text = str(dict(lock_info or {}).get("path", "") or "").strip()
  if not path_text:
    return
  path = Path(path_text)
  try:
    if path.exists():
      path.unlink()
  except OSError:
    return


def find_previous_successful_weekly_run(
  weekly_root,
  watch_profile_signature: str,
) -> dict | None:
  weekly_runs_root = _resolve_weekly_runs_root(weekly_root)
  signature = str(watch_profile_signature or "").strip()
  if not weekly_runs_root.exists():
    return None
  matches: list[dict[str, Any]] = []
  for status_path in weekly_runs_root.glob("*/weekly_run_status.json"):
    try:
      status_payload = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
      continue
    if str(status_payload.get("watch_profile_signature", "") or "") != signature:
      continue
    if str(status_payload.get("overall_status", "") or "") not in SUCCESSFUL_WEEKLY_STATUSES:
      continue
    run_dir = status_path.parent
    matches.append(
      {
        "weekly_run_id": str(status_payload.get("weekly_run_id", run_dir.name) or run_dir.name),
        "overall_status": str(status_payload.get("overall_status", "") or ""),
        "created_at": str(status_payload.get("created_at", "") or ""),
        "run_dir": run_dir,
        "status_path": status_path,
        "integrated_signals_path": run_dir / "integrated_signals.json",
        "weekly_diff_path": run_dir / "weekly_diff.json",
        "retrieval_manifest_path": run_dir / "retrieval_run_manifest.json",
      }
    )
  if not matches:
    return None
  matches.sort(key=lambda item: str(item.get("created_at", "") or ""), reverse=True)
  return matches[0]


def run_weekly_watch(
  config: dict,
  output_root,
  provider_adapters: dict | None = None,
) -> dict:
  provider_adapters = dict(provider_adapters or {})
  base_root = Path(output_root) if output_root is not None else get_v9_runs_dir()
  ensure_v9_run_dirs(base_root)
  weekly_runs_root = _resolve_weekly_runs_root(base_root)
  weekly_locks_root = _resolve_weekly_locks_root(base_root)
  weekly_run_id = _build_weekly_run_id(str(dict(config or {}).get("_run_id", "") or ""))
  run_dir = weekly_runs_root / weekly_run_id
  run_dir.mkdir(parents=True, exist_ok=True)

  stage_log = _initial_stage_log()
  provider_log: dict[str, Any] = {}
  watch_profile: dict[str, Any] | None = None
  watch_profile_signature = ""
  lock_info: dict[str, Any] | None = None
  retrieval_manifest: dict[str, Any] | None = None
  current_candidates = {"patent": [], "paper": [], "web_company": []}
  previous_run: dict[str, Any] | None = None
  integrated_payload: dict[str, Any] | None = None
  final_signals: list[dict[str, Any]] = []
  weekly_diff: dict[str, Any] | None = None
  digest_markdown = ""
  email_preview_payload: dict[str, Any] = {}
  created_at = _now_iso()

  config_validation = validate_weekly_run_config(config if isinstance(config, dict) else {})
  normalized_config = dict(config_validation.get("normalized_config", {}) or {})
  normalized_config["_run_id"] = weekly_run_id
  _write_json(run_dir / "weekly_run_config_snapshot.json", sanitize_weekly_run_config(normalized_config))

  try:
    if not isinstance(config, dict):
      _set_stage(stage_log, "load_config", "failed", message="config は dict である必要があります。")
      return _finalize_weekly_run(
        run_dir=run_dir,
        weekly_run_id=weekly_run_id,
        created_at=created_at,
        stage_log=stage_log,
        provider_log=provider_log,
        overall_status="failed",
        watch_profile_signature="",
        theme_name="",
        config=normalized_config,
        retrieval_manifest=None,
        integrated_payload=None,
        weekly_diff=None,
        digest_markdown="",
        email_preview_payload={},
      )

    if config_validation["errors"]:
      _set_stage(
        stage_log,
        "load_config",
        "blocked",
        message="weekly run config の設定不足により実行を停止しました。",
        errors=list(config_validation["errors"]),
        warnings=list(config_validation["warnings"]),
      )
      return _finalize_weekly_run(
        run_dir=run_dir,
        weekly_run_id=weekly_run_id,
        created_at=created_at,
        stage_log=stage_log,
        provider_log=provider_log,
        overall_status="blocked",
        watch_profile_signature="",
        theme_name="",
        config=normalized_config,
        retrieval_manifest=None,
        integrated_payload=None,
        weekly_diff=None,
        digest_markdown="",
        email_preview_payload={},
      )

    if not bool(normalized_config.get("enabled", False)):
      _set_stage(
        stage_log,
        "load_config",
        "blocked",
        message="enabled=false のため Scheduler 実行は停止しました。",
        warnings=list(config_validation["warnings"]),
      )
      return _finalize_weekly_run(
        run_dir=run_dir,
        weekly_run_id=weekly_run_id,
        created_at=created_at,
        stage_log=stage_log,
        provider_log=provider_log,
        overall_status="blocked",
        watch_profile_signature="",
        theme_name="",
        config=normalized_config,
        retrieval_manifest=None,
        integrated_payload=None,
        weekly_diff=None,
        digest_markdown="",
        email_preview_payload={},
      )

    _set_stage(
      stage_log,
      "load_config",
      "success",
      message="weekly run config を読み込みました。",
      warnings=list(config_validation["warnings"]),
    )

    try:
      watch_profile = _load_watch_profile_path(str(normalized_config.get("watch_profile_path", "") or ""))
      watch_profile_signature = stable_payload_signature(watch_profile)
      _set_stage(
        stage_log,
        "load_watch_profile",
        "success",
        message="Watch Profile を読み込みました。",
        details={
          "theme_name": str(watch_profile.get("theme_name", "") or ""),
          "watch_profile_signature": watch_profile_signature,
        },
      )
    except Exception as exc:  # noqa: BLE001
      _set_stage(
        stage_log,
        "load_watch_profile",
        "failed",
        message="Watch Profile の読込に失敗しました。",
        errors=[str(exc)],
      )
      return _finalize_weekly_run(
        run_dir=run_dir,
        weekly_run_id=weekly_run_id,
        created_at=created_at,
        stage_log=stage_log,
        provider_log=provider_log,
        overall_status="failed",
        watch_profile_signature=watch_profile_signature,
        theme_name=str((watch_profile or {}).get("theme_name", "") or ""),
        config=normalized_config,
        retrieval_manifest=None,
        integrated_payload=None,
        weekly_diff=None,
        digest_markdown="",
        email_preview_payload={},
      )

    lock_info = acquire_weekly_run_lock(
      watch_profile_signature,
      weekly_run_id,
      weekly_locks_root,
      stale_timeout_seconds=int(normalized_config.get("timeouts", {}).get("lock_stale_seconds", 21600) or 21600),
    )
    if not lock_info.get("acquired", False):
      _set_stage(
        stage_log,
        "build_search_plan",
        "blocked",
        message=str(lock_info.get("message", "") or "lock failed"),
      )
      return _finalize_weekly_run(
        run_dir=run_dir,
        weekly_run_id=weekly_run_id,
        created_at=created_at,
        stage_log=stage_log,
        provider_log=provider_log,
        overall_status="blocked",
        watch_profile_signature=watch_profile_signature,
        theme_name=str(watch_profile.get("theme_name", "") or ""),
        config=normalized_config,
        retrieval_manifest=None,
        integrated_payload=None,
        weekly_diff=None,
        digest_markdown="",
        email_preview_payload={},
      )

    total_limit = sum(
      int(normalized_config.get("limits", {}).get(key, 0) or 0)
      for key in ("patent_max_results", "paper_max_results", "web_max_results", "company_max_results")
    )
    search_plan = build_unified_search_plan(
      watch_profile,
      total_limit=total_limit,
      source_limits={
        "patent": int(normalized_config["limits"]["patent_max_results"]),
        "paper": int(normalized_config["limits"]["paper_max_results"]),
        "web": int(normalized_config["limits"]["web_max_results"]),
        "company": int(normalized_config["limits"]["company_max_results"]),
      },
    )
    _set_stage(
      stage_log,
      "build_search_plan",
      "success",
      message="検索計画を生成しました。",
      details={"total_limit": total_limit},
    )

    source_runs_for_manifest: dict[str, dict[str, Any]] = {}
    for source_type in ("patent", "paper", "web_company"):
      stage_name = _SOURCE_TO_STAGE[source_type]
      stage_result = _run_provider_stage(
        source_type=source_type,
        search_plan=search_plan,
        watch_profile=watch_profile,
        config=normalized_config,
        output_root=base_root,
        weekly_run_id=weekly_run_id,
        provider_adapters=provider_adapters,
      )
      current_candidates[source_type] = deepcopy(list(stage_result.get("rows", []) or []))
      provider_log[source_type] = dict(stage_result.get("provider_log", {}) or {})
      source_run = dict(stage_result.get("source_run", {}) or {})
      if source_run:
        source_runs_for_manifest[source_type] = source_run
      _set_stage(
        stage_log,
        stage_name,
        str(stage_result.get("status", "failed") or "failed"),
        message=str(stage_result.get("message", "") or ""),
        warnings=list(stage_result.get("warnings", []) or []),
        errors=list(stage_result.get("errors", []) or []),
        details=dict(stage_result.get("details", {}) or {}),
      )

    if source_runs_for_manifest:
      retrieval_manifest = build_retrieval_run_manifest(watch_profile, source_runs_for_manifest)
      save_retrieval_run_manifest(retrieval_manifest, base_root)
      _write_json(run_dir / "retrieval_run_manifest.json", retrieval_manifest)
      _set_stage(
        stage_log,
        "save_retrieval_manifest",
        "success" if str(retrieval_manifest.get("status", "") or "") == "success" else "partial_success",
        message="retrieval manifest を保存しました。",
        details={"manifest_id": str(retrieval_manifest.get("manifest_id", "") or "")},
      )
    else:
      if bool(normalized_config.get("execution", {}).get("dry_run", True)):
        retrieval_manifest = find_latest_compatible_manifest(base_root, watch_profile_signature)
        if retrieval_manifest is not None:
          loaded_bundle = load_candidates_from_manifest(retrieval_manifest)
          current_candidates = {
            "patent": deepcopy(list(loaded_bundle.get("candidates_by_source", {}).get("patent", []) or [])),
            "paper": deepcopy(list(loaded_bundle.get("candidates_by_source", {}).get("paper", []) or [])),
            "web_company": deepcopy(list(loaded_bundle.get("candidates_by_source", {}).get("web_company", []) or [])),
          }
          provider_log["reused_manifest"] = {
            "manifest_id": str(retrieval_manifest.get("manifest_id", "") or ""),
            "status": str(loaded_bundle.get("status", "") or ""),
            "warnings": list(loaded_bundle.get("warnings", []) or []),
          }
          _write_json(run_dir / "retrieval_run_manifest.json", retrieval_manifest)
          _set_stage(
            stage_log,
            "save_retrieval_manifest",
            "success" if int(loaded_bundle.get("total_candidate_count", 0) or 0) > 0 else "blocked",
            message="dry-run のため保存済み retrieval manifest を再利用しました。",
            warnings=list(loaded_bundle.get("warnings", []) or []),
            details={"manifest_id": str(retrieval_manifest.get("manifest_id", "") or "")},
          )
        else:
          _set_stage(
            stage_log,
            "save_retrieval_manifest",
            "blocked",
            message="dry-run で再利用可能な retrieval manifest が見つかりませんでした。",
          )
      else:
        _set_stage(
          stage_log,
          "save_retrieval_manifest",
          "failed",
          message="保存できる retrieval 候補がありません。",
        )

    total_candidate_count = sum(len(rows) for rows in current_candidates.values())
    if total_candidate_count <= 0:
      overall_status = "blocked" if bool(normalized_config.get("execution", {}).get("dry_run", True)) else "failed"
      return _finalize_weekly_run(
        run_dir=run_dir,
        weekly_run_id=weekly_run_id,
        created_at=created_at,
        stage_log=stage_log,
        provider_log=provider_log,
        overall_status=overall_status,
        watch_profile_signature=watch_profile_signature,
        theme_name=str(watch_profile.get("theme_name", "") or ""),
        config=normalized_config,
        retrieval_manifest=retrieval_manifest,
        integrated_payload=None,
        weekly_diff=None,
        digest_markdown="",
        email_preview_payload={
          "status": "blocked",
          "message": "取得候補が 0 件のため Email Preview を生成しませんでした。",
        },
      )

    integrated_payload = integrate_multi_source_signals(
      base_signals=[],
      watch_profile=watch_profile,
      patent_rows=current_candidates["patent"],
      paper_rows=current_candidates["paper"],
      web_company_rows=current_candidates["web_company"],
    )
    if int(integrated_payload.get("ranked_count", 0) or 0) <= 0:
      _set_stage(stage_log, "integrate_signals", "failed", message="統合 Signal が 0 件でした。")
      return _finalize_weekly_run(
        run_dir=run_dir,
        weekly_run_id=weekly_run_id,
        created_at=created_at,
        stage_log=stage_log,
        provider_log=provider_log,
        overall_status="failed",
        watch_profile_signature=watch_profile_signature,
        theme_name=str(watch_profile.get("theme_name", "") or ""),
        config=normalized_config,
        retrieval_manifest=retrieval_manifest,
        integrated_payload=integrated_payload,
        weekly_diff=None,
        digest_markdown="",
        email_preview_payload={},
      )
    _set_stage(
      stage_log,
      "integrate_signals",
      "success",
      message="Signal 統合・重複除去・ランキングを実行しました。",
      details={
        "raw_count": int(integrated_payload.get("raw_count", 0) or 0),
        "deduped_count": int(integrated_payload.get("deduped_count", 0) or 0),
        "ranked_count": int(integrated_payload.get("ranked_count", 0) or 0),
      },
    )

    previous_run = find_previous_successful_weekly_run(weekly_runs_root, watch_profile_signature)
    if previous_run is None:
      _set_stage(stage_log, "load_previous_success", "skipped", message="前回成功 run は見つかりませんでした。初回 run として扱います。")
      previous_signals = []
    else:
      previous_signals = _load_integrated_signals_from_run(previous_run)
      _set_stage(
        stage_log,
        "load_previous_success",
        "success",
        message="前回成功 run を読み込みました。",
        details={"previous_weekly_run_id": str(previous_run.get("weekly_run_id", "") or "")},
      )

    final_signals = apply_signal_change_tracking(list(integrated_payload.get("signals", []) or []), previous_signals)
    weekly_diff = compare_snapshots(previous_signals, list(integrated_payload.get("signals", []) or []))
    weekly_diff["previous_weekly_run_id"] = str((previous_run or {}).get("weekly_run_id", "") or "")
    weekly_diff["watch_profile_signature"] = watch_profile_signature
    _set_stage(
      stage_log,
      "calculate_weekly_diff",
      "success",
      message="前回成功 run との差分を計算しました。",
      details=dict(weekly_diff.get("counts", {}) or {}),
    )

    integrated_payload["signals"] = deepcopy(final_signals)
    _write_json(run_dir / "integrated_signals.json", integrated_payload)
    _write_json(run_dir / "weekly_diff.json", weekly_diff)

    digest_markdown = build_weekly_digest_markdown(
      [Signal.from_dict(item) for item in final_signals],
      WatchProfile.from_dict(watch_profile),
      data_source="取得済みデータ",
      loaded_count=len(final_signals),
      reviewed_signals=final_signals,
    )
    digest_markdown = _normalize_scheduler_digest_markdown(digest_markdown)
    if not digest_markdown.strip():
      _set_stage(stage_log, "build_digest", "failed", message="Digest 生成に失敗しました。")
      return _finalize_weekly_run(
        run_dir=run_dir,
        weekly_run_id=weekly_run_id,
        created_at=created_at,
        stage_log=stage_log,
        provider_log=provider_log,
        overall_status="failed",
        watch_profile_signature=watch_profile_signature,
        theme_name=str(watch_profile.get("theme_name", "") or ""),
        config=normalized_config,
        retrieval_manifest=retrieval_manifest,
        integrated_payload=integrated_payload,
        weekly_diff=weekly_diff,
        digest_markdown="",
        email_preview_payload={},
      )
    (run_dir / "weekly_digest.md").write_text(digest_markdown, encoding="utf-8")
    _set_stage(stage_log, "build_digest", "success", message="Digest を生成しました。")

    email_config = _build_effective_email_config(
      load_email_delivery_config(),
      dict(normalized_config.get("email", {}) or {}),
    )
    email_preview = build_digest_email_preview(
      digest_markdown,
      theme_name=str(watch_profile.get("theme_name", "") or ""),
      data_source="取得済みデータ",
      signals=final_signals,
      data_source_mode="retrieval_saved",
      watch_profile=watch_profile,
    )
    email_dry_run_result = run_email_delivery_dry_run(email_preview, email_config)
    email_preview_payload = {
      "schema_version": WEEKLY_SCHEDULER_SCHEMA_VERSION,
      "status": str(email_dry_run_result.get("status", "") or ""),
      "subject": str(email_preview.get("subject", "") or ""),
      "digest_sha256": str(email_preview.get("digest_sha256", "") or ""),
      "data_source": str(email_preview.get("data_source", "") or ""),
      "signal_count": int(email_preview.get("signal_count", 0) or 0),
      "validation_errors": list(email_dry_run_result.get("validation_errors", []) or []),
      "validation_warnings": list(email_dry_run_result.get("validation_warnings", []) or []),
      "recipient_masked": str(email_dry_run_result.get("recipient_masked", "") or ""),
      "send_attempted": False,
      "send_succeeded": False,
      "message": "Email Preview を生成しました。",
    }
    _write_json(run_dir / "email_preview.json", email_preview_payload)
    _set_stage(stage_log, "build_email_preview", "success", message="Email Preview を生成しました。")

    send_email_result = None
    if bool(normalized_config.get("execution", {}).get("dry_run", True)):
      _set_stage(stage_log, "send_email", "skipped", message="dry_run=true のためメール送信は実行しません。")
    elif bool(normalized_config.get("_no_email", False)):
      _set_stage(stage_log, "send_email", "skipped", message="--no-email 指定のためメール送信は実行しません。")
    elif not bool(normalized_config.get("email", {}).get("self_send_enabled", False)):
      _set_stage(stage_log, "send_email", "skipped", message="self_send_enabled=false のためメール送信は実行しません。")
    elif str(normalized_config.get("email", {}).get("mode", "") or "") != "self_only":
      _set_stage(stage_log, "send_email", "blocked", message="email.mode=self_only ではないため送信を停止しました。")
    elif _find_previous_sent_digest(weekly_runs_root, watch_profile_signature, str(email_preview.get("digest_sha256", "") or "")) is not None:
      previous_sent = _find_previous_sent_digest(weekly_runs_root, watch_profile_signature, str(email_preview.get("digest_sha256", "") or ""))
      email_preview_payload["message"] = "同一 Digest はすでに self-only 送信済みです。"
      email_preview_payload["duplicate_of_weekly_run_id"] = str((previous_sent or {}).get("weekly_run_id", "") or "")
      _write_json(run_dir / "email_preview.json", email_preview_payload)
      _set_stage(stage_log, "send_email", "blocked", message=email_preview_payload["message"])
    else:
      send_fn = provider_adapters.get("email_send") or send_digest_email_self_only
      send_email_result = send_fn(email_preview, email_config)
      email_preview_payload["send_attempted"] = bool(dict(send_email_result or {}).get("send_attempted", False))
      email_preview_payload["send_succeeded"] = bool(dict(send_email_result or {}).get("send_succeeded", False))
      email_preview_payload["delivery_status"] = str(dict(send_email_result or {}).get("status", "") or "")
      email_preview_payload["safe_error_message"] = str(dict(send_email_result or {}).get("safe_error_message", "") or "")
      email_preview_payload["recipient_masked"] = str(dict(send_email_result or {}).get("recipient_masked", email_preview_payload.get("recipient_masked", "")) or "")
      email_preview_payload["message"] = (
        "self-only メール送信が完了しました。"
        if email_preview_payload["send_succeeded"]
        else "self-only メール送信は完了しませんでした。"
      )
      _write_json(run_dir / "email_preview.json", email_preview_payload)
      if email_preview_payload["send_succeeded"]:
        save_email_delivery_log(send_email_result, base_root)
        _set_stage(stage_log, "send_email", "success", message=email_preview_payload["message"])
      else:
        _set_stage(stage_log, "send_email", "blocked", message=email_preview_payload["message"], errors=[email_preview_payload["safe_error_message"]] if email_preview_payload["safe_error_message"] else [])

    overall_status = _determine_overall_status(
      stage_log=stage_log,
      dry_run=bool(normalized_config.get("execution", {}).get("dry_run", True)),
      send_email_result=send_email_result,
    )
    return _finalize_weekly_run(
      run_dir=run_dir,
      weekly_run_id=weekly_run_id,
      created_at=created_at,
      stage_log=stage_log,
      provider_log=provider_log,
      overall_status=overall_status,
      watch_profile_signature=watch_profile_signature,
      theme_name=str(watch_profile.get("theme_name", "") or ""),
      config=normalized_config,
      retrieval_manifest=retrieval_manifest,
      integrated_payload=integrated_payload,
      weekly_diff=weekly_diff,
      digest_markdown=digest_markdown,
      email_preview_payload=email_preview_payload,
    )
  finally:
    if lock_info:
      release_weekly_run_lock(lock_info)


def build_cron_preview(
  config: dict,
  project_dir,
  python_executable,
) -> str:
  normalized = dict(validate_weekly_run_config(config).get("normalized_config", {}) or {})
  schedule = dict(normalized.get("schedule", {}) or {})
  weekday_map = {"SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6}
  minute = int(schedule.get("minute", 0) or 0)
  hour = int(schedule.get("hour", 8) or 8)
  weekday = weekday_map.get(str(schedule.get("day_of_week", "MON") or "MON").upper(), 1)
  timezone = str(schedule.get("timezone", "Asia/Tokyo") or "Asia/Tokyo")
  config_path = str(normalized.get("_config_path", "config/v9_weekly_run_config.json") or "config/v9_weekly_run_config.json")
  return (
    f"TZ={timezone}\n"
    f"{minute} {hour} * * {weekday} cd {Path(project_dir)} && "
    f"{Path(python_executable)} scripts/run_v9_weekly_watch.py --config {config_path}"
  )


def build_launchd_preview(
  config: dict,
  project_dir,
  python_executable,
) -> str:
  normalized = dict(validate_weekly_run_config(config).get("normalized_config", {}) or {})
  schedule = dict(normalized.get("schedule", {}) or {})
  config_path = str(normalized.get("_config_path", "config/v9_weekly_run_config.json") or "config/v9_weekly_run_config.json")
  label = "ai.techcartography.v9.weekly-watch"
  return "\n".join(
    [
      '<?xml version="1.0" encoding="UTF-8"?>',
      '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">',
      '<plist version="1.0">',
      "<dict>",
      f"  <key>Label</key><string>{label}</string>",
      "  <key>ProgramArguments</key>",
      "  <array>",
      f"    <string>{Path(python_executable)}</string>",
      f"    <string>{Path(project_dir) / 'scripts' / 'run_v9_weekly_watch.py'}</string>",
      "    <string>--config</string>",
      f"    <string>{config_path}</string>",
      "  </array>",
      "  <key>WorkingDirectory</key>",
      f"  <string>{Path(project_dir)}</string>",
      "  <key>EnvironmentVariables</key>",
      "  <dict>",
      f"    <key>TZ</key><string>{str(schedule.get('timezone', 'Asia/Tokyo') or 'Asia/Tokyo')}</string>",
      "  </dict>",
      "  <key>StartCalendarInterval</key>",
      "  <dict>",
      f"    <key>Weekday</key><integer>{_launchd_weekday(str(schedule.get('day_of_week', 'MON') or 'MON'))}</integer>",
      f"    <key>Hour</key><integer>{int(schedule.get('hour', 8) or 8)}</integer>",
      f"    <key>Minute</key><integer>{int(schedule.get('minute', 0) or 0)}</integer>",
      "  </dict>",
      "  <key>RunAtLoad</key><false/>",
      "</dict>",
      "</plist>",
    ]
  )


def _run_provider_stage(
  *,
  source_type: str,
  search_plan: dict[str, Any],
  watch_profile: dict[str, Any],
  config: dict[str, Any],
  output_root: Path,
  weekly_run_id: str,
  provider_adapters: dict[str, Any],
) -> dict[str, Any]:
  execution = dict(config.get("execution", {}) or {})
  stage_retry_limit = int(execution.get("stage_retry_limit", 0) or 0)
  dry_run = bool(execution.get("dry_run", True))
  enabled = bool(execution.get(f"{source_type}_enabled", False))
  if not enabled:
    return {
      "status": "skipped",
      "message": f"{source_type} provider は disabled です。",
      "rows": [],
      "warnings": [],
      "errors": [],
      "provider_log": {"provider": source_type, "mode": "disabled"},
      "details": {},
    }
  if dry_run:
    return {
      "status": "skipped",
      "message": f"dry_run=true のため {source_type} provider 実行はスキップしました。",
      "rows": [],
      "warnings": [],
      "errors": [],
      "provider_log": {"provider": source_type, "mode": "dry_run"},
      "details": {},
    }

  default_adapter_map = {
    "patent": _default_patent_stage_adapter,
    "paper": _default_paper_stage_adapter,
    "web_company": _default_web_company_stage_adapter,
  }
  adapter = provider_adapters.get(source_type) or default_adapter_map[source_type]
  timeout_key = f"{source_type}_seconds"
  if source_type == "web_company":
    timeout_key = "web_company_seconds"
  timeout_seconds = int(config.get("timeouts", {}).get(timeout_key, 1200) or 1200)
  return _call_with_retry(
    lambda: adapter(
      search_plan=search_plan,
      watch_profile=watch_profile,
      config=config,
      output_root=output_root,
      weekly_run_id=weekly_run_id,
    ),
    retries=stage_retry_limit,
    timeout_seconds=timeout_seconds,
  )


def _default_patent_stage_adapter(
  *,
  search_plan: dict[str, Any],
  watch_profile: dict[str, Any],
  config: dict[str, Any],
  output_root: Path,
  weekly_run_id: str,
) -> dict[str, Any]:
  approved_query_ids = list(config.get("patent", {}).get("approved_query_ids", []) or [])
  if not approved_query_ids:
    return _blocked_provider_stage("patent", "approved query が未設定のため特許取得を停止しました。")
  maximum_bytes_billed = int(config.get("patent", {}).get("maximum_bytes_billed", 0) or 0)
  if maximum_bytes_billed <= 0:
    return _blocked_provider_stage("patent", "maximum_bytes_billed が未設定のため特許取得を停止しました。")
  per_query_limit = _per_query_limit(int(config.get("limits", {}).get("patent_max_results", 500) or 500), len(approved_query_ids))
  env_cfg = BigQuerySafetyConfig.from_env()
  bigquery_config = BigQuerySafetyConfig(
    enable_bigquery_run=True,
    show_bigquery_admin=env_cfg.show_bigquery_admin,
    bigquery_project_id=env_cfg.bigquery_project_id,
    bigquery_location=env_cfg.bigquery_location,
    bigquery_max_bytes_billed=maximum_bytes_billed,
    bigquery_default_limit=per_query_limit,
    bigquery_dry_run_only=False,
    bigquery_allow_execute=True,
  )
  rows: list[dict[str, Any]] = []
  query_logs: list[dict[str, Any]] = []
  query_plans: list[dict[str, Any]] = []
  statuses: list[str] = []
  errors: list[str] = []
  for query_id in approved_query_ids:
    preview = build_patent_bigquery_preview(
      search_plan,
      watch_profile,
      selected_query_id=query_id,
      time_range=str(config.get("patent", {}).get("time_range", "12m") or "12m"),
      max_results=per_query_limit,
      config=bigquery_config,
    )
    dry_run_result = run_patent_bigquery_dry_run(preview, config=bigquery_config)
    retrieval_result = execute_patent_bigquery_retrieval(
      preview,
      dry_run_result,
      approved=True,
      config=bigquery_config,
    )
    query_plans.append(
      {
        "query_id": query_id,
        "preview_request": dict(preview.get("request", {}) or {}),
        "dry_run_result": dry_run_result,
      }
    )
    query_logs.append(
      {
        "query_id": query_id,
        "dry_run_status": str(dry_run_result.get("dry_run_status", "") or ""),
        "provider_status": str(retrieval_result.get("provider_status", "") or ""),
        "rows_retrieved": int(retrieval_result.get("rows_retrieved", 0) or 0),
        "error": retrieval_result.get("error"),
      }
    )
    statuses.append(str(retrieval_result.get("provider_status", "") or "error"))
    rows.extend(list(retrieval_result.get("rows", []) or []))
    if retrieval_result.get("error"):
      errors.append(str(retrieval_result.get("error")))
  stage_status = _combine_provider_stage_status(statuses, len(rows))
  artifact_dir = _save_scheduler_retrieval_artifact(
    "patent",
    output_root,
    retrieval_run_id=f"weekly_patent_{weekly_run_id}",
    provider_status="success" if stage_status == "success" else "partial_success" if stage_status == "partial_success" else "error",
    rows=rows,
    plan_payload={"queries": query_plans},
    provider_log={"query_logs": query_logs},
  )
  return {
    "status": stage_status,
    "message": "特許取得を実行しました。" if rows else "特許取得は候補 0 件でした。",
    "rows": rows,
    "warnings": [],
    "errors": errors if stage_status in {"partial_success", "failed"} else [],
    "provider_log": {"provider": "patent", "query_logs": query_logs},
    "source_run": {
      "run_id": f"weekly_patent_{weekly_run_id}",
      "artifact_dir": str(artifact_dir),
      "status": "success" if stage_status == "success" else "partial_success" if rows else "failed",
      "candidate_count": len(rows),
    } if rows else {},
    "details": {"approved_query_count": len(approved_query_ids), "rows_retrieved": len(rows)},
  }


def _default_paper_stage_adapter(
  *,
  search_plan: dict[str, Any],
  watch_profile: dict[str, Any],
  config: dict[str, Any],
  output_root: Path,
  weekly_run_id: str,
) -> dict[str, Any]:
  approved_query_ids = list(config.get("paper", {}).get("approved_query_ids", []) or [])
  if not approved_query_ids:
    return _blocked_provider_stage("paper", "approved query が未設定のため論文取得を停止しました。")
  per_query_limit = _per_query_limit(int(config.get("limits", {}).get("paper_max_results", 300) or 300), len(approved_query_ids))
  rows: list[dict[str, Any]] = []
  query_logs: list[dict[str, Any]] = []
  query_plans: list[dict[str, Any]] = []
  statuses: list[str] = []
  errors: list[str] = []
  for query_id in approved_query_ids:
    preview = build_openalex_paper_preview(
      search_plan,
      watch_profile,
      selected_query_id=query_id,
      time_range=str(config.get("paper", {}).get("time_range", "12m") or "12m"),
      max_results=per_query_limit,
      per_page=int(config.get("paper", {}).get("per_page", 25) or 25),
      retry_limit=int(config.get("paper", {}).get("retry_limit", 2) or 2),
      polite_email=str(config.get("paper", {}).get("polite_email", "") or "").strip() or None,
    )
    retrieval_result = execute_openalex_paper_retrieval(preview)
    query_plans.append({"query_id": query_id, "preview_request": dict(preview.get("request", {}) or {})})
    query_logs.append(
      {
        "query_id": query_id,
        "provider_status": str(retrieval_result.get("provider_status", "") or ""),
        "rows_retrieved": int(retrieval_result.get("rows_retrieved", 0) or 0),
        "pages_fetched": int(retrieval_result.get("pages_fetched", 0) or 0),
        "error": retrieval_result.get("error"),
      }
    )
    statuses.append(str(retrieval_result.get("provider_status", "") or "error"))
    rows.extend(list(retrieval_result.get("rows", []) or []))
    if retrieval_result.get("error"):
      errors.append(str(retrieval_result.get("error")))
  stage_status = _combine_provider_stage_status(statuses, len(rows))
  artifact_dir = _save_scheduler_retrieval_artifact(
    "paper",
    output_root,
    retrieval_run_id=f"weekly_paper_{weekly_run_id}",
    provider_status="success" if stage_status == "success" else "partial_success" if stage_status == "partial_success" else "error",
    rows=rows,
    plan_payload={"queries": query_plans},
    provider_log={"query_logs": query_logs},
  )
  return {
    "status": stage_status,
    "message": "論文取得を実行しました。" if rows else "論文取得は候補 0 件でした。",
    "rows": rows,
    "warnings": [],
    "errors": errors if stage_status in {"partial_success", "failed"} else [],
    "provider_log": {"provider": "paper", "query_logs": query_logs},
    "source_run": {
      "run_id": f"weekly_paper_{weekly_run_id}",
      "artifact_dir": str(artifact_dir),
      "status": "success" if stage_status == "success" else "partial_success" if rows else "failed",
      "candidate_count": len(rows),
    } if rows else {},
    "details": {"approved_query_count": len(approved_query_ids), "rows_retrieved": len(rows)},
  }


def _default_web_company_stage_adapter(
  *,
  search_plan: dict[str, Any],
  watch_profile: dict[str, Any],
  config: dict[str, Any],
  output_root: Path,
  weekly_run_id: str,
) -> dict[str, Any]:
  del watch_profile
  approved_query_ids = set(str(item or "").strip() for item in list(config.get("web_company", {}).get("approved_query_ids", []) or []) if str(item or "").strip())
  if not approved_query_ids:
    return _blocked_provider_stage("web_company", "approved query が未設定のため Web/企業取得を停止しました。")
  filtered_plan = deepcopy(search_plan)
  filtered_queries = [
    dict(query)
    for query in list(filtered_plan.get("global_web_plan", {}).get("queries", []) or [])
    if str(dict(query or {}).get("query_id", "") or "").strip() in approved_query_ids
  ]
  filtered_plan.setdefault("global_web_plan", {})["queries"] = filtered_queries
  if not filtered_queries:
    return _blocked_provider_stage("web_company", "approved query と一致する Global Web query がありません。")
  preview = build_global_web_retrieval_preview(
    filtered_plan,
    max_query_count=min(int(config.get("web_company", {}).get("max_query_count", len(filtered_queries)) or len(filtered_queries)), len(filtered_queries)),
    verification_limit=int(config.get("web_company", {}).get("verification_limit", 30) or 30),
    summary_top_n=int(config.get("web_company", {}).get("summary_top_n", 10) or 10),
  )
  retrieval_result = execute_global_web_retrieval(preview)
  stage_status = _combine_provider_stage_status([str(retrieval_result.get("provider_status", "") or "error")], len(list(retrieval_result.get("rows", []) or [])))
  artifact_dir = _save_scheduler_retrieval_artifact(
    "web_company",
    output_root,
    retrieval_run_id=f"weekly_web_company_{weekly_run_id}",
    provider_status="success" if stage_status == "success" else "partial_success" if stage_status == "partial_success" else "error",
    rows=list(retrieval_result.get("rows", []) or []),
    plan_payload={"request": dict(preview.get("request", {}) or {})},
    provider_log={"provider_log": list(retrieval_result.get("provider_log", []) or [])},
  )
  return {
    "status": stage_status,
    "message": "Web/企業情報取得を実行しました。" if retrieval_result.get("rows") else "Web/企業情報取得は候補 0 件でした。",
    "rows": list(retrieval_result.get("rows", []) or []),
    "warnings": [],
    "errors": [str(retrieval_result.get("error"))] if retrieval_result.get("error") and stage_status in {"partial_success", "failed"} else [],
    "provider_log": {
      "provider": "web_company",
      "query_count": int(retrieval_result.get("query_count", 0) or 0),
      "provider_log": list(retrieval_result.get("provider_log", []) or []),
    },
    "source_run": {
      "run_id": f"weekly_web_company_{weekly_run_id}",
      "artifact_dir": str(artifact_dir),
      "status": "success" if stage_status == "success" else "partial_success" if retrieval_result.get("rows") else "failed",
      "candidate_count": len(list(retrieval_result.get("rows", []) or [])),
    } if retrieval_result.get("rows") else {},
    "details": {"approved_query_count": len(approved_query_ids), "rows_retrieved": len(list(retrieval_result.get("rows", []) or []))},
  }


def _call_with_retry(callable_fn: Callable[[], dict[str, Any]], *, retries: int, timeout_seconds: int) -> dict[str, Any]:
  attempt = 0
  while True:
    attempt += 1
    try:
      return _call_with_timeout(callable_fn, timeout_seconds)
    except FuturesTimeoutError:
      if attempt > retries + 1:
        return {
          "status": "failed",
          "message": "stage timeout",
          "rows": [],
          "warnings": [],
          "errors": [f"timeout after {timeout_seconds} seconds"],
          "provider_log": {"attempts": attempt},
          "details": {"timeout_seconds": timeout_seconds},
        }
    except Exception as exc:  # noqa: BLE001
      if attempt > retries + 1:
        return {
          "status": "failed",
          "message": f"stage execution failed: {type(exc).__name__}",
          "rows": [],
          "warnings": [],
          "errors": [str(exc)],
          "provider_log": {"attempts": attempt},
          "details": {},
        }


def _call_with_timeout(callable_fn: Callable[[], dict[str, Any]], timeout_seconds: int) -> dict[str, Any]:
  with ThreadPoolExecutor(max_workers=1) as executor:
    future = executor.submit(callable_fn)
    return future.result(timeout=max(timeout_seconds, 1))


def _blocked_provider_stage(source_type: str, message: str) -> dict[str, Any]:
  return {
    "status": "blocked",
    "message": message,
    "rows": [],
    "warnings": [],
    "errors": [],
    "provider_log": {"provider": source_type, "mode": "blocked"},
    "details": {},
  }


def _combine_provider_stage_status(provider_statuses: list[str], row_count: int) -> str:
  normalized = [str(status or "").strip().lower() for status in provider_statuses if str(status or "").strip()]
  if row_count <= 0:
    if normalized and all(status in {"validation_error", "not_approved", "dry_run_required", "blocked_by_max_bytes", "execute_rejected"} for status in normalized):
      return "blocked"
    return "failed"
  if normalized and all(status == "success" for status in normalized):
    return "success"
  return "partial_success"


def _per_query_limit(total_limit: int, query_count: int) -> int:
  if query_count <= 0:
    return max(total_limit, 1)
  return max(total_limit // query_count, 1)


def _save_scheduler_retrieval_artifact(
  source_type: str,
  base_root: Path,
  *,
  retrieval_run_id: str,
  provider_status: str,
  rows: list[dict[str, Any]],
  plan_payload: dict[str, Any],
  provider_log: dict[str, Any],
) -> Path:
  dirs = ensure_v9_run_dirs(base_root)
  runs_dir = dirs["root"] / _SOURCE_RUN_SUBDIRS[source_type]
  runs_dir.mkdir(parents=True, exist_ok=True)
  target_dir = runs_dir / retrieval_run_id
  target_dir.mkdir(parents=True, exist_ok=True)
  _write_json(
    target_dir / _SOURCE_STAGED_FILENAMES[source_type],
    {
      "retrieval_run_id": retrieval_run_id,
      "provider_status": provider_status,
      "rows": rows,
    },
  )
  _write_json(target_dir / _SOURCE_PLAN_FILENAMES[source_type], plan_payload)
  _write_json(target_dir / _SOURCE_PROVIDER_LOG_FILENAMES[source_type], provider_log)
  return target_dir


def _load_watch_profile_path(path_text: str) -> dict[str, Any]:
  path = Path(str(path_text or "").strip())
  if not str(path):
    raise RuntimeError("watch_profile_path が未設定です。")
  resolved = path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()
  payload = json.loads(resolved.read_text(encoding="utf-8"))
  if not isinstance(payload, dict):
    raise RuntimeError("Watch Profile の形式が不正です。")
  return migrate_watch_profile(payload)


def _load_integrated_signals_from_run(previous_run: dict[str, Any]) -> list[dict[str, Any]]:
  path = Path(previous_run["integrated_signals_path"])
  if not path.exists():
    return []
  payload = json.loads(path.read_text(encoding="utf-8"))
  if isinstance(payload, dict):
    return list(payload.get("signals", []) or [])
  return []


def _build_effective_email_config(base_config: EmailDeliveryConfig, email_settings: dict[str, Any]) -> EmailDeliveryConfig:
  mode = str(email_settings.get("mode", base_config.send_mode) or base_config.send_mode).strip().lower()
  if mode not in {"preview", "self_only"}:
    mode = base_config.send_mode
  return replace(base_config, send_mode=mode)


def _find_previous_sent_digest(weekly_root: Path, watch_profile_signature: str, digest_sha256: str) -> dict[str, Any] | None:
  if not digest_sha256:
    return None
  for status_path in _resolve_weekly_runs_root(weekly_root).glob("*/weekly_run_status.json"):
    try:
      payload = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
      continue
    if str(payload.get("watch_profile_signature", "") or "") != str(watch_profile_signature or ""):
      continue
    email_payload = dict(payload.get("email_preview", {}) or {})
    if not bool(email_payload.get("send_succeeded", False)):
      continue
    if str(email_payload.get("digest_sha256", "") or "") != digest_sha256:
      continue
    return {
      "weekly_run_id": str(payload.get("weekly_run_id", status_path.parent.name) or status_path.parent.name),
      "status_path": str(status_path),
    }
  return None


def _determine_overall_status(
  *,
  stage_log: list[dict[str, Any]],
  dry_run: bool,
  send_email_result: dict[str, Any] | None,
) -> str:
  status_map = {item["stage"]: item["status"] for item in stage_log}
  if status_map.get("load_config") == "blocked":
    return "blocked"
  if status_map.get("load_watch_profile") == "failed":
    return "failed"
  if status_map.get("integrate_signals") == "failed" or status_map.get("build_digest") == "failed":
    return "failed"
  if dry_run:
    if status_map.get("build_digest") == "success":
      return "partial_success"
    return "blocked"
  provider_statuses = [status_map.get(stage, "pending") for stage in ("retrieve_patent", "retrieve_paper", "retrieve_web_company")]
  if any(status == "failed" for status in provider_statuses):
    return "partial_success"
  if any(status in {"blocked", "partial_success"} for status in provider_statuses):
    return "partial_success"
  if send_email_result is not None and not bool(send_email_result.get("send_succeeded", False)) and bool(send_email_result.get("send_attempted", False)):
    return "partial_success"
  return "success"


def _finalize_weekly_run(
  *,
  run_dir: Path,
  weekly_run_id: str,
  created_at: str,
  stage_log: list[dict[str, Any]],
  provider_log: dict[str, Any],
  overall_status: str,
  watch_profile_signature: str,
  theme_name: str,
  config: dict[str, Any],
  retrieval_manifest: dict[str, Any] | None,
  integrated_payload: dict[str, Any] | None,
  weekly_diff: dict[str, Any] | None,
  digest_markdown: str,
  email_preview_payload: dict[str, Any],
) -> dict[str, Any]:
  _set_stage(stage_log, "finalize", overall_status, message="weekly scheduler run を完了しました。")
  _write_json(run_dir / "stage_log.json", stage_log)
  _write_json(run_dir / "provider_log.json", provider_log)
  _write_json(
    run_dir / "retrieval_run_manifest.json",
    retrieval_manifest if retrieval_manifest is not None else {
      "schema_version": WEEKLY_SCHEDULER_SCHEMA_VERSION,
      "status": "unavailable",
      "message": "retrieval manifest は生成されませんでした。",
    },
  )
  _write_json(
    run_dir / "integrated_signals.json",
    integrated_payload if integrated_payload is not None else {
      "schema_version": WEEKLY_SCHEDULER_SCHEMA_VERSION,
      "signals": [],
      "ranked_count": 0,
    },
  )
  _write_json(
    run_dir / "weekly_diff.json",
    weekly_diff if weekly_diff is not None else {
      "schema_version": WEEKLY_SCHEDULER_SCHEMA_VERSION,
      "counts": {"New": 0, "Rising": 0, "Dropped": 0, "Stable": 0},
      "summary": "weekly diff は生成されませんでした。",
    },
  )
  (run_dir / "weekly_digest.md").write_text(
    digest_markdown if digest_markdown else "# Tech Cartography v9 Weekly Run Preview\n\nDigest は未生成です。\n",
    encoding="utf-8",
  )
  _write_json(
    run_dir / "email_preview.json",
    email_preview_payload if email_preview_payload else {
      "schema_version": WEEKLY_SCHEDULER_SCHEMA_VERSION,
      "status": "blocked",
      "message": "Email Preview は生成されませんでした。",
      "send_attempted": False,
      "send_succeeded": False,
    },
  )
  status_payload = {
    "schema_version": WEEKLY_SCHEDULER_SCHEMA_VERSION,
    "weekly_run_id": weekly_run_id,
    "created_at": created_at,
    "completed_at": _now_iso(),
    "overall_status": overall_status,
    "watch_profile_signature": watch_profile_signature,
    "theme_name": theme_name,
    "dry_run": bool(dict(config or {}).get("execution", {}).get("dry_run", True)),
    "config_snapshot_path": str(run_dir / "weekly_run_config_snapshot.json"),
    "retrieval_manifest_path": str(run_dir / "retrieval_run_manifest.json"),
    "integrated_signals_path": str(run_dir / "integrated_signals.json"),
    "weekly_diff_path": str(run_dir / "weekly_diff.json"),
    "weekly_digest_path": str(run_dir / "weekly_digest.md"),
    "email_preview_path": str(run_dir / "email_preview.json"),
    "stage_statuses": {item["stage"]: item["status"] for item in stage_log},
    "email_preview": email_preview_payload,
  }
  _write_json(run_dir / "weekly_run_status.json", status_payload)
  return {
    "weekly_run_id": weekly_run_id,
    "status": overall_status,
    "run_dir": str(run_dir),
    "watch_profile_signature": watch_profile_signature,
    "theme_name": theme_name,
    "stage_statuses": status_payload["stage_statuses"],
    "email_preview": email_preview_payload,
  }


def _resolve_weekly_runs_root(base_root: Path | str) -> Path:
  base = Path(base_root)
  if base.name == "weekly_runs":
    base.mkdir(parents=True, exist_ok=True)
    return base
  path = base / "weekly_runs"
  path.mkdir(parents=True, exist_ok=True)
  return path


def _resolve_weekly_locks_root(base_root: Path | str) -> Path:
  base = Path(base_root)
  if base.name == "weekly_locks":
    base.mkdir(parents=True, exist_ok=True)
    return base
  path = base / "weekly_locks"
  path.mkdir(parents=True, exist_ok=True)
  return path


def _initial_stage_log() -> list[dict[str, Any]]:
  return [
    {
      "stage": stage,
      "status": "pending",
      "message": "",
      "started_at": None,
      "ended_at": None,
      "warnings": [],
      "errors": [],
      "details": {},
    }
    for stage in WEEKLY_STAGE_SEQUENCE
  ]


def _set_stage(
  stage_log: list[dict[str, Any]],
  stage_name: str,
  status: str,
  *,
  message: str = "",
  warnings: list[str] | None = None,
  errors: list[str] | None = None,
  details: dict[str, Any] | None = None,
) -> None:
  now = _now_iso()
  for entry in stage_log:
    if entry["stage"] != stage_name:
      continue
    entry["status"] = status
    entry["message"] = message
    entry["started_at"] = entry["started_at"] or now
    entry["ended_at"] = now
    entry["warnings"] = list(warnings or [])
    entry["errors"] = list(errors or [])
    entry["details"] = dict(details or {})
    break


def _normalize_scheduler_digest_markdown(markdown_text: str) -> str:
  original = "このPhaseではデモ / staged データのみを扱い、外部API、PDF/OCR深掘り、メール送信、scheduler起動は行いません。"
  replacement = "このDigestは weekly scheduler 実行結果に基づく lightweight signal watch レポートです。外部API実行やメール送信の有無は weekly run 設定と stage log を参照してください。"
  return str(markdown_text or "").replace(original, replacement)


def _read_lock_payload(lock_path: Path) -> dict[str, Any]:
  try:
    return json.loads(lock_path.read_text(encoding="utf-8"))
  except Exception:  # noqa: BLE001
    return {}


def _is_stale_lock(existing: dict[str, Any], *, stale_timeout_seconds: int, now: datetime) -> bool:
  started_at = str(existing.get("started_at", "") or "").strip()
  if not started_at:
    return True
  try:
    started = datetime.fromisoformat(started_at)
  except ValueError:
    return True
  return now - started > timedelta(seconds=max(stale_timeout_seconds, 60))


def _write_json(path: Path, payload: Any) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _build_weekly_run_id(explicit_run_id: str = "") -> str:
  cleaned = "".join(char for char in str(explicit_run_id or "").strip() if char.isalnum() or char in {"-", "_"})
  if cleaned:
    return cleaned
  return "weekly_watch_" + datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")


def _now_iso() -> str:
  return datetime.now().astimezone().isoformat(timespec="seconds")


def _launchd_weekday(day_of_week: str) -> int:
  mapping = {"SUN": 1, "MON": 2, "TUE": 3, "WED": 4, "THU": 5, "FRI": 6, "SAT": 7}
  return mapping.get(str(day_of_week or "MON").upper(), 2)


__all__ = [
  "SUCCESSFUL_WEEKLY_STATUSES",
  "TERMINAL_WEEKLY_STATUSES",
  "WEEKLY_SCHEDULER_SCHEMA_VERSION",
  "WEEKLY_STAGE_SEQUENCE",
  "acquire_weekly_run_lock",
  "build_cron_preview",
  "build_launchd_preview",
  "find_previous_successful_weekly_run",
  "load_weekly_run_config",
  "release_weekly_run_lock",
  "run_weekly_watch",
  "validate_weekly_run_config",
]
