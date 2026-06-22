"""Tests for Phase 25Q documentation."""

from __future__ import annotations

from pathlib import Path


def test_phase25q_docs_exist_and_cover_safety() -> None:
  text = Path("docs/phase25q_approved_member_send.md").read_text(encoding="utf-8")
  assert "Phase 25Q" in text
  assert "self-only" in text.lower() or "self_only" in text
  assert "ENABLE_APPROVED_MEMBER_SEND" in text
  assert "SEND TO APPROVED MEMBER" in text
  assert "approved@example.com" in text
  assert "一斉送信" in text
  assert "scheduler" in text.lower()
  assert "--update-env-vars" in text
  assert "outputs/live_approved_member_send" in text
