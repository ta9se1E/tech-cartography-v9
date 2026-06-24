"""Phase 25V docs tests."""

from __future__ import annotations

from pathlib import Path

DOCS = Path("docs/phase25v_evidence_gap_strategic_watch_brief.md")


def test_phase25v_docs() -> None:
  assert DOCS.is_file()
  text = DOCS.read_text(encoding="utf-8")
  for topic in ("Evidence Gap", "Strategic Watch Brief", "Deep Research", "候補", "禁止", "Run History"):
    assert topic in text
