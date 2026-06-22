"""Safety tests for approved member send (Phase 25Q)."""

from __future__ import annotations

import re
from pathlib import Path


def test_cloudbuild_defaults_safe() -> None:
  text = Path("cloudbuild.yaml").read_text(encoding="utf-8")
  assert "ENABLE_APPROVED_MEMBER_SEND=false" in text
  assert "DISABLE_EMAIL_SEND=true" in text
  assert "DISABLE_SCHEDULER=true" in text
  assert "TECH_CARTOGRAPHY_APPROVED_MEMBER_EMAILS=" not in text
  assert "SMTP_PASSWORD=" not in text or "tech-cartography-smtp-password" in text


def test_deploy_script_defaults_safe() -> None:
  text = Path("scripts/deploy_live_safe.sh").read_text(encoding="utf-8")
  assert "ENABLE_APPROVED_MEMBER_SEND=false" in text
  assert "DISABLE_EMAIL_SEND=true" in text
  assert "TECH_CARTOGRAPHY_APPROVED_MEMBER_EMAILS=" not in text


def test_sender_and_config_do_not_print_secrets() -> None:
  sender = Path("src/tech_cartography/services/live_approved_member_email_sender.py").read_text(encoding="utf-8")
  config = Path("src/tech_cartography/runtime/approved_member_send_config.py").read_text(encoding="utf-8")
  ui = Path("src/tech_cartography/ui/live_approved_member_email_send_ui.py").read_text(encoding="utf-8")
  for text in (sender, config, ui):
    assert "print(" not in text or "SMTP_PASSWORD" not in text
    assert not re.search(r"os\.environ\[.SMTP_PASSWORD", text)


def test_no_scheduler_enable_in_deploy_files() -> None:
  cloudbuild = Path("cloudbuild.yaml").read_text(encoding="utf-8")
  deploy = Path("scripts/deploy_live_safe.sh").read_text(encoding="utf-8")
  assert not re.search(r"DISABLE_SCHEDULER\s*=\s*false", cloudbuild)
  assert not re.search(r"DISABLE_SCHEDULER\s*=\s*false", deploy)
