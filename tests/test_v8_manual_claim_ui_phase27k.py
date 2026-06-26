"""UI tests for v8 manual claim injection (Phase 27K)."""

from __future__ import annotations

from pathlib import Path


def test_claim_map_ui_manual_injection_phase27k() -> None:
  text = Path("src/tech_cartography/ui/v8_claim_map_ui.py").read_text(encoding="utf-8")
  for token in (
    "Phase27K",
    "claims_input.csvへ保存",
    "Manual Claim Refresh Pack",
    "Top5",
    "backup_path",
    "claim_source_type",
  ):
    assert token in text
  assert "use_container_width" not in text


def test_evidence_map_ui_manual_claim_status() -> None:
  text = Path("src/tech_cartography/ui/v8_evidence_map_ui.py").read_text(encoding="utf-8")
  assert "manual_input" in text or "loaded" in text
  assert "claim_text_required" in text
  assert "use_container_width" not in text


def test_gap_ui_claim_injection_change() -> None:
  text = Path("src/tech_cartography/ui/v8_gap_next_actions_ui.py").read_text(encoding="utf-8")
  assert "claim投入後" in text or "claim_text_required" in text
  assert "use_container_width" not in text


def test_export_ui_manual_claim_refresh_pack() -> None:
  text = Path("src/tech_cartography/ui/v8_export_ui.py").read_text(encoding="utf-8")
  assert "Manual Claim Refresh Pack" in text
  assert "claim_text_required_count" in text
  assert "use_container_width" not in text
