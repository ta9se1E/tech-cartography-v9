"""Tests for Phase27R.3 executive summary UI helpers."""

from __future__ import annotations

from pathlib import Path

import tech_cartography.ui.v8_executive_summary_ui as exec_ui

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"


def _read(rel: str) -> str:
  return (SRC / rel).read_text(encoding="utf-8")


def test_executive_summary_module_copy() -> None:
  assert "裏取り候補" in exec_ui.EVIDENCE_EXECUTIVE_TEMPLATE
  assert "未確認事項" in exec_ui.GAP_EXECUTIVE_TEMPLATE
  assert "定点観測" in exec_ui.WATCH_EXECUTIVE_SUMMARY or "人手承認" in exec_ui.WATCH_EXECUTIVE_SUMMARY
  assert "共有資料" in exec_ui.EXPORT_EXECUTIVE_SUMMARY or "研究チーム" in exec_ui.EXPORT_EXECUTIVE_SUMMARY
  assert callable(exec_ui.render_evidence_executive_summary)
  assert callable(exec_ui.render_gap_executive_summary)
  assert callable(exec_ui.render_watch_executive_summary)
  assert callable(exec_ui.render_export_executive_summary)


def test_ui_tabs_import_executive_summary() -> None:
  evidence = _read("tech_cartography/ui/v8_evidence_map_ui.py")
  gap = _read("tech_cartography/ui/v8_gap_next_actions_ui.py")
  fp = _read("tech_cartography/ui/v8_fixed_point_observation_ui.py")
  export = _read("tech_cartography/ui/v8_export_ui.py")
  assert "render_evidence_executive_summary" in evidence
  assert "render_gap_executive_summary" in gap
  assert "render_watch_executive_summary" in fp
  assert "render_export_executive_summary" in export
  assert "デモではOFF" in fp
  assert "export dir（開発者向け）" in evidence
  assert "export dir（開発者向け）" in gap
