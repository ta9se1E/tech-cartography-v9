"""Recipient configuration loader for manual test email (Phase 24.2)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def load_recipient_config(path: Path | str) -> dict[str, Any]:
  config_path = Path(path)
  if not config_path.exists():
    return {
      "_error": f"宛先設定ファイルが見つかりません: {config_path}",
      "_path": str(config_path),
    }
  try:
    data = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
      return {"_error": "宛先設定ファイルの形式が不正です（オブジェクトである必要があります）。"}
    return data
  except (OSError, json.JSONDecodeError) as exc:
    return {"_error": f"宛先設定ファイルの読み込みに失敗しました: {type(exc).__name__}"}


def get_recipient_group(config: dict[str, Any], group_name: str) -> dict[str, Any] | None:
  if config.get("_error"):
    return None
  group = config.get(str(group_name).strip())
  if not isinstance(group, dict):
    return None
  return group


def _normalize_email_list(values: object) -> list[str]:
  if not values:
    return []
  if isinstance(values, str):
    parts = [part.strip() for part in values.replace(";", ",").split(",")]
    return [part for part in parts if part]
  if isinstance(values, list):
    return [str(v).strip() for v in values if str(v).strip()]
  return []


def _is_valid_email(address: str) -> bool:
  return bool(_EMAIL_RE.match(str(address or "").strip()))


def validate_recipient_group(group: dict[str, Any]) -> tuple[bool, list[str]]:
  errors: list[str] = []
  if not group.get("enabled"):
    errors.append("recipient group は無効です（enabled=false）。送信前に enabled=true にしてください。")

  to_list = _normalize_email_list(group.get("to"))
  if not to_list:
    errors.append("宛先（to）が空です。少なくとも1件の宛先を設定してください。")

  for address in to_list:
    if not _is_valid_email(address):
      errors.append(f"宛先の形式が不正です: {address}")

  for address in _normalize_email_list(group.get("cc")):
    if not _is_valid_email(address):
      errors.append(f"CCの形式が不正です: {address}")

  return len(errors) == 0, errors


def resolve_recipients(
  config_path: Path | str,
  group_name: str,
) -> tuple[list[str], list[str], list[str]]:
  """Return (to, cc, errors). errors is empty when resolution succeeded."""
  config = load_recipient_config(config_path)
  if config.get("_error"):
    return [], [], [str(config["_error"])]

  group = get_recipient_group(config, group_name)
  if group is None:
    return [], [], [f"recipient group '{group_name}' が見つかりません。"]

  valid, errors = validate_recipient_group(group)
  if not valid:
    return [], [], errors

  to_list = _normalize_email_list(group.get("to"))
  cc_list = _normalize_email_list(group.get("cc"))
  return to_list, cc_list, []
