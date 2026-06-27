"""Tests for Phase27N Cloud Run readiness UI modules."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"


def _read(rel: str) -> str:
  return (SRC / rel).read_text(encoding="utf-8")


def test_export_ui_cloud_run_readiness_pack() -> None:
  text = _read("tech_cartography/ui/v8_export_ui.py")
  assert "Cloud Run Readiness Pack" in text
  assert "Generate Cloud Run Readiness Pack" in text
  assert "use_container_width" not in text


def test_admin_ui_cloud_run_readiness() -> None:
  text = _read("tech_cartography/ui/v8_admin_settings_ui.py")
  assert "Cloud Run" in text
  assert "readiness" in text.lower()
  assert "DISABLE_EMAIL_SEND" in text or "DISABLE_SCHEDULER" in text
  assert "use_container_width" not in text


def test_intro_ui_phase27n() -> None:
  text = _read("tech_cartography/ui/v8_intro_ui.py")
  assert "Phase27N" in text or "Cloud Run Readiness" in text or "render_judge_conclusion_card" in text
  assert "deploy" in text.lower() or "Cloud Run" in text
  assert "render_next_action_card" in text or "render_judge_three_minute_guide" in text
  assert "use_container_width" not in text


def test_tab_config_phase27n() -> None:
  text = _read("tech_cartography/ui/v8_tab_config.py")
  assert (
    "Phase27N" in text
    or "Phase27Q.1" in text
    or "Phase27Q.3" in text
    or "Judge Mode" in text
  )
  assert "UI骨格 Phase27B" not in text


def test_demo_safe_ui_phase27n_sidebar() -> None:
  text = _read("tech_cartography/ui/demo_safe_ui.py")
  assert (
    "Phase27N" in text
    or "Phase27Q.3" in text
    or "Submission Demo" in text
    or "render_judge_mode_sidebar" in text
    or "Judge Mode" in text
  )
  assert "use_container_width" not in text
