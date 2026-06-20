"""Tests for PAN precursor theme loader (Phase 24.5D)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.ui.analyst_mode_ui import (
  ANALYST_INPUT_KEY_PREFIX,
  PAN_PRECURSOR_THEME_PRESET,
  pan_theme_session_state_updates,
)
from tech_cartography.ui import theme_validation_ui

PROJECT_ROOT = Path(__file__).resolve().parent.parent
THEME_VALIDATION_UI = PROJECT_ROOT / "src" / "tech_cartography" / "ui" / "theme_validation_ui.py"


def test_pan_preset_has_required_fields() -> None:
  assert PAN_PRECURSOR_THEME_PRESET["theme_id"] == "pan_precursor_surface_internal_defects"
  assert PAN_PRECURSOR_THEME_PRESET["theme_name"] == "PAN系炭素繊維前駆体の表面・内部欠陥制御"
  assert PAN_PRECURSOR_THEME_PRESET["seed_publication_numbers"] == [
    "JP2022090764A",
    "JP2023163084A",
    "JP2018084002A",
  ]
  assert PAN_PRECURSOR_THEME_PRESET["core_keywords"]
  assert PAN_PRECURSOR_THEME_PRESET["application_keywords"]
  assert PAN_PRECURSOR_THEME_PRESET["material_process_keywords"]
  assert PAN_PRECURSOR_THEME_PRESET["exclude_keywords"]


def test_pan_theme_session_state_updates_restore_widgets() -> None:
  updates = pan_theme_session_state_updates(key_prefix=ANALYST_INPUT_KEY_PREFIX)
  assert updates[f"{ANALYST_INPUT_KEY_PREFIX}_theme_id"] == "pan_precursor_surface_internal_defects"
  assert updates[f"{ANALYST_INPUT_KEY_PREFIX}_theme_name"] == PAN_PRECURSOR_THEME_PRESET["theme_name"]
  assert "JP2022090764A" in updates[f"{ANALYST_INPUT_KEY_PREFIX}_seed_publications"]
  assert "JP2023163084A" in updates[f"{ANALYST_INPUT_KEY_PREFIX}_seed_publications"]
  assert "JP2018084002A" in updates[f"{ANALYST_INPUT_KEY_PREFIX}_seed_publications"]
  assert "PAN" in updates[f"{ANALYST_INPUT_KEY_PREFIX}_core_keywords"]


def test_ui_has_pan_theme_loader_button() -> None:
  text = THEME_VALIDATION_UI.read_text(encoding="utf-8")
  assert "PAN前駆体欠陥制御テーマを読み込む" in text
  assert "def render_pan_theme_loader_button" in text
  assert "pan_theme_session_state_updates" in text
