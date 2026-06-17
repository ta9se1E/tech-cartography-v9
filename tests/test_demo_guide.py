"""Tests for Phase 21 demo guide."""

from __future__ import annotations

from pathlib import Path


def test_demo_guide_exists() -> None:
  path = Path("docs/demo_guide_phase21.md")
  assert path.exists()


def test_demo_guide_has_startup_instructions() -> None:
  text = Path("docs/demo_guide_phase21.md").read_text(encoding="utf-8")
  assert "streamlit run app.py" in text
  assert "起動" in text


def test_demo_guide_has_caveats() -> None:
  text = Path("docs/demo_guide_phase21.md").read_text(encoding="utf-8")
  assert "supporting evidence candidate" in text.lower() or "証明ではない" in text
  assert "FTO" in text or "侵害" in text
  assert "専門家レビュー" in text
