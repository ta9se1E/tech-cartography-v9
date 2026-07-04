"""Digest email preview and self-only delivery helpers for v9."""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from .persistence import PROJECT_ROOT, ensure_v9_run_dirs

EMAIL_SCHEMA_VERSION = "v9.6a"
EMAIL_SEND_MODE_PREVIEW = "preview"
EMAIL_SEND_MODE_SELF_ONLY = "self_only"
_ALLOWED_SEND_MODES = {EMAIL_SEND_MODE_PREVIEW, EMAIL_SEND_MODE_SELF_ONLY}
_INVALID_SECRET_VALUES = {"", "dummy", "placeholder", "<secret-manager-only>"}
_URL_PATTERN = re.compile(r"(https?://[^\s<>()]+)")
_BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")
_NUMBERED_ITEM_PATTERN = re.compile(r"^\d+\.\s+")
_MULTI_RECIPIENT_SPLIT_PATTERN = re.compile(r"[,\n;\r\t]")
_EMAIL_LINEBREAK_PATTERN = re.compile(r"[\r\n]")


@dataclass(frozen=True)
class EmailDeliveryConfig:
  send_mode: str
  disabled: bool
  sender: str
  self_recipient: str
  recipient_allowlist: tuple[str, ...]
  smtp_host: str
  smtp_port: int
  smtp_username: str
  smtp_password: str
  use_starttls: bool
  timeout_seconds: int


def load_email_delivery_config(
  environ: Mapping[str, str] | None = None,
) -> EmailDeliveryConfig:
  env = _load_email_delivery_environment(environ)
  disabled = _env_bool(env, "DISABLE_EMAIL_SEND", True)
  send_mode = str(env.get("EMAIL_SEND_MODE", EMAIL_SEND_MODE_PREVIEW) or EMAIL_SEND_MODE_PREVIEW).strip().lower()
  if send_mode not in _ALLOWED_SEND_MODES:
    send_mode = EMAIL_SEND_MODE_PREVIEW
  sender = _sanitize_single_line(_first_non_empty_env_value(env, "EMAIL_SENDER", "SMTP_FROM_EMAIL"))
  self_recipient = _sanitize_single_line(_first_non_empty_env_value(env, "EMAIL_SELF_RECIPIENT", "SMTP_FROM_EMAIL"))
  allowlist_value = _first_non_empty_env_value(env, "EMAIL_RECIPIENT_ALLOWLIST", "SMTP_FROM_EMAIL")
  allowlist = tuple(
    sorted(
      {
        _sanitize_single_line(item).lower()
        for item in re.split(r"[,\n;]+", allowlist_value)
        if _sanitize_single_line(item)
      }
    )
  )
  smtp_port = _safe_int(str(env.get("SMTP_PORT", "") or ""), default=0)
  smtp_password = _first_non_empty_env_value(env, "SMTP_PASSWORD")
  if smtp_password.lower() in _INVALID_SECRET_VALUES:
    smtp_password = ""
  return EmailDeliveryConfig(
    send_mode=send_mode,
    disabled=disabled,
    sender=sender,
    self_recipient=self_recipient,
    recipient_allowlist=allowlist,
    smtp_host=_sanitize_single_line(_first_non_empty_env_value(env, "SMTP_HOST")),
    smtp_port=smtp_port,
    smtp_username=_sanitize_single_line(_first_non_empty_env_value(env, "SMTP_USERNAME", "SMTP_USER")),
    smtp_password=smtp_password,
    use_starttls=_env_bool(env, "SMTP_USE_STARTTLS", True),
    timeout_seconds=max(_safe_int(_first_non_empty_env_value(env, "SMTP_TIMEOUT_SECONDS", "SMTP_TIMEOUT"), default=30), 1),
  )


def build_digest_email_subject(
  theme_name: str,
) -> str:
  cleaned = _sanitize_single_line(theme_name)
  if not cleaned:
    cleaned = "Weekly Watch"
  subject = f"[Tech Cartography] {cleaned} - Weekly Watch"
  if len(subject) > 140:
    budget = 140 - len("[Tech Cartography]  - Weekly Watch")
    clipped = cleaned[: max(budget - 1, 10)].rstrip()
    cleaned = clipped + "..."
    subject = f"[Tech Cartography] {cleaned} - Weekly Watch"
  return subject


