"""Weekly digest job orchestration for local scheduling (Phase 24.3)."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from tech_cartography.delivery.send_log import (
  STATUS_BLOCKED_MISSING_ADAPTER,
  STATUS_BLOCKED_MISSING_RECIPIENT,
  STATUS_BLOCKED_RECIPIENT_DISABLED,
  STATUS_DRAFT_SAVED,
  STATUS_DRY_RUN,
  STATUS_FAILED,
  STATUS_SENT,
  _load_send_log_index,
)
from tech_cartography.delivery.weekly_digest_send import run_weekly_digest_send_test
from tech_cartography.web_signals.schema import utc_now_iso

JOB_STATUS_DRY_RUN = "dry_run"
JOB_STATUS_DRAFT_SAVED = "draft_saved"
JOB_STATUS_SENT = "sent"
JOB_STATUS_SKIPPED = "skipped_already_sent_this_week"
JOB_STATUS_BLOCKED = "blocked"
JOB_STATUS_FAILED = "failed"

_BLOCKED_SEND_STATUSES = {
  STATUS_BLOCKED_MISSING_ADAPTER,
  STATUS_BLOCKED_MISSING_RECIPIENT,
  STATUS_BLOCKED_RECIPIENT_DISABLED,
}


@dataclass
class WeeklyJobConfig:
  publication_number: str
  recipient_config_path: str
  recipient_group: str = "default"
  output_dir: str = "outputs/delivery"
  project_root: str = "."
  include_zip: bool = True
  build_draft: bool = True
  send_email: bool = False
  dry_run: bool = False
  timezone: str = "Asia/Tokyo"
  run_label: str = "weekly_digest"
  allow_repeat_this_week: bool = False


@dataclass
class WeeklyJobResult:
  job_id: str
  created_at: str
  publication_number: str
  status: str
  message: str
  delivery_paths: dict[str, str] = field(default_factory=dict)
  email_draft_path: str | None = None
  email_sent_path: str | None = None
  send_log_path: str | None = None
  job_log_path: str | None = None
  recipient_group: str | None = None
  run_label: str | None = None

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


def build_weekly_job_config(
  *,
  publication_number: str,
  recipient_config_path: str | Path,
  recipient_group: str = "default",
  output_dir: str | Path = "outputs/delivery",
  project_root: str | Path = ".",
  include_zip: bool = True,
  build_draft: bool = True,
  send_email: bool = False,
  dry_run: bool = False,
  timezone: str = "Asia/Tokyo",
  run_label: str = "weekly_digest",
  allow_repeat_this_week: bool = False,
) -> WeeklyJobConfig:
  return WeeklyJobConfig(
    publication_number=str(publication_number).strip(),
    recipient_config_path=str(recipient_config_path),
    recipient_group=str(recipient_group).strip() or "default",
    output_dir=str(output_dir),
    project_root=str(project_root),
    include_zip=include_zip,
    build_draft=build_draft,
    send_email=send_email,
    dry_run=dry_run,
    timezone=timezone,
    run_label=run_label,
    allow_repeat_this_week=allow_repeat_this_week,
  )


def _parse_created_at_to_tz(created_at: str, timezone: str) -> datetime | None:
  raw = str(created_at or "").strip()
  if not raw:
    return None
  try:
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
      dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo(timezone))
  except (ValueError, KeyError):
    return None


def should_skip_already_sent_this_week(
  publication_number: str,
  output_dir: Path | str,
  *,
  timezone: str = "Asia/Tokyo",
) -> tuple[bool, str]:
  """Return whether a sent log already exists for the current ISO week (Asia/Tokyo)."""
  pub = str(publication_number).strip()
  out = Path(output_dir)
  log_dir = out / "email_send_logs"
  now = datetime.now(ZoneInfo(timezone))
  current_year, current_week, _ = now.isocalendar()

  index = _load_send_log_index(log_dir)
  for entry in index:
    if str(entry.get("publication_number", "")).strip() != pub:
      continue
    if str(entry.get("status", "")).strip() != STATUS_SENT:
      continue
    created = _parse_created_at_to_tz(str(entry.get("created_at", "")), timezone)
    if created is None:
      continue
    year, week, _ = created.isocalendar()
    if year == current_year and week == current_week:
      return (
        True,
        f"今週（{timezone} ISO週 {current_year}-W{current_week:02d}）に送信済みログがあります。"
        f" created_at={entry.get('created_at')}",
      )

  latest = log_dir / f"send_log_latest_{pub}.json"
  if latest.exists():
    try:
      data = json.loads(latest.read_text(encoding="utf-8"))
      if str(data.get("status", "")).strip() == STATUS_SENT:
        created = _parse_created_at_to_tz(str(data.get("created_at", "")), timezone)
        if created is not None:
          year, week, _ = created.isocalendar()
          if year == current_year and week == current_week:
            return (
              True,
              f"今週（{timezone} ISO週 {current_year}-W{current_week:02d}）に送信済みです。"
              f" created_at={data.get('created_at')}",
            )
    except (OSError, json.JSONDecodeError, TypeError):
      pass

  return False, ""


def _map_send_status_to_job_status(send_status: str) -> str:
  status = str(send_status or "").strip()
  if status == STATUS_DRY_RUN:
    return JOB_STATUS_DRY_RUN
  if status == STATUS_DRAFT_SAVED:
    return JOB_STATUS_DRAFT_SAVED
  if status == STATUS_SENT:
    return JOB_STATUS_SENT
  if status == STATUS_FAILED:
    return JOB_STATUS_FAILED
  if status in _BLOCKED_SEND_STATUSES:
    return JOB_STATUS_BLOCKED
  return JOB_STATUS_FAILED


def run_weekly_digest_job(config: WeeklyJobConfig) -> WeeklyJobResult:
  """Run weekly digest delivery job; reuses manual send orchestration."""
  root = Path(config.project_root)
  out = Path(config.output_dir)
  if not out.is_absolute():
    out = root / out
  pub = config.publication_number
  created_at = utc_now_iso()
  job_id = f"job-{uuid.uuid4().hex[:10]}"

  if (
    config.send_email
    and not config.dry_run
    and not config.allow_repeat_this_week
  ):
    skip, reason = should_skip_already_sent_this_week(
      pub,
      out,
      timezone=config.timezone,
    )
    if skip:
      result = WeeklyJobResult(
        job_id=job_id,
        created_at=created_at,
        publication_number=pub,
        status=JOB_STATUS_SKIPPED,
        message=reason,
        recipient_group=config.recipient_group,
        run_label=config.run_label,
      )
      save_weekly_job_log(result, out)
      return result

  recipient_path = Path(config.recipient_config_path)
  if not recipient_path.is_absolute():
    recipient_path = root / recipient_path

  send_result = run_weekly_digest_send_test(
    publication_number=pub,
    project_root=root,
    output_dir=out,
    recipient_config_path=recipient_path,
    recipient_group=config.recipient_group,
    dry_run=config.dry_run,
    build_draft=config.build_draft,
    send_email=config.send_email,
    include_zip=config.include_zip,
  )

  send_log = send_result.send_log
  job_status = JOB_STATUS_DRAFT_SAVED
  message = "週次ジョブを実行しました。"
  send_log_path: str | None = None
  email_draft_path: str | None = None
  email_sent_path: str | None = None

  if send_log:
    job_status = _map_send_status_to_job_status(send_log.status)
    message = send_log.message
    if send_result.send_log_paths:
      send_log_path = str(send_result.send_log_paths.get("send_log_latest", "")) or None
    email_draft_path = send_log.draft_path
    email_sent_path = send_log.sent_path

  result = WeeklyJobResult(
    job_id=job_id,
    created_at=created_at,
    publication_number=pub,
    status=job_status,
    message=message,
    delivery_paths=dict(send_result.delivery_paths),
    email_draft_path=email_draft_path,
    email_sent_path=email_sent_path,
    send_log_path=send_log_path,
    recipient_group=config.recipient_group,
    run_label=config.run_label,
  )
  save_weekly_job_log(result, out)
  return result


def save_weekly_job_log(result: WeeklyJobResult, output_dir: Path | str) -> dict[str, Path]:
  log_dir = Path(output_dir) / "job_logs"
  log_dir.mkdir(parents=True, exist_ok=True)
  pub = result.publication_number
  timestamp = result.created_at.replace(":", "").replace("+", "p")[:15]

  paths = {
    "job_log_json": log_dir / f"job_log_{timestamp}_{pub}.json",
    "job_log_latest": log_dir / f"job_log_latest_{pub}.json",
    "job_log_index": log_dir / "job_log_index.json",
  }

  payload = result.to_dict()
  encoded = json.dumps(payload, indent=2, ensure_ascii=False)
  paths["job_log_json"].write_text(encoded, encoding="utf-8")
  paths["job_log_latest"].write_text(encoded, encoding="utf-8")

  index_path = paths["job_log_index"]
  index: list[dict[str, Any]] = []
  if index_path.exists():
    try:
      data = json.loads(index_path.read_text(encoding="utf-8"))
      if isinstance(data, list):
        index = data
    except (OSError, json.JSONDecodeError):
      index = []
  index.append(payload)
  index_path.write_text(json.dumps(index[-50:], indent=2, ensure_ascii=False), encoding="utf-8")

  result.job_log_path = str(paths["job_log_latest"])
  return paths


def render_weekly_job_summary_md(result: WeeklyJobResult) -> str:
  lines = [
    f"# Weekly Digest Job: {result.publication_number}",
    "",
    f"- job_id: {result.job_id}",
    f"- created_at: {result.created_at}",
    f"- status: {result.status}",
    f"- message: {result.message}",
    f"- recipient_group: {result.recipient_group or '（なし）'}",
    f"- run_label: {result.run_label or '（なし）'}",
    "",
    "## パス",
    "",
    f"- email_draft_path: {result.email_draft_path or '（なし）'}",
    f"- email_sent_path: {result.email_sent_path or '（なし）'}",
    f"- send_log_path: {result.send_log_path or '（なし）'}",
    f"- job_log_path: {result.job_log_path or '（なし）'}",
    "",
    "## delivery_paths",
    "",
  ]
  if result.delivery_paths:
    for key, path in sorted(result.delivery_paths.items()):
      lines.append(f"- {key}: {path}")
  else:
    lines.append("- （なし）")
  return "\n".join(lines)
