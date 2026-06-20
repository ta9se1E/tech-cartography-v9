"""Email outbox — draft storage before explicit SMTP send (Phase 24.1.1)."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from tech_cartography.delivery.japanese_copy import (
  ja_caveats,
  ja_email_draft_preamble,
  ja_preview_only_notice_short,
  ja_status_description,
  ja_status_label,
  ja_ui_send_disabled_notice,
)
from tech_cartography.delivery.weekly_digest import WeeklyDigest, markdown_to_simple_html
from tech_cartography.web_signals.schema import utc_now_iso

EMAIL_DRAFT_CAUTIONS = [
  *ja_caveats(),
  ja_preview_only_notice_short(),
  ja_ui_send_disabled_notice(),
]

STATUS_PREVIEW_ONLY = "preview_only"
STATUS_DRAFT_SAVED = "draft_saved"
STATUS_BLOCKED_MISSING_RECIPIENT = "blocked_missing_recipient"
STATUS_BLOCKED_MISSING_ADAPTER = "blocked_missing_adapter"
STATUS_SENT = "sent"
STATUS_FAILED = "failed"


@dataclass
class EmailDraft:
  draft_id: str
  created_at: str
  publication_number: str
  to: list[str]
  cc: list[str]
  subject: str
  markdown_body: str
  html_body: str
  attachments: list[str]
  status: str
  caveats: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> EmailDraft:
    return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class EmailOutbox:
  outbox_id: str
  created_at: str
  drafts: list[EmailDraft] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return {
      "outbox_id": self.outbox_id,
      "created_at": self.created_at,
      "drafts": [draft.to_dict() for draft in self.drafts],
    }


def _normalize_recipients(values: list[str] | str | None) -> list[str]:
  if not values:
    return []
  if isinstance(values, str):
    parts = [part.strip() for part in values.replace(";", ",").split(",")]
    return [part for part in parts if part and "@" in part]
  return [str(v).strip() for v in values if str(v).strip() and "@" in str(v)]


def build_email_draft_from_weekly_digest(
  digest: WeeklyDigest,
  *,
  publication_number: str,
  to: list[str] | str | None = None,
  cc: list[str] | str | None = None,
  subject_prefix: str | None = None,
  attachments: list[str] | None = None,
  status: str = STATUS_DRAFT_SAVED,
  send_requested: bool = False,
) -> EmailDraft:
  pub = str(publication_number).strip()
  recipients = _normalize_recipients(to)
  cc_list = _normalize_recipients(cc)

  prefix = str(subject_prefix or "").strip()
  subject = digest.subject
  if prefix:
    subject = f"{prefix} {subject}"

  resolved_status = status
  if send_requested and not recipients:
    resolved_status = STATUS_BLOCKED_MISSING_RECIPIENT
  elif not recipients and resolved_status == STATUS_DRAFT_SAVED:
    resolved_status = STATUS_PREVIEW_ONLY

  status_label = ja_status_label(resolved_status)
  status_desc = ja_status_description(resolved_status)

  email_md_lines = [
    f"宛先: {', '.join(recipients) if recipients else '（未設定）'}",
    f"CC: {', '.join(cc_list) if cc_list else '（なし）'}",
    f"件名: {subject}",
    "",
    ja_email_draft_preamble(),
    "",
    f"- 状態: {status_label}",
    f"- 説明: {status_desc}",
    "- UIからの送信: 無効",
    "- 送信方法: CLIで --send-email を明示した場合のみ",
    "",
    digest.markdown_body,
  ]
  markdown_body = "\n".join(email_md_lines)
  html_body = markdown_to_simple_html(markdown_body)

  return EmailDraft(
    draft_id=f"draft-{uuid.uuid4().hex[:10]}",
    created_at=utc_now_iso(),
    publication_number=pub,
    to=recipients,
    cc=cc_list,
    subject=subject,
    markdown_body=markdown_body,
    html_body=html_body,
    attachments=list(attachments or digest.attachments),
    status=resolved_status,
    caveats=list(EMAIL_DRAFT_CAUTIONS),
  )


def render_email_draft_summary_md(draft: EmailDraft) -> str:
  status_label = ja_status_label(draft.status)
  lines = [
    f"# メール下書き: {draft.publication_number}",
    "",
    f"- draft_id: {draft.draft_id}",
    f"- 作成日時: {draft.created_at}",
    f"- 状態: {status_label} ({draft.status})",
    f"- 宛先: {', '.join(draft.to) if draft.to else '（未設定）'}",
    f"- CC: {', '.join(draft.cc) if draft.cc else '（なし）'}",
    f"- 件名: {draft.subject}",
    "",
    "## 添付候補",
    "",
  ]
  if draft.attachments:
    for path in draft.attachments:
      lines.append(f"- {path}")
  else:
    lines.append("- （なし）")
  lines.extend(["", "## 注意事項", ""])
  for caveat in draft.caveats:
    lines.append(f"- {caveat}")
  lines.extend(["", "## 本文プレビュー", "", draft.markdown_body[:4000]])
  if len(draft.markdown_body) > 4000:
    lines.append("\n…（以下省略）")
  return "\n".join(lines)


def save_email_draft(draft: EmailDraft, output_dir: Path | str) -> dict[str, Path]:
  outbox_dir = Path(output_dir) / "email_outbox"
  outbox_dir.mkdir(parents=True, exist_ok=True)
  pub = draft.publication_number

  paths = {
    "email_draft_md": outbox_dir / f"email_draft_{pub}.md",
    "email_draft_html": outbox_dir / f"email_draft_{pub}.html",
    "email_draft_json": outbox_dir / f"email_draft_{pub}.json",
    "outbox_index": outbox_dir / "outbox_index.json",
  }

  paths["email_draft_md"].write_text(render_email_draft_summary_md(draft), encoding="utf-8")
  paths["email_draft_html"].write_text(draft.html_body, encoding="utf-8")
  paths["email_draft_json"].write_text(
    json.dumps(draft.to_dict(), indent=2, ensure_ascii=False),
    encoding="utf-8",
  )

  index = _load_outbox_index(outbox_dir)
  index.drafts = [d for d in index.drafts if d.publication_number != pub]
  index.drafts.append(draft)
  paths["outbox_index"].write_text(
    json.dumps(index.to_dict(), indent=2, ensure_ascii=False),
    encoding="utf-8",
  )
  return paths


def _load_outbox_index(outbox_dir: Path) -> EmailOutbox:
  index_path = outbox_dir / "outbox_index.json"
  if not index_path.exists():
    return EmailOutbox(outbox_id=f"outbox-{uuid.uuid4().hex[:8]}", created_at=utc_now_iso())
  try:
    data = json.loads(index_path.read_text(encoding="utf-8"))
    drafts = [EmailDraft.from_dict(item) for item in data.get("drafts", [])]
    return EmailOutbox(
      outbox_id=str(data.get("outbox_id", f"outbox-{uuid.uuid4().hex[:8]}")),
      created_at=str(data.get("created_at", utc_now_iso())),
      drafts=drafts,
    )
  except (OSError, json.JSONDecodeError, TypeError):
    return EmailOutbox(outbox_id=f"outbox-{uuid.uuid4().hex[:8]}", created_at=utc_now_iso())


def load_email_draft(path: Path | str) -> EmailDraft | None:
  p = Path(path)
  if not p.exists():
    return None
  try:
    data = json.loads(p.read_text(encoding="utf-8"))
    return EmailDraft.from_dict(data)
  except (OSError, json.JSONDecodeError, TypeError):
    return None


def load_email_draft_for_publication(output_dir: Path | str, publication_number: str) -> EmailDraft | None:
  pub = str(publication_number).strip()
  json_path = Path(output_dir) / "email_outbox" / f"email_draft_{pub}.json"
  return load_email_draft(json_path)
