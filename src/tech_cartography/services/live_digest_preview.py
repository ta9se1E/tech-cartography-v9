"""Live digest mail preview from latest Web Signal pack (Phase 25F)."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tech_cartography.services.live_web_signal_pack import (
  find_latest_live_web_signal_pack_path,
  load_latest_live_web_signal_pack,
  load_live_web_signal_pack,
)

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
    "preview_mode": PREVIEW_ONLY_LABEL,
  }


def _assert_no_sensitive_material(serialized: str) -> None:
  lowered = serialized.lower()
  if "tavily_api_key" in lowered or '"api_key"' in lowered:
    raise ValueError("Refusing to save payload containing API key material")
  if _SENSITIVE_KEY_PATTERN.search(serialized):
    if any(token in lowered for token in ("api_key", "smtp_password", "authorization:")):
      raise ValueError("Refusing to save payload containing sensitive material")


def build_save_payload(preview: dict[str, Any]) -> dict[str, Any]:
  return {
    "source_pack_path": preview.get("source_pack_path"),
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
  }


def save_live_digest_preview(
  preview: dict[str, Any],
  output_root: Path | str,
) -> dict[str, str]:
  root = Path(output_root)
  out_dir = root / "outputs" / "live_digest_preview"
  out_dir.mkdir(parents=True, exist_ok=True)

  created_at = str(preview.get("created_at") or _utc_now_iso())
  slug = _timestamp_slug(created_at)
  json_path = out_dir / f"live_digest_preview_{slug}.json"
  md_path = out_dir / f"live_digest_preview_{slug}.md"
  txt_path = out_dir / f"live_digest_preview_{slug}.txt"

  payload = build_save_payload(preview)
  serialized = json.dumps(payload, indent=2, ensure_ascii=False)
  _assert_no_sensitive_material(serialized)

  json_path.write_text(serialized + "\n", encoding="utf-8")
  md_path.write_text(str(preview.get("markdown_body") or ""), encoding="utf-8")
  txt_path.write_text(str(preview.get("plain_text_body") or ""), encoding="utf-8")
  return {"json": str(json_path), "markdown": str(md_path), "text": str(txt_path)}


def live_digest_preview_dir(output_root: Path | str) -> Path:
  return Path(output_root) / "outputs" / "live_digest_preview"


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
) -> dict[str, Any]:
  """Build and save digest preview from latest pack. Never sends email."""
  assert_preview_only_operation()
  can_create_live_digest_preview()

  if login_required and not is_authenticated:
    return {"ok": False, "error": "login_required", "message": "ログイン後に実行できます。"}
  if login_required and str(auth_role or "member") != "admin":
    return {"ok": False, "error": "admin_required", "message": "管理者のみ実行できます。"}

  pack_path = find_latest_live_web_signal_pack_path(output_root)
  if pack_path is None:
    return {
      "ok": False,
      "error": "missing_source_pack",
      "message": "latest live_web_signal_pack がありません。先に Web Signal Pack を作成してください。",
    }

  pack = load_live_web_signal_pack(pack_path)
  if not pack:
    return {
      "ok": False,
      "error": "invalid_source_pack",
      "message": "source pack の読み込みに失敗しました。",
    }

  try:
    preview = generate_live_digest_preview(
      pack,
      source_pack_path=str(pack_path),
      theme_name=theme_name or str(pack.get("theme_name") or ""),
      recipient_group_name=recipient_group_name,
      user_note=user_note,
    )
    saved_paths = save_live_digest_preview(preview, output_root)
  except (OSError, ValueError) as exc:
    return {"ok": False, "error": "save_failed", "message": str(exc)}

  return {
    "ok": True,
    "error": None,
    "message": "メール下書きプレビューを作成しました（送信なし）。",
    "preview": preview,
    "saved_paths": saved_paths,
    "email_send_disabled": email_send_is_disabled(),
  }
