"""Tests for Phase27M demo flow UI modules."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"


def _read(rel: str) -> str:
  return (SRC / rel).read_text(encoding="utf-8")


def test_demo_flow_ui_phase27m() -> None:
  text = _read("tech_cartography/ui/v8_demo_flow_ui.py")
  assert "render_demo_flow_banner" in text
  assert "artifact missing" in text
  assert "normalize_text_items" not in text or "render_next_action_card" in text
  assert "use_container_width" not in text


def test_intro_shortest_demo_flow() -> None:
  text = _read("tech_cartography/ui/v8_intro_ui.py")
  assert "最短デモ操作" in text
  assert "Phase27M" in text
  assert "artifact missing" in text.lower() or "未生成" in text
  assert "render_next_action_card" in text


def test_tab_config_phase27m() -> None:
  text = _read("tech_cartography/ui/v8_tab_config.py")
  assert "Phase27M" in text


def test_input_first_step() -> None:
  text = _read("tech_cartography/ui/v8_input_ui.py")
  assert "まずここから" in text


def test_export_demo_readiness_pack() -> None:
  text = _read("tech_cartography/ui/v8_export_ui.py")
  assert "Demo Readiness Pack" in text
  assert "Generate Demo Readiness Pack" in text
