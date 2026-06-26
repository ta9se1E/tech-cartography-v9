"""Tests for v8 manual claim UI (Phase 27J)."""

from __future__ import annotations

from pathlib import Path

import tech_cartography.ui.v8_claim_map_ui as claim_ui
import tech_cartography.ui.v8_evidence_map_ui as evidence_ui
import tech_cartography.ui.v8_export_ui as export_ui
import tech_cartography.ui.v8_gap_next_actions_ui as gap_ui
import tech_cartography.ui.v8_fixed_point_observation_ui as fp_ui


def test_claim_map_ui_manual_injection_section() -> None:
  text = Path(claim_ui.__file__).read_text(encoding="utf-8")
  assert "手動投入" in text or "manual" in text.lower()
  assert "claims_input.csvへ保存" in text
  assert "生成しません" in text
  assert "use_container_width" not in text
  assert "SMTP_PASSWORD" not in text


def test_evidence_map_ui_post_injection_hints() -> None:
  text = Path(evidence_ui.__file__).read_text(encoding="utf-8")
  assert "manual_input" in text or "claim投入後" in text
  assert "candidate" in text.lower() or "候補" in text


def test_export_ui_manual_claim_refresh_pack() -> None:
  text = Path(export_ui.__file__).read_text(encoding="utf-8")
  assert "Manual Claim Refresh Pack" in text
  assert "manual_claim_refresh" in text


def test_gap_and_fixed_point_ui_phase27j() -> None:
  gap_text = Path(gap_ui.__file__).read_text(encoding="utf-8")
  fp_text = Path(fp_ui.__file__).read_text(encoding="utf-8")
  assert "claim投入後" in gap_text or "Phase27J" in gap_text
  assert "次回タスク" in fp_text or "Phase27J" in fp_text


def test_claim_map_ui_importable() -> None:
  assert callable(claim_ui.render_v8_claim_map_tab)
