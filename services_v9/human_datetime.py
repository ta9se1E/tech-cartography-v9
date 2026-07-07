"""Human-facing datetime formatting for Study Demo."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")


def parse_datetime(value: Any) -> datetime | None:
  text = str(value or "").strip()
  if not text or text in {"—", "-", "null", "None"}:
    return None
  normalized = text.replace("Z", "+00:00")
  try:
    parsed = datetime.fromisoformat(normalized)
  except ValueError:
    return None
  if parsed.tzinfo is None:
    parsed = parsed.replace(tzinfo=timezone.utc)
  return parsed


def format_datetime_jst(value: Any, *, with_seconds: bool = False) -> str:
  parsed = parse_datetime(value)
  if not parsed:
    return "日時未記録"
  local = parsed.astimezone(JST)
  if with_seconds:
    return local.strftime("%Y/%m/%d %H:%M:%S JST")
  return local.strftime("%Y/%m/%d %H:%M JST")


def format_date_jst(value: Any) -> str:
  parsed = parse_datetime(value)
  if not parsed:
    return "日時未記録"
  return parsed.astimezone(JST).strftime("%Y/%m/%d")


def format_relative_date_if_needed(value: Any) -> str:
  return format_datetime_jst(value)


__all__ = [
  "format_date_jst",
  "format_datetime_jst",
  "format_relative_date_if_needed",
  "parse_datetime",
]
