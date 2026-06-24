"""Live digest mail preview from latest Web Signal pack (Phase 25F)."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tech_cartography.runtime.live_artifact_paths import (
  check_directory_writable,
  get_live_digest_preview_dir,
)
from tech_cartography.runtime.user_context import evaluate_live_admin_access, normalize_user_context
from tech_cartography.services.live_run_history import (
  attach_user_run_metadata,
  copy_user_run_metadata,
  generate_run_id,
  map_result_status,
  record_live_run,
)
from tech_cartography.services.live_web_signal_pack import (
  SOURCE_TYPE_LIVE,
  find_latest_live_web_signal_pack_path,
  load_latest_live_web_signal_pack,
  load_live_web_signal_pack,
)
from tech_cartography.services.live_watch_profile_manager import get_active_watch_profile
from tech_cartography.services.live_web_signal_collector import (
  find_latest_web_signal_collection_path,
  load_web_signal_collection,
)
from tech_cartography.services.live_web_signal_review import (
  DIGEST_WITH_SIGNALS_ACTION,
  build_web_signal_review,
  integrate_review_into_preview,
  record_web_signal_review_run,
  save_web_signal_review,
)


def attach_strategic_watch_artifact_references(
  preview: dict[str, Any],
  output_root: Path | str,
) -> dict[str, Any]:
  """Attach latest Evidence Gap / Strategic Watch Brief paths — read only, no rebuild."""
  from tech_cartography.services.live_evidence_gap_builder import (
    find_latest_evidence_gap_path,
    load_evidence_gap_artifact,
  )
  from tech_cartography.services.live_strategic_watch_brief import (
    find_latest_strategic_watch_brief_path,
    load_strategic_watch_brief,
  )

  merged = dict(preview)
  gap_path = find_latest_evidence_gap_path(output_root)
  brief_path = find_latest_strategic_watch_brief_path(output_root)
  gap_artifact = load_evidence_gap_artifact(gap_path) if gap_path else None
  brief_artifact = load_strategic_watch_brief(brief_path) if brief_path else None

  merged["latest_evidence_gap_artifact_path"] = str(gap_path) if gap_path else None
  merged["latest_strategic_watch_brief_path"] = str(brief_path) if brief_path else None
  merged["latest_evidence_gap_count"] = len((gap_artifact or {}).get("evidence_gaps") or [])
  merged["latest_next_verification_action_count"] = len(
    (gap_artifact or {}).get("next_verification_actions")
    or (brief_artifact or {}).get("next_verification_actions")
    or [],
  )

  ref_lines = ["## Strategic Watch References", ""]
  if gap_path:
    ref_lines.extend(
      [
        "### Evidence Gap（参照のみ）",
        f"- artifact: {gap_path}",
        f"- gap_count: {merged['latest_evidence_gap_count']}",
        "",
      ],
    )
  if brief_path:
    ref_lines.extend(
      [
        "### Strategic Watch Brief（参照のみ）",
        f"- artifact: {brief_path}",
        "",
      ],
    )
  if gap_path or brief_path:
    ref_lines.append("> Evidence Gap / Brief は別 artifact です。Digest 作成時に自動再生成しません。")
    section = "\n".join(ref_lines).strip() + "\n"
    merged["strategic_watch_reference_markdown"] = section
    merged["markdown_body"] = str(merged.get("markdown_body") or "").rstrip() + "\n\n" + section
    merged["plain_text_body"] = str(merged.get("plain_text_body") or "").rstrip() + "\n\n" + section.replace("##", "===").replace("###", "---")
  return merged

def resolve_latest_web_signal_pack(
  output_root: Path | str,
) -> tuple[dict[str, Any] | None, Path | None, str | None]:
  """Return newest pack from live or next-cycle directories."""
  from tech_cartography.services.live_next_cycle_tavily_runner import (
    SOURCE_TYPE as NEXT_CYCLE_SOURCE_TYPE,
    find_latest_next_cycle_web_signal_pack_path,
    load_next_cycle_web_signal_pack,
  )

  options: list[tuple[Path, dict[str, Any], str]] = []
  live_path = find_latest_live_web_signal_pack_path(output_root)
  if live_path is not None:
    live_pack = load_live_web_signal_pack(live_path)
    if live_pack:
      source_type = str(live_pack.get("source_type") or SOURCE_TYPE_LIVE)
      options.append((live_path, live_pack, source_type))

  next_path = find_latest_next_cycle_web_signal_pack_path(output_root)
  if next_path is not None:
    next_pack = load_next_cycle_web_signal_pack(next_path)
    if next_pack:
      source_type = str(next_pack.get("source_type") or NEXT_CYCLE_SOURCE_TYPE)
      options.append((next_path, next_pack, source_type))

  if not options:
    return None, None, None

  pack_path, pack, source_type = max(options, key=lambda row: row[0].stat().st_mtime)
  merged = dict(pack)
  merged["source_type"] = source_type
  return merged, pack_path, source_type


def load_latest_web_signal_pack_for_digest(output_root: Path | str) -> tuple[dict[str, Any] | None, Path | None]:
  pack, path, _source_type = resolve_latest_web_signal_pack(output_root)
  return pack, path


MAX_KEY_SIGNALS = 3
PREVIEW_ONLY_LABEL = "preview_only_no_send"

SAFETY_NOTICE = (
  "These Web Signals are review candidates only. "
  "They do not prove direct relationship, market truth, legal status, infringement, or validity. "
  "Primary-source verification is required before any decision."
)

SAFETY_NOTICE_JA = (
  "Web Signal は確認候補です。直接関係・市場事実の証明ではありません。"
  "FTO、侵害、有効性判断ではありません。最終判断には原典確認が必要です。"
)

FORBIDDEN_BODY_PHRASES: tuple[str, ...] = (
  "infringement confirmed",
  "fto cleared",
  "valid patent",
  "market fact",
  "proves infringement",
  "侵害確定",
  "有効性確定",
  "FTOクリア",
)

DEFAULT_EVIDENCE_GAPS: tuple[str, ...] = (
  "Patent / claim linkage is not included in this live preview.",
  "Primary sources have not been verified for each candidate.",
  "Snapshot is limited to the latest Tavily Web Signal pack.",
  "Human review_status=needs_human_review for every candidate.",
)

DEFAULT_NEXT_ACTIONS: tuple[str, ...] = (
  "Open each URL and verify against primary sources.",
  "Discuss candidates with the R&D team before sharing externally.",
  "Link promising signals to patent / claim context in a later phase.",
)

_SENSITIVE_KEY_PATTERN = re.compile(r"(api[_-]?key|authorization|token|secret|smtp|sendgrid|gmail)", re.IGNORECASE)


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _timestamp_slug(iso_ts: str) -> str:
  return iso_ts.replace(":", "").replace("-", "")


def email_send_is_disabled() -> bool:
  from tech_cartography.runtime.cloud_run_config import is_email_send_disabled

  return is_email_send_disabled()


def can_create_live_digest_preview() -> tuple[bool, str]:
  """Preview creation is always allowed; actual email send remains separate."""
  if email_send_is_disabled():
    return True, "Digest preview only — email send disabled (DISABLE_EMAIL_SEND=true)."
  return True, "Digest preview only — no email send in this phase."


DIGEST_PREVIEW_ACCESS_MESSAGES: dict[str, str] = {
  "login_required": "ログイン後に実行できます。",
  "admin_required": "admin権限が必要です。",
}


def evaluate_digest_preview_access(
  *,
  login_required: bool,
  is_authenticated: bool,
  auth_role: str,
  user_context: dict[str, Any] | None = None,
) -> tuple[bool, str | None, str, dict[str, Any]]:
  """Return (allowed, error_code, message, resolved_user_context). IAP-safe."""
  access_ok, access_error, resolved_ctx = evaluate_live_admin_access(
    login_required=login_required,
    is_authenticated=is_authenticated,
    auth_role=auth_role,
    user_context=user_context,
  )
  if access_ok:
    return True, None, "実行可能", resolved_ctx
  error = access_error or "blocked"
  return False, error, DIGEST_PREVIEW_ACCESS_MESSAGES.get(error, "実行できません。"), resolved_ctx


def digest_preview_safety_metadata(*, uses_web_signals: bool, signal_count: int = 0) -> dict[str, Any]:
  metadata: dict[str, Any] = {
    "uses_web_signals": uses_web_signals,
    "candidate_information_only": True,
    "legal_judgement": False,
    "fto_judgement": False,
    "infringement_judgement": False,
    "validity_judgement": False,
    "no_external_api_call": True,
    "no_email_send": True,
    "no_scheduler_start": True,
  }
  if uses_web_signals:
    metadata["signal_count"] = signal_count
  return metadata


def assert_preview_only_operation() -> None:
  """Document guard: preview path must never invoke SMTP/API send."""
  return None


def _score_value(item: dict[str, Any]) -> float:
  try:
    return float(item.get("score"))
  except (TypeError, ValueError):
    return -1.0


def _why_review_candidate(item: dict[str, Any]) -> str:
  signal_type = str(item.get("signal_type") or "unknown")
  confidence = str(item.get("confidence_label") or "low")
  mapping = {
    "company_signal": "企業・IR 動向の確認候補として共有価値があります（確定事実ではありません）。",
    "public_project_signal": "公的プロジェクト / 資金調達シグナルの確認候補です（原典確認が必要）。",
    "market_signal": "市場・需要トレンドの確認候補です（市場真実の証明ではありません）。",
    "research_signal": "研究・技術動向の確認候補です（特許・論文との関係は未検証）。",
    "unknown": "分類未確定の確認候補です。タイトルと URL を人間が確認してください。",
  }
  base = mapping.get(signal_type, mapping["unknown"])
  return f"{base} confidence={confidence} / review_status=needs_human_review"


def select_key_signals(candidates: list[dict[str, Any]], *, limit: int = MAX_KEY_SIGNALS) -> list[dict[str, Any]]:
  ranked = sorted(candidates, key=_score_value, reverse=True)
  key_signals: list[dict[str, Any]] = []
  for item in ranked[:limit]:
    key_signals.append(
      {
        "signal_id": item.get("signal_id"),
        "title": item.get("title"),
        "url": item.get("url"),
        "snippet": item.get("snippet"),
        "signal_type": item.get("signal_type"),
        "confidence_label": item.get("confidence_label"),
        "review_status": item.get("review_status"),
        "why_review": _why_review_candidate(item),
      },
    )
  return key_signals


def build_evidence_gaps(*, pack: dict[str, Any], key_signals: list[dict[str, Any]]) -> list[str]:
  gaps = list(DEFAULT_EVIDENCE_GAPS)
  if not key_signals:
    gaps.insert(0, "No Web Signal candidates were available in the source pack.")
  query = str(pack.get("query") or "").strip()
  if query:
    gaps.append(f"Search query snapshot: {query} (not re-run in digest preview phase).")
  return gaps


def build_digest_subject(
  *,
  theme_name: str,
  recipient_group_name: str | None = None,
) -> str:
  group = str(recipient_group_name or "").strip()
  if group:
    return f"[Tech Cartography] Weekly Web Signal Digest — {theme_name} ({group})"
  return f"[Tech Cartography] Weekly Web Signal Digest — {theme_name}"


def build_plain_text_body(
  *,
  theme_name: str,
  recipient_group_name: str | None,
  user_note: str | None,
  key_signals: list[dict[str, Any]],
  evidence_gaps: list[str],
  next_actions: list[str],
) -> str:
  lines = [
    f"Subject theme: {theme_name}",
  ]
  if recipient_group_name:
    lines.append(f"Recipient group: {recipient_group_name}")
  lines.extend(
    [
      "",
      "=== 今週の確認対象テーマ ===",
      theme_name,
      "",
      "=== 注目 Web Signal 候補（最大3件） ===",
    ],
  )
  if not key_signals:
    lines.append("(候補なし — source pack を確認してください)")
  for index, signal in enumerate(key_signals, start=1):
    lines.extend(
      [
        f"{index}. {signal.get('title') or '(no title)'}",
        f"   URL: {signal.get('url')}",
        f"   type: {signal.get('signal_type')} | confidence: {signal.get('confidence_label')}",
        f"   なぜ確認すべきか: {signal.get('why_review')}",
        "",
      ],
    )
  lines.extend(["=== 注意点 / Evidence Gaps ==="])
  for gap in evidence_gaps:
    lines.append(f"- {gap}")
  lines.extend(["", "=== 次アクション ==="])
  for action in next_actions:
    lines.append(f"- {action}")
  if user_note:
    lines.extend(["", "=== メモ ===", user_note.strip()])
  lines.extend(
    [
      "",
      "=== 免責 ===",
      SAFETY_NOTICE_JA,
      SAFETY_NOTICE,
      "",
      "[PREVIEW ONLY — NOT SENT]",
    ],
  )
  return "\n".join(lines).strip() + "\n"


def build_markdown_body(
  *,
  theme_name: str,
  recipient_group_name: str | None,
  user_note: str | None,
  key_signals: list[dict[str, Any]],
  evidence_gaps: list[str],
  next_actions: list[str],
) -> str:
  lines = [
    "# Live Digest Mail Preview",
    "",
    "> **PREVIEW ONLY — NOT SENT**",
    "",
    f"## 今週の確認対象テーマ",
    "",
    theme_name,
    "",
    "## 注目 Web Signal 候補（最大3件）",
    "",
  ]
  if not key_signals:
    lines.append("_候補なし — source pack を確認してください_")
  for index, signal in enumerate(key_signals, start=1):
    lines.extend(
      [
        f"### {index}. {signal.get('title') or '(no title)'}",
        "",
        f"- URL: {signal.get('url')}",
        f"- signal_type: {signal.get('signal_type')}",
        f"- confidence_label: {signal.get('confidence_label')}",
        f"- review_status: {signal.get('review_status')}",
        f"- なぜ確認すべきか: {signal.get('why_review')}",
        "",
        str(signal.get("snippet") or ""),
        "",
      ],
    )
  lines.extend(["## 注意点 / Evidence Gaps", ""])
  for gap in evidence_gaps:
    lines.append(f"- {gap}")
  lines.extend(["", "## 次アクション", ""])
  for action in next_actions:
    lines.append(f"- {action}")
  if user_note:
    lines.extend(["", "## メモ", "", user_note.strip()])
  lines.extend(["", "## 免責", "", SAFETY_NOTICE_JA, "", SAFETY_NOTICE, ""])
  if recipient_group_name:
    lines.extend(["", f"_Recipient group: {recipient_group_name}_"])
  return "\n".join(lines).strip() + "\n"


def validate_preview_language(text: str) -> list[str]:
  lowered = text.lower()
  violations: list[str] = []
  for phrase in FORBIDDEN_BODY_PHRASES:
    if phrase.lower() in lowered:
      violations.append(phrase)
  return violations


def generate_live_digest_preview(
  pack: dict[str, Any],
  *,
  source_pack_path: str | None = None,
  theme_name: str | None = None,
  recipient_group_name: str | None = None,
  user_note: str | None = None,
) -> dict[str, Any]:
  assert_preview_only_operation()
  resolved_theme = str(theme_name or pack.get("theme_name") or "Unknown theme").strip()
  candidates = list(pack.get("candidates") or [])
  key_signals = select_key_signals(candidates)
  evidence_gaps = build_evidence_gaps(pack=pack, key_signals=key_signals)
  next_actions = list(pack.get("next_actions") or DEFAULT_NEXT_ACTIONS)
  created_at = _utc_now_iso()
  digest_title = f"Weekly Web Signal Digest — {resolved_theme}"
  subject = build_digest_subject(theme_name=resolved_theme, recipient_group_name=recipient_group_name)
  plain_text_body = build_plain_text_body(
    theme_name=resolved_theme,
    recipient_group_name=recipient_group_name,
    user_note=user_note,
    key_signals=key_signals,
    evidence_gaps=evidence_gaps,
    next_actions=next_actions,
  )
  markdown_body = build_markdown_body(
    theme_name=resolved_theme,
    recipient_group_name=recipient_group_name,
    user_note=user_note,
    key_signals=key_signals,
    evidence_gaps=evidence_gaps,
    next_actions=next_actions,
  )
  violations = validate_preview_language(plain_text_body + markdown_body)
  if violations:
    raise ValueError(f"Preview body contains forbidden phrasing: {violations[0]}")

  return {
    "preview_id": f"live-digest-{uuid.uuid4().hex[:10]}",
    "digest_title": digest_title,
    "subject": subject,
    "plain_text_body": plain_text_body,
    "markdown_body": markdown_body,
    "key_signals": key_signals,
    "evidence_gaps": evidence_gaps,
    "next_actions": next_actions,
    "safety_notice": SAFETY_NOTICE,
    "created_at": created_at,
    "theme_name": resolved_theme,
    "recipient_group_name": recipient_group_name,
    "user_note": user_note,
    "source_pack_path": source_pack_path,
    "source_type": str(pack.get("source_type") or SOURCE_TYPE_LIVE),
    "preview_mode": PREVIEW_ONLY_LABEL,
  }


def _assert_no_sensitive_material(serialized: str) -> None:
  lowered = serialized.lower()
  if "tavily_api_key" in lowered or '"api_key"' in lowered:
    raise ValueError("Refusing to save payload containing API key material")
  if _SENSITIVE_KEY_PATTERN.search(serialized):
    if any(token in lowered for token in ("api_key", "smtp_password", "authorization:")):
      raise ValueError("Refusing to save payload containing sensitive material")


def build_save_payload(preview: dict[str, Any], *, output_root: Path | str | None = None) -> dict[str, Any]:
  active_profile_path: str | None = None
  active_profile_id: str | None = None
  collection_path: str | None = None
  collection_run_id: str | None = None
  if output_root is not None:
    active, active_path = get_active_watch_profile(output_root)
    if active and active_path:
      active_profile_path = active_path
      active_profile_id = str(active.get("profile_id") or "") or None
    coll_path = find_latest_web_signal_collection_path(output_root)
    if coll_path is not None:
      collection = load_web_signal_collection(coll_path) or {}
      collection_path = str(coll_path)
      collection_run_id = str(collection.get("run_id") or "") or None
  payload = {
    "source_pack_path": preview.get("source_pack_path"),
    "source_type": preview.get("source_type"),
    "theme_name": preview.get("theme_name"),
    "subject": preview.get("subject"),
    "body": preview.get("plain_text_body"),
    "markdown_body": preview.get("markdown_body"),
    "key_signals": preview.get("key_signals") or [],
    "next_actions": preview.get("next_actions") or [],
    "safety_notice": preview.get("safety_notice") or SAFETY_NOTICE,
    "created_at": preview.get("created_at"),
    "preview_mode": PREVIEW_ONLY_LABEL,
    "digest_title": preview.get("digest_title"),
    "evidence_gaps": preview.get("evidence_gaps") or [],
    "active_watch_profile_path": active_profile_path or preview.get("active_watch_profile_path"),
    "active_watch_profile_id": active_profile_id or preview.get("active_watch_profile_id"),
    "latest_web_signal_collection_path": collection_path or preview.get("latest_web_signal_collection_path"),
    "latest_web_signal_collection_run_id": collection_run_id or preview.get("latest_web_signal_collection_run_id"),
    "uses_web_signals": preview.get("uses_web_signals"),
    "source_web_signal_artifact": preview.get("source_web_signal_artifact"),
    "web_signal_result_count": (preview.get("web_signal_review") or {}).get("total_signal_count"),
    "web_signal_review_id": (preview.get("web_signal_review") or {}).get("review_id"),
    "latest_evidence_gap_artifact_path": preview.get("latest_evidence_gap_artifact_path"),
    "latest_strategic_watch_brief_path": preview.get("latest_strategic_watch_brief_path"),
    "latest_evidence_gap_count": preview.get("latest_evidence_gap_count"),
    "latest_next_verification_action_count": preview.get("latest_next_verification_action_count"),
  }
  return copy_user_run_metadata(payload, preview)


def save_live_digest_preview(
  preview: dict[str, Any],
  output_root: Path | str,
) -> dict[str, str]:
  out_dir = get_live_digest_preview_dir(output_root)
  writable, message = check_directory_writable(out_dir)
  if not writable:
    raise ValueError(message or f"Cannot write live digest preview to {out_dir}")

  created_at = str(preview.get("created_at") or _utc_now_iso())
  slug = _timestamp_slug(created_at)
  json_path = out_dir / f"live_digest_preview_{slug}.json"
  md_path = out_dir / f"live_digest_preview_{slug}.md"
  txt_path = out_dir / f"live_digest_preview_{slug}.txt"

  payload = build_save_payload(preview, output_root=output_root)
  serialized = json.dumps(payload, indent=2, ensure_ascii=False)
  _assert_no_sensitive_material(serialized)

  json_path.write_text(serialized + "\n", encoding="utf-8")
  md_path.write_text(str(preview.get("markdown_body") or ""), encoding="utf-8")
  txt_path.write_text(str(preview.get("plain_text_body") or ""), encoding="utf-8")
  return {"json": str(json_path), "markdown": str(md_path), "text": str(txt_path)}


def live_digest_preview_dir(output_root: Path | str) -> Path:
  return get_live_digest_preview_dir(output_root)


def find_latest_live_digest_preview_path(output_root: Path | str) -> Path | None:
  out_dir = live_digest_preview_dir(output_root)
  if not out_dir.exists():
    return None
  files = sorted(out_dir.glob("live_digest_preview_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
  return files[0] if files else None


def load_live_digest_preview(path: Path | str) -> dict[str, Any] | None:
  target = Path(path)
  if not target.exists():
    return None
  try:
    data = json.loads(target.read_text(encoding="utf-8"))
  except (json.JSONDecodeError, OSError):
    return None
  return data if isinstance(data, dict) else None


def load_latest_live_digest_preview(output_root: Path | str) -> dict[str, Any] | None:
  latest = find_latest_live_digest_preview_path(output_root)
  if latest is None:
    return None
  return load_live_digest_preview(latest)


def create_live_digest_preview_from_latest_pack(
  *,
  output_root: Path | str,
  theme_name: str | None = None,
  recipient_group_name: str | None = None,
  user_note: str | None = None,
  login_required: bool,
  is_authenticated: bool,
  auth_role: str,
  user_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
  """Build and save digest preview from latest pack. Never sends email."""
  run_id = generate_run_id()
  started_at = _utc_now_iso()
  resolved_theme = str(theme_name or "").strip()
  resolved_ctx = normalize_user_context(user_context)

  def _finalize(
    result: dict[str, Any],
    *,
    theme: str | None = None,
    source_paths: list[str] | None = None,
    action_type: str = "live_digest_preview",
    operation_metadata: dict[str, Any] | None = None,
  ) -> dict[str, Any]:
    paths = [p for p in (source_paths or []) if p]
    record_live_run(
      action_type=action_type,
      status=map_result_status(ok=result.get("ok"), error=result.get("error")),
      run_id=run_id,
      started_at=started_at,
      user_context=resolved_ctx,
      theme_name=theme or resolved_theme or None,
      input_summary=user_note,
      output_artifact_paths=result.get("saved_paths") or {},
      source_artifact_paths=paths,
      error_summary=None if result.get("ok") else str(result.get("message") or result.get("error") or ""),
      operation_metadata=operation_metadata,
      project_root=output_root,
    )
    result["run_id"] = run_id
    return result

  assert_preview_only_operation()
  can_create_live_digest_preview()

  access_ok, access_error, access_message, resolved_ctx = evaluate_digest_preview_access(
    login_required=login_required,
    is_authenticated=is_authenticated,
    auth_role=auth_role,
    user_context=resolved_ctx,
  )
  if not access_ok:
    return _finalize(
      {"ok": False, "error": access_error, "message": access_message},
      operation_metadata=digest_preview_safety_metadata(uses_web_signals=False),
    )

  pack, resolved_path, source_type = resolve_latest_web_signal_pack(output_root)
  pack_path = resolved_path
  if pack_path is None:
    return _finalize(
      {
      "ok": False,
      "error": "missing_source_pack",
      "message": "latest web signal pack がありません。先に Web Signal Pack または Next Cycle Pack を作成してください。",
    },
    )

  pack = pack or load_live_web_signal_pack(pack_path)
  if not pack and pack_path is not None:
    from tech_cartography.services.live_next_cycle_tavily_runner import load_next_cycle_web_signal_pack

    pack = load_next_cycle_web_signal_pack(pack_path)
  if not pack:
    return _finalize(
      {
      "ok": False,
      "error": "invalid_source_pack",
      "message": "source pack の読み込みに失敗しました。",
    },
      source_paths=[str(pack_path)],
    )

  try:
    preview = generate_live_digest_preview(
      pack,
      source_pack_path=str(pack_path),
      theme_name=theme_name or str(pack.get("theme_name") or ""),
      recipient_group_name=recipient_group_name,
      user_note=user_note,
    )
    review = build_web_signal_review(output_root)
    preview = integrate_review_into_preview(preview, review)
    preview = attach_strategic_watch_artifact_references(preview, output_root)
    preview = attach_user_run_metadata(preview, user_context=resolved_ctx, run_id=run_id)
    active, active_path = get_active_watch_profile(output_root)
    if active_path:
      preview["active_watch_profile_path"] = active_path
      preview["active_watch_profile_id"] = active.get("profile_id")
    review_saved: dict[str, str] | None = None
    try:
      review_saved = save_web_signal_review(review, output_root)
      record_web_signal_review_run(
        review=review,
        output_root=output_root,
        user_context=resolved_ctx,
        saved_paths=review_saved,
      )
    except (OSError, ValueError):
      review_saved = None
    saved_paths = save_live_digest_preview(preview, output_root)
    uses_web_signals = bool(review.get("artifact_exists"))
    source_paths = [str(pack_path)]
    web_signal_path = review.get("source_artifact_path")
    if uses_web_signals and web_signal_path:
      source_paths.append(str(web_signal_path))
    action_type = DIGEST_WITH_SIGNALS_ACTION if uses_web_signals else "live_digest_preview"
    run_metadata = digest_preview_safety_metadata(
      uses_web_signals=uses_web_signals,
      signal_count=int(review.get("total_signal_count") or 0),
    )
  except (OSError, ValueError) as exc:
    return _finalize(
      {"ok": False, "error": "save_failed", "message": str(exc)},
      source_paths=[str(pack_path)],
      theme=str(pack.get("theme_name") or ""),
      operation_metadata=digest_preview_safety_metadata(uses_web_signals=False),
    )

  return _finalize(
    {
    "ok": True,
    "error": None,
    "message": "メール下書きプレビューを作成しました（送信なし）。",
    "preview": preview,
    "saved_paths": saved_paths,
    "email_send_disabled": email_send_is_disabled(),
    "source_type": source_type or preview.get("source_type"),
    "uses_web_signals": uses_web_signals,
  },
    source_paths=source_paths,
    theme=str(preview.get("theme_name") or pack.get("theme_name") or ""),
    action_type=action_type,
    operation_metadata=run_metadata,
  )
