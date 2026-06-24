"""Docs checks for Phase 25U."""

from __future__ import annotations

from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs/phase25u_web_signal_digest_integration.md"


def test_phase25u_docs_cover_topics() -> None:
  assert DOCS.is_file()
  text = DOCS.read_text(encoding="utf-8")
  for topic in (
    "Phase 25U",
    "Phase 25T",
    "候補情報",
    "Digest Preview",
    "Run History",
    "禁止",
    "FTO",
  ):
    assert topic in text
