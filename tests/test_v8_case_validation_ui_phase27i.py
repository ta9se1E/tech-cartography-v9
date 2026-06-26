"""Tests for v8 case validation UI (Phase 27I)."""

from __future__ import annotations

from pathlib import Path

import tech_cartography.ui.v8_export_ui as export_ui
import tech_cartography.ui.v8_intro_ui as intro_ui
import tech_cartography.ui.v8_admin_settings_ui as admin_ui


def test_export_ui_has_three_case_validation_section() -> None:
  text = Path(export_ui.__file__).read_text(encoding="utf-8")
  assert "3案件検証パック" in text
  assert "Generate Three Case Validation Pack" in text
  assert "readiness_for_demo" in text or "readiness" in text.lower()
  assert "common_blocking_issues" in text or "blocking" in text.lower()
  assert "use_container_width" not in text
  assert "SMTP_PASSWORD" not in text


def test_intro_ui_phase27i_guidance() -> None:
  text = Path(intro_ui.__file__).read_text(encoding="utf-8")
  assert "Phase27I" in text
  assert "3案件検証パック" in text
  assert "render_next_action_card" in text or "normalize_text_items" in text


def test_admin_settings_local_validation_notice() -> None:
  text = Path(admin_ui.__file__).read_text(encoding="utf-8")
  assert "Phase27I" in text
  assert "Cloud Build" in text or "Cloud Run" in text
  assert "SMTP_PASSWORD" not in text


def test_export_ui_importable() -> None:
  assert callable(export_ui.render_v8_export_tab)