def build_digest_email_preview(
  digest_markdown: str,
  theme_name: str,
  data_source: str,
  signals: list[dict],
  *,
  data_source_mode: str | None = None,
  watch_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
  markdown_text = str(digest_markdown or "").strip()
  subject = build_digest_email_subject(theme_name)
  signal_dicts = [dict(signal or {}) for signal in list(signals or [])]
  plain_text_body = _build_plain_text_body(
    digest_markdown=markdown_text,
    data_source=data_source,
    signal_count=len(signal_dicts),
  )
  html_body = _markdown_to_safe_html(markdown_text, data_source=data_source, signal_count=len(signal_dicts))
  return {
    "subject": subject,
    "theme_name": str(theme_name or "").strip(),
    "data_source": str(data_source or "").strip(),
    "data_source_mode": str(data_source_mode or "").strip(),
    "watch_profile": dict(watch_profile or {}),
    "signals": signal_dicts,
    "digest_markdown": markdown_text,
    "plain_text_body": plain_text_body,
    "html_body": html_body,
    "digest_sha256": hashlib.sha256(markdown_text.encode("utf-8")).hexdigest(),
    "signal_count": len(signal_dicts),
  }


def validate_self_only_delivery(
  config: EmailDeliveryConfig,
  recipient: str,
  signals: list[dict],
  data_source: str,
  *,
  data_source_mode: str | None = None,
) -> list[dict]:
  rows: list[dict] = []
  cleaned_recipient = _sanitize_single_line(recipient).lower()
  source_mode = str(data_source_mode or "").strip().lower()
  source_label = str(data_source or "").strip()

  if config.disabled:
    rows.append({"status": "error", "message": "メール送信は停止中です（DISABLE_EMAIL_SEND=true）。"})
  if config.send_mode != EMAIL_SEND_MODE_SELF_ONLY:
    rows.append({"status": "error", "message": "EMAIL_SEND_MODE=self_only の場合のみ実送信できます。"})
  if not _is_valid_single_email(config.sender):
    rows.append({"status": "error", "message": "EMAIL_SENDER が未設定または不正です。"})
  if not _is_valid_single_email(config.self_recipient):
    rows.append({"status": "error", "message": "EMAIL_SELF_RECIPIENT が未設定または不正です。"})
  if not _is_valid_single_email(cleaned_recipient):
    rows.append({"status": "error", "message": "送信先メールアドレスが不正です。"})
  if _looks_like_multiple_recipients(recipient):
    rows.append({"status": "error", "message": "複数宛先は許可されていません。"})
  if cleaned_recipient != config.self_recipient.lower():
    rows.append({"status": "error", "message": "recipient は EMAIL_SELF_RECIPIENT と完全一致する必要があります。"})
  if cleaned_recipient not in set(config.recipient_allowlist):
    rows.append({"status": "error", "message": "recipient が EMAIL_RECIPIENT_ALLOWLIST に含まれていません。"})
  if not config.smtp_host:
    rows.append({"status": "error", "message": "SMTP_HOST が未設定です。"})
  if config.smtp_port <= 0:
    rows.append({"status": "error", "message": "SMTP_PORT が未設定または不正です。"})
  if not config.smtp_username:
    rows.append({"status": "error", "message": "SMTP_USERNAME が未設定です。"})
  if not config.smtp_password:
    rows.append({"status": "error", "message": "SMTP_PASSWORD が未設定です。"})

  source_errors, source_warnings = _evaluate_signal_source_policy(
    list(signals or []),
    data_source=source_label,
    data_source_mode=source_mode,
  )
  rows.extend({"status": "error", "message": message} for message in source_errors)
  rows.extend({"status": "warning", "message": message} for message in source_warnings)
  return rows


def run_email_delivery_dry_run(
  preview: dict,
  config: EmailDeliveryConfig,
) -> dict:
  recipient = str(config.self_recipient or "").strip()
  validation_rows = validate_self_only_delivery(
    config,
    recipient,
    list(preview.get("signals", []) or []),
    str(preview.get("data_source", "") or ""),
    data_source_mode=str(preview.get("data_source_mode", "") or ""),
  )
  errors = [str(row.get("message", "") or "") for row in validation_rows if str(row.get("status", "") or "") == "error"]
  warnings = [str(row.get("message", "") or "") for row in validation_rows if str(row.get("status", "") or "") == "warning"]
  body = str(preview.get("plain_text_body", "") or "")
  if not body.strip():
    errors.append("メール本文が空です。")
  if "http://" not in body and "https://" not in body:
    warnings.append("Preview本文に source URL が見つかりません。")
  status = "ready"
  if errors:
    status = "blocked"
  elif warnings:
    status = "warning"
  return {
    "schema_version": EMAIL_SCHEMA_VERSION,
    "delivery_run_id": _build_delivery_run_id(),
    "created_at": _now_iso(),
    "status": status,
    "send_mode": config.send_mode,
    "send_attempted": False,
    "send_succeeded": False,
    "recipient": recipient,
    "recipient_masked": _mask_email(recipient),
    "sender_masked": _mask_email(config.sender),
    "subject": str(preview.get("subject", "") or ""),
    "data_source": str(preview.get("data_source", "") or ""),
    "signal_count": int(preview.get("signal_count", 0) or 0),
    "validation_errors": errors,
    "validation_warnings": warnings,
    "digest_sha256": str(preview.get("digest_sha256", "") or ""),
    "smtp_host": config.smtp_host or "",
    "safe_error_message": errors[0] if errors else "",
  }


def send_digest_email_self_only(
  preview: dict,
  config: EmailDeliveryConfig,
  *,
  smtp_factory: type[smtplib.SMTP] | None = None,
  smtp_ssl_factory: type[smtplib.SMTP_SSL] | None = None,
) -> dict:
  dry_run_result = run_email_delivery_dry_run(preview, config)
  result = dict(dry_run_result)
  result["send_attempted"] = False
  result["send_succeeded"] = False
  if dry_run_result["status"] == "blocked":
    result["safe_error_message"] = dry_run_result["validation_errors"][0] if dry_run_result["validation_errors"] else "delivery blocked"
    return result

  recipient = str(config.self_recipient or "").strip()
  message = EmailMessage()
  message["Subject"] = str(preview.get("subject", "") or "")
  message["From"] = config.sender
  message["To"] = recipient
  message.set_content(str(preview.get("plain_text_body", "") or ""))
  message.add_alternative(str(preview.get("html_body", "") or ""), subtype="html")

  result["send_attempted"] = True
  try:
    if config.smtp_port == 465 and not config.use_starttls:
      client_cls = smtp_ssl_factory or smtplib.SMTP_SSL
      with client_cls(config.smtp_host, config.smtp_port, timeout=config.timeout_seconds) as server:
        server.login(config.smtp_username, config.smtp_password)
        server.send_message(message)
    else:
      client_cls = smtp_factory or smtplib.SMTP
      with client_cls(config.smtp_host, config.smtp_port, timeout=config.timeout_seconds) as server:
        server.ehlo()
        if config.use_starttls:
          context = ssl.create_default_context()
          server.starttls(context=context)
          server.ehlo()
        server.login(config.smtp_username, config.smtp_password)
        server.send_message(message)
  except (OSError, smtplib.SMTPException) as exc:
    result["status"] = "blocked" if dry_run_result["status"] == "blocked" else "error"
    result["send_succeeded"] = False
    result["error_type"] = type(exc).__name__
    result["safe_error_message"] = f"SMTP送信に失敗しました: {type(exc).__name__}"
    return result

  result["status"] = "sent"
  result["send_succeeded"] = True
  result["safe_error_message"] = ""
  result["error_type"] = ""
  return result


def save_email_delivery_log(
  result: dict,
  output_dir: Path | str | None = None,
) -> Path:
  dirs = ensure_v9_run_dirs(Path(output_dir) if output_dir is not None else None)
  runs_dir = dirs["root"] / "email_delivery_runs"
  runs_dir.mkdir(parents=True, exist_ok=True)
  result_payload = dict(result or {})
  delivery_run_id, target_dir = _reserve_email_delivery_run_dir(
    runs_dir,
    preferred_run_id=str(result_payload.get("delivery_run_id", "") or "").strip(),
  )
  path = target_dir / "email_delivery_log.json"
  payload = {
    "schema_version": EMAIL_SCHEMA_VERSION,
    "delivery_run_id": delivery_run_id,
    "created_at": str(result_payload.get("created_at", "") or _now_iso()),
    "status": str(result_payload.get("status", "") or ""),
    "send_mode": str(result_payload.get("send_mode", "") or ""),
    "recipient_masked": str(result_payload.get("recipient_masked", "") or ""),
    "sender_masked": str(result_payload.get("sender_masked", "") or ""),
    "subject": str(result_payload.get("subject", "") or ""),
    "data_source": str(result_payload.get("data_source", "") or ""),
    "signal_count": int(result_payload.get("signal_count", 0) or 0),
    "digest_sha256": str(result_payload.get("digest_sha256", "") or ""),
    "send_attempted": _is_true_bool(result_payload.get("send_attempted")),
    "send_succeeded": _is_true_bool(result_payload.get("send_succeeded")),
    "smtp_host": str(result_payload.get("smtp_host", "") or ""),
    "error_type": str(result_payload.get("error_type", "") or ""),
    "safe_error_message": str(result_payload.get("safe_error_message", "") or ""),
  }
  path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  return path


def is_successful_digest_delivery_record(
  payload: Mapping[str, Any] | dict[str, Any],
  digest_sha256: str,
) -> bool:
  expected_digest = str(digest_sha256 or "").strip()
  if not expected_digest:
    return False
  record = dict(payload or {})
  if str(record.get("digest_sha256", "") or "").strip() != expected_digest:
    return False
  return _is_true_bool(record.get("send_attempted")) and _is_true_bool(record.get("send_succeeded"))


def has_successful_digest_delivery(
  delivery_log_root: Path | str,
  digest_sha256: str,
) -> bool:
  expected_digest = str(digest_sha256 or "").strip()
  if not expected_digest:
    return False
  runs_dir = _resolve_email_delivery_runs_dir(delivery_log_root)
  if not runs_dir.exists():
    return False
  for log_path in runs_dir.glob("*/email_delivery_log.json"):
    try:
      payload = json.loads(log_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
      continue
    if is_successful_digest_delivery_record(payload, expected_digest):
      return True
  return False


def _build_plain_text_body(
  *,
  digest_markdown: str,
  data_source: str,
  signal_count: int,
) -> str:
  lines = [
    digest_markdown.strip(),
    "",
    "---",
    f"データソース: {data_source}",
    f"Signal件数: {signal_count}",
    "注意事項: このメールは review-aware Digest Preview をそのまま送信しています。",
  ]
  return "\n".join(lines).strip() + "\n"


def _markdown_to_safe_html(markdown_text: str, *, data_source: str, signal_count: int) -> str:
  body_lines = [line.rstrip() for line in str(markdown_text or "").splitlines()]
  html_parts = [
    "<html><body>",
    '<div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; line-height: 1.6;">',
  ]
  paragraph_buffer: list[str] = []
  list_stack: list[str] = []

  def flush_paragraph() -> None:
    nonlocal paragraph_buffer
    if not paragraph_buffer:
      return
    text = " ".join(item.strip() for item in paragraph_buffer if item.strip())
    if text:
      html_parts.append(f"<p>{_format_inline_html(text)}</p>")
    paragraph_buffer = []

  def close_lists() -> None:
    nonlocal list_stack
    while list_stack:
      html_parts.append(f"</{list_stack.pop()}>")

  for raw_line in body_lines:
    stripped = raw_line.strip()
    if not stripped:
      flush_paragraph()
      close_lists()
      continue
    if stripped.startswith("### "):
      flush_paragraph()
      close_lists()
      html_parts.append(f"<h3>{_format_inline_html(stripped[4:])}</h3>")
      continue
    if stripped.startswith("## "):
      flush_paragraph()
      close_lists()
      html_parts.append(f"<h2>{_format_inline_html(stripped[3:])}</h2>")
      continue
    if stripped.startswith("# "):
      flush_paragraph()
      close_lists()
      html_parts.append(f"<h1>{_format_inline_html(stripped[2:])}</h1>")
      continue
    if stripped.startswith("- "):
      flush_paragraph()
      if not list_stack or list_stack[-1] != "ul":
        close_lists()
        html_parts.append("<ul>")
        list_stack.append("ul")
      html_parts.append(f"<li>{_format_inline_html(stripped[2:])}</li>")
      continue
    if _NUMBERED_ITEM_PATTERN.match(stripped):
      flush_paragraph()
      if not list_stack or list_stack[-1] != "ol":
        close_lists()
        html_parts.append("<ol>")
        list_stack.append("ol")
      item_text = _NUMBERED_ITEM_PATTERN.sub("", stripped, count=1)
      html_parts.append(f"<li>{_format_inline_html(item_text)}</li>")
      continue
    paragraph_buffer.append(stripped)

  flush_paragraph()
  close_lists()
  html_parts.extend(
    [
      "<hr />",
      f"<p><strong>データソース:</strong> {_format_inline_html(data_source)}</p>",
      f"<p><strong>Signal件数:</strong> {signal_count}</p>",
      "<p><strong>注意事項:</strong> このメールは review-aware Digest Preview をそのまま送信しています。</p>",
      "</div>",
      "</body></html>",
    ]
  )
  return "\n".join(html_parts)


def _format_inline_html(text: str) -> str:
  escaped = html.escape(str(text or ""))
  escaped = _BOLD_PATTERN.sub(lambda match: f"<strong>{html.escape(match.group(1))}</strong>", escaped)
  return _URL_PATTERN.sub(lambda match: f'<a href="{match.group(1)}">{match.group(1)}</a>', escaped)


def _evaluate_signal_source_policy(
  signals: list[dict[str, Any]],
  *,
  data_source: str,
  data_source_mode: str,
) -> tuple[list[str], list[str]]:
  errors: list[str] = []
  warnings: list[str] = []
  mode = str(data_source_mode or "").strip().lower()
  source_label = str(data_source or "").strip()
  if mode == "demo" or "デモ" in source_label:
    errors.append("デモデータは Preview のみで、実送信は禁止です。")
    return errors, warnings
  if mode == "csv" or "CSV" in source_label.upper():
    errors.append("CSVアップロードデータは Preview のみで、実送信は禁止です。")
    return errors, warnings
  if mode == "json" or "JSON" in source_label.upper():
    errors.append("JSONアップロードデータは Preview のみで、実送信は禁止です。")
    return errors, warnings
  if mode != "retrieval_saved":
    errors.append("取得済みデータモード以外では実送信できません。")
    return errors, warnings
  if not signals:
    errors.append("送信対象の Signal がありません。")
    return errors, warnings

  has_real_retrieval = False
  for signal in signals:
    if bool(signal.get("is_synthetic_demo", False)):
      errors.append("synthetic data を含むため実送信できません。")
      return errors, warnings
    retrieval_mode = str(signal.get("retrieval_mode", "") or "").strip().lower()
    data_origin = str(signal.get("data_origin", "") or "").strip().lower()
    if retrieval_mode == "real":
      has_real_retrieval = True
    if retrieval_mode == "local" or data_origin == "base_signal":
      errors.append("demo/base 由来の Signal を含むため実送信できません。")
      return errors, warnings
    for trace in list(signal.get("source_trace", []) or []):
      trace_origin = str(dict(trace or {}).get("data_origin", "") or "").strip().lower()
      trace_status = str(dict(trace or {}).get("provider_status", "") or "").strip().lower()
      if trace_origin == "base_signal":
        errors.append("base signal trace を含むため実送信できません。")
        return errors, warnings
      if trace_status == "partial_success":
        warnings.append("partial_success の取得結果を含みます。内容確認のうえ self-only 送信してください。")
  if not has_real_retrieval:
    errors.append("retrieval_mode=real の取得済みデータを確認できないため実送信できません。")
  return errors, _dedupe_strings(warnings)


def _sanitize_single_line(value: str) -> str:
  cleaned = _EMAIL_LINEBREAK_PATTERN.sub(" ", str(value or ""))
  return re.sub(r"\s+", " ", cleaned).strip()


def _is_valid_single_email(value: str) -> bool:
  candidate = _sanitize_single_line(value)
  if not candidate or _looks_like_multiple_recipients(candidate):
    return False
  return bool(re.fullmatch(r"[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+", candidate))


def _looks_like_multiple_recipients(value: str) -> bool:
  candidate = str(value or "")
  return bool(_MULTI_RECIPIENT_SPLIT_PATTERN.search(candidate.strip()))


def _mask_email(value: str) -> str:
  email = _sanitize_single_line(value)
  if "@" not in email:
    return "***"
  local, domain = email.split("@", 1)
  masked_local = "*" if len(local) <= 1 else f"{local[0]}***"
  return f"{masked_local}@{domain}"


def _env_bool(env: Mapping[str, str], name: str, default: bool) -> bool:
  raw = env.get(name)
  if raw is None:
    return default
  return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _safe_int(value: str, default: int) -> int:
  try:
    return int(str(value).strip())
  except (TypeError, ValueError):
    return default


def _build_delivery_run_id() -> str:
  return "email_delivery_" + datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%f") + f"_{uuid4().hex[:8]}"


def _now_iso() -> str:
  return datetime.now().astimezone().isoformat(timespec="seconds")


def _resolve_email_delivery_runs_dir(delivery_log_root: Path | str) -> Path:
  root = Path(delivery_log_root)
  if root.name == "email_delivery_runs":
    return root
  return root / "email_delivery_runs"


def _load_email_delivery_environment(
  environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
  if environ is not None:
    return dict(environ)
  env = _read_project_dotenv(PROJECT_ROOT / ".env")
  env.update(os.environ)
  return env


def _read_project_dotenv(path: Path) -> dict[str, str]:
  try:
    lines = path.read_text(encoding="utf-8").splitlines()
  except FileNotFoundError:
    return {}
  except OSError:
    return {}
  payload: dict[str, str] = {}
  for raw_line in lines:
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
      continue
    key, value = line.split("=", 1)
    key = key.strip()
    value = value.strip()
    if value and len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
      value = value[1:-1]
    payload[key] = value
  return payload


def _first_non_empty_env_value(
  env: Mapping[str, str],
  *names: str,
) -> str:
  for name in names:
    value = str(env.get(name, "") or "").strip()
    if value:
      return value
  return ""


def _reserve_email_delivery_run_dir(
  runs_dir: Path,
  *,
  preferred_run_id: str = "",
) -> tuple[str, Path]:
  base_run_id = _sanitize_delivery_run_id(preferred_run_id) or _build_delivery_run_id()
  candidate_run_id = base_run_id
  while True:
    target_dir = runs_dir / candidate_run_id
    try:
      target_dir.mkdir(parents=True, exist_ok=False)
      return candidate_run_id, target_dir
    except FileExistsError:
      candidate_run_id = _derive_collision_safe_delivery_run_id(base_run_id)


def _derive_collision_safe_delivery_run_id(base_run_id: str) -> str:
  return f"{base_run_id}_{uuid4().hex[:8]}"


def _sanitize_delivery_run_id(value: str) -> str:
  cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "_", _sanitize_single_line(value))
  return cleaned.strip("._")


def _is_true_bool(value: object) -> bool:
  return value is True


def _dedupe_strings(values: list[str]) -> list[str]:
  seen: set[str] = set()
  output: list[str] = []
  for value in values:
    key = str(value or "").strip()
    if not key or key in seen:
      continue
    seen.add(key)
    output.append(key)
  return output


__all__ = [
  "EMAIL_SCHEMA_VERSION",
  "EMAIL_SEND_MODE_PREVIEW",
  "EMAIL_SEND_MODE_SELF_ONLY",
  "EmailDeliveryConfig",
  "build_digest_email_preview",
  "build_digest_email_subject",
  "has_successful_digest_delivery",
  "is_successful_digest_delivery_record",
  "load_email_delivery_config",
  "run_email_delivery_dry_run",
  "save_email_delivery_log",
  "send_digest_email_self_only",
  "validate_self_only_delivery",
]
