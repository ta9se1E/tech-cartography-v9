"""Tests for recipient config (Phase 24.2)."""

from __future__ import annotations

import json
from pathlib import Path

from tech_cartography.delivery.recipient_config import (
  get_recipient_group,
  load_recipient_config,
  resolve_recipients,
  validate_recipient_group,
)


def test_load_recipient_config_missing_file(tmp_path: Path) -> None:
  config = load_recipient_config(tmp_path / "missing.json")
  assert "_error" in config


def test_resolve_recipients_disabled_group(tmp_path: Path) -> None:
  path = tmp_path / "recipients.json"
  path.write_text(
    json.dumps(
      {
        "default": {
          "to": ["reviewer@example.com"],
          "cc": [],
          "enabled": False,
        },
      },
    ),
    encoding="utf-8",
  )
  to_list, cc_list, errors = resolve_recipients(path, "default")
  assert to_list == []
  assert cc_list == []
  assert errors
  assert any("enabled=false" in err for err in errors)


def test_resolve_recipients_empty_to(tmp_path: Path) -> None:
  path = tmp_path / "recipients.json"
  path.write_text(
    json.dumps({"default": {"to": [], "cc": [], "enabled": True}}),
    encoding="utf-8",
  )
  _, _, errors = resolve_recipients(path, "default")
  assert errors
  assert any("空" in err for err in errors)


def test_resolve_recipients_invalid_email(tmp_path: Path) -> None:
  path = tmp_path / "recipients.json"
  path.write_text(
    json.dumps({"default": {"to": ["not-an-email"], "cc": [], "enabled": True}}),
    encoding="utf-8",
  )
  _, _, errors = resolve_recipients(path, "default")
  assert errors
  assert any("形式が不正" in err for err in errors)


def test_resolve_recipients_valid_group(tmp_path: Path) -> None:
  path = tmp_path / "recipients.json"
  path.write_text(
    json.dumps(
      {
        "internal_review": {
          "to": ["reviewer@example.com"],
          "cc": ["cc@example.com"],
          "enabled": True,
        },
      },
    ),
    encoding="utf-8",
  )
  to_list, cc_list, errors = resolve_recipients(path, "internal_review")
  assert errors == []
  assert to_list == ["reviewer@example.com"]
  assert cc_list == ["cc@example.com"]


def test_get_recipient_group_missing() -> None:
  assert get_recipient_group({"default": {"enabled": True}}, "missing") is None
