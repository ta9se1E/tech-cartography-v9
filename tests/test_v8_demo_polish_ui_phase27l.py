"""Tests for Phase27L demo polish UI modules."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"


def _read(rel: str) -> str:
  return (SRC / rel).read_text(encoding="utf-8")


def test_evidence_map_ui_phase27l() -> None:
  text = _read("tech_cartography/ui/v8_evidence_map_ui.py")
  assert "Evidence Mapの見方" in text
  assert "Evidence Map is not proof" in text
  assert "supporting evidence candidate" in text.lower()
  assert "manual_claim_count" in text
  assert "claim_text_required" in text
  assert "use_container_width" not in text


def test_gap_ui_phase27l() -> None:
  text = _read("tech_cartography/ui/v8_gap_next_actions_ui.py")
  assert "Gapの見方" in text
  assert "Gap is not invalidity" in text or "弱点ではなく" in text
  assert "Top 3 Next Actions" in text
  assert "Remaining Limitations" in text
  assert "use_container_width" not in text


def test_fixed_point_ui_phase27l() -> None:
  text = _read("tech_cartography/ui/v8_fixed_point_observation_ui.py")
  assert "定点観測で回る流れ" in text
  assert "no_email_send" in text
  assert "no_scheduler_start" in text
  assert "use_container_width" not in text


def test_export_ui_demo_polish_pack() -> None:
  text = _read("tech_cartography/ui/v8_export_ui.py")
  assert "Demo Polish Pack" in text
  assert "Generate Demo Polish Pack" in text
  assert "use_container_width" not in text


def test_intro_ui_demo_flow() -> None:
  text = _read("tech_cartography/ui/v8_intro_ui.py")
  assert "Phase27M" in text or "Phase27L" in text
  assert "デモ操作" in text
  assert "render_next_action_card" in text
  assert "use_container_width" not in text
