"""Docs checks for Phase 25S Watch Profile management."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS = PROJECT_ROOT / "docs/phase25s_watch_profile_management.md"


def test_phase25s_docs_exist_and_cover_topics() -> None:
  assert DOCS.is_file()
  text = DOCS.read_text(encoding="utf-8")
  for topic in (
    "Watch Profile",
    "draft",
    "active",
    "archive",
    "ACTIVATE WATCH PROFILE",
    "Scheduler dry-run",
    "Digest Preview",
    "Run History",
    "ENABLE_WATCH_PROFILE_MANAGEMENT",
    "外部 API",
    "メール送信",
    "Scheduler",
  ):
    assert topic in text
