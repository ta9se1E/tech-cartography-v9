"""Tests for Phase 25Q.2 send safety docs."""

from __future__ import annotations

from pathlib import Path


def test_phase25q2_docs_cover_safety_reset() -> None:
  text = Path("docs/phase25q2_send_safety_reset.md").read_text(encoding="utf-8")
  assert "Phase 25Q.2" in text
  assert "safe_off" in text
  assert "controlled_manual_send_enabled" in text
  assert "risky_email_enabled" in text
  assert "misconfigured" in text
  assert "ENABLE_APPROVED_MEMBER_SEND=false" in text
  assert "DISABLE_EMAIL_SEND=true" in text
  assert "reset_required" in text
  assert "SMTP_PASSWORD" not in text or "扱わない" in text
  assert "一斉送信" in text
  assert "scheduler" in text.lower()
