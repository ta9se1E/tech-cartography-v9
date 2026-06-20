"""Orchestration for manual weekly digest test email (Phase 24.2)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tech_cartography.delivery.email_outbox import (
  load_email_draft_for_publication,
)
from tech_cartography.delivery.email_sender import can_send_email, send_email_smtp
from tech_cartography.delivery.japanese_copy import ja_digest_subject, ja_status_message
from tech_cartography.delivery.recipient_config import resolve_recipients
from tech_cartography.delivery.send_log import (
  EmailSendLog,
  STATUS_BLOCKED_MISSING_ADAPTER,
  STATUS_BLOCKED_MISSING_RECIPIENT,
  STATUS_BLOCKED_RECIPIENT_DISABLED,
  STATUS_DRAFT_SAVED as LOG_DRAFT_SAVED,
  STATUS_DRY_RUN,
  STATUS_FAILED as LOG_FAILED,
  STATUS_SENT as LOG_SENT,
  save_send_log,
)
from tech_cartography.delivery.store import build_delivery_package
from tech_cartography.web_signals.schema import utc_now_iso


@dataclass
class SendWeeklyDigestResult:
  publication_number: str
  output_dir: str
  recipient_group: str
  to: list[str] = field(default_factory=list)
  cc: list[str] = field(default_factory=list)
  dry_run: bool = False
  build_draft: bool = False
  send_email: bool = False
  send_log: EmailSendLog | None = None
  send_log_paths: dict[str, Path] = field(default_factory=dict)
  delivery_paths: dict[str, str] = field(default_factory=dict)
  email_send_result: dict[str, Any] | None = None


def _recipient_blocked_status(errors: list[str]) -> str:
  joined = " ".join(errors)
  if "enabled=false" in joined or "無効です" in joined:
    return STATUS_BLOCKED_RECIPIENT_DISABLED
  return STATUS_BLOCKED_MISSING_RECIPIENT


def _make_send_log(
  *,
  publication_number: str,
  subject: str,
  to_count: int,
  cc_count: int,
  status: str,
  message: str,
  recipient_group: str,
  draft_paths: dict[str, Path] | None = None,
  error_summary: str | None = None,
) -> EmailSendLog:
  draft_paths = draft_paths or {}
  return EmailSendLog(
    log_id=f"sendlog-{uuid.uuid4().hex[:10]}",
    created_at=utc_now_iso(),
    publication_number=publication_number,
    subject=subject,
    to_count=to_count,
    cc_count=cc_count,
    status=status,
    message=message,
    draft_path=str(draft_paths.get("email_draft_md", "")) or None,
    html_path=str(draft_paths.get("email_draft_html", "")) or None,
    json_path=str(draft_paths.get("email_draft_json", "")) or None,
    error_summary=error_summary,
    recipient_group=recipient_group,
  )


def run_weekly_digest_send_test(
  *,
  publication_number: str,
  project_root: Path | str,
  output_dir: Path | str = "outputs/delivery",
  recipient_config_path: Path | str,
  recipient_group: str = "default",
  dry_run: bool = False,
  build_draft: bool = False,
  send_email: bool = False,
  subject_prefix: str | None = None,
  include_zip: bool = False,
) -> SendWeeklyDigestResult:
  root = Path(project_root)
  out = Path(output_dir)
  if not out.is_absolute():
    out = root / out
  pub = str(publication_number).strip()
  group = str(recipient_group).strip() or "default"

  to_list, cc_list, errors = resolve_recipients(recipient_config_path, group)

  subject = ja_digest_subject(pub, utc_now_iso()[:10])
  result = SendWeeklyDigestResult(
    publication_number=pub,
    output_dir=str(out),
    recipient_group=group,
    to=to_list,
    cc=cc_list,
    dry_run=dry_run,
    build_draft=build_draft,
    send_email=send_email,
  )

  if dry_run:
    if errors:
      status = _recipient_blocked_status(errors)
      message = "dry-run: 宛先設定を確認してください。" + " / ".join(errors)
    else:
      status = STATUS_DRY_RUN
      message = (
        f"dry-run: 送信は行いません。宛先 to={len(to_list)}件 / cc={len(cc_list)}件。"
        " --build-draft または --send-email で下書き作成・送信を実行できます。"
      )
    send_log = _make_send_log(
      publication_number=pub,
      subject=subject,
      to_count=len(to_list),
      cc_count=len(cc_list),
      status=status,
      message=message,
      recipient_group=group,
      error_summary=" / ".join(errors) if errors else None,
    )
    result.send_log = send_log
    result.send_log_paths = save_send_log(send_log, out)
    return result

  should_build = build_draft or send_email
  if should_build and errors:
    status = _recipient_blocked_status(errors)
    send_log = _make_send_log(
      publication_number=pub,
      subject=subject,
      to_count=len(to_list),
      cc_count=len(cc_list),
      status=status,
      message="宛先設定が不正なため、下書き作成・送信を中止しました。",
      recipient_group=group,
      error_summary=" / ".join(errors),
    )
    result.send_log = send_log
    result.send_log_paths = save_send_log(send_log, out)
    return result

  draft_paths: dict[str, Path] = {}
  delivery_result = None

  if should_build:
    delivery_result = build_delivery_package(
      publication_number=pub,
      project_root=root,
      output_dir=out,
      include_zip=include_zip,
      build_email_draft=True,
      email_to=to_list,
      email_cc=cc_list,
      subject_prefix=subject_prefix,
      send_email=False,
    )
    result.delivery_paths = {key: str(path) for key, path in delivery_result.paths.items()}
    draft_paths = {
      key: path
      for key, path in delivery_result.paths.items()
      if key in {"email_draft_md", "email_draft_html", "email_draft_json"}
    }
    subject = delivery_result.email_draft.subject if delivery_result.email_draft else subject

  if not send_email:
    status = LOG_DRAFT_SAVED if should_build else STATUS_DRY_RUN
    if should_build:
        message = ja_status_message(LOG_DRAFT_SAVED)
    else:
      message = "送信オプションがありません。--build-draft または --send-email を指定してください。"
    send_log = _make_send_log(
      publication_number=pub,
      subject=subject,
      to_count=len(to_list),
      cc_count=len(cc_list),
      status=status,
      message=message,
      recipient_group=group,
      draft_paths=draft_paths,
    )
    result.send_log = send_log
    result.send_log_paths = save_send_log(send_log, out)
    return result

  # Explicit send path
  email_draft = delivery_result.email_draft if delivery_result else load_email_draft_for_publication(out, pub)
  if email_draft is None:
    send_log = _make_send_log(
      publication_number=pub,
      subject=subject,
      to_count=len(to_list),
      cc_count=len(cc_list),
      status=STATUS_BLOCKED_MISSING_RECIPIENT,
      message="メール下書きが見つかりません。--build-draft を先に実行してください。",
      recipient_group=group,
    )
    result.send_log = send_log
    result.send_log_paths = save_send_log(send_log, out)
    return result

  ready, smtp_reason = can_send_email()
  if not ready:
    send_log = _make_send_log(
      publication_number=pub,
      subject=email_draft.subject,
      to_count=len(to_list),
      cc_count=len(cc_list),
      status=STATUS_BLOCKED_MISSING_ADAPTER,
      message=f"SMTP未設定のため送信しません。{smtp_reason}",
      recipient_group=group,
      draft_paths=draft_paths,
      error_summary=smtp_reason,
    )
    result.send_log = send_log
    result.send_log_paths = save_send_log(send_log, out)
    return result

  send_result = send_email_smtp(email_draft)
  result.email_send_result = send_result

  if send_result.get("ok"):
    log_status = LOG_SENT
    message = f"テストメールを送信しました（宛先 {send_result.get('recipient_count', 0)} 件）。"
  else:
    log_status = LOG_FAILED if send_result.get("status") == LOG_FAILED else str(send_result.get("status"))
    message = str(send_result.get("message", "送信に失敗しました。"))

  send_log = _make_send_log(
    publication_number=pub,
    subject=email_draft.subject,
    to_count=len(to_list),
    cc_count=len(cc_list),
    status=log_status,
    message=message,
    recipient_group=group,
    draft_paths=draft_paths,
    error_summary=None if send_result.get("ok") else message,
  )
  result.send_log = send_log
  result.send_log_paths = save_send_log(send_log, out)
  return result
