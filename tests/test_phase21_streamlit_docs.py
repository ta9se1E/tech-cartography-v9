"""Tests for Phase 21 Streamlit state documentation."""

from __future__ import annotations

from pathlib import Path


def test_phase21_streamlit_state_keys_doc_exists() -> None:
  path = Path("docs/phase21_streamlit_state_keys.md")
  assert path.exists()
  text = path.read_text(encoding="utf-8")
  assert "WIDGET_SELECTED_RUN_ID" in text
  assert "STATE_SELECTED_RUN_ID" in text
  assert "STATE_PENDING_SELECTED_RUN_ID" in text
  assert "直接変更しない" in text


def test_phase21_ui_checklist_exists() -> None:
  path = Path("docs/phase21_ui_state_patch_checklist.md")
  assert path.exists()
  text = path.read_text(encoding="utf-8")
  assert "streamlit run app.py" in text
  assert "latest_run" in text
  assert "7タブ" in text
