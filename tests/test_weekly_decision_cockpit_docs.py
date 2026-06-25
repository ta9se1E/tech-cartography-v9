"""Phase 25W docs tests."""

from __future__ import annotations

from pathlib import Path

DOCS = Path("docs/phase25w_weekly_decision_cockpit.md")


def test_docs_cover_topics() -> None:
  assert DOCS.is_file()
  text = DOCS.read_text(encoding="utf-8")
  for topic in ("Weekly Decision Cockpit", "Deep Research", "Evidence Gap", "Run History", "禁止"):
    assert topic in text
