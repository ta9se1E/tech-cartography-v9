"""Docs checks for Phase 25T controlled web signal collection."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS = PROJECT_ROOT / "docs/phase25t_controlled_web_signal_collection.md"


def test_phase25t_docs_cover_required_topics() -> None:
  assert DOCS.is_file()
  text = DOCS.read_text(encoding="utf-8")
  for topic in (
    "Phase 25T",
    "active Watch Profile",
    "DISABLE_EXTERNAL_API",
    "ENABLE_MANUAL_WEB_SIGNAL_COLLECTION",
    "COLLECT WEB SIGNALS",
    "候補",
    "Run History",
    "Scheduler",
    "メール",
    "禁止",
  ):
    assert topic in text
