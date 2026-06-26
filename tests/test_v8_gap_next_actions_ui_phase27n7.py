"""Tests for Phase27N.7 Gap / Next Actions refresh cache hotfix."""

from __future__ import annotations

import ast
from pathlib import Path

import tech_cartography.ui.v8_gap_next_actions_ui as gap_ui

GAP_UI_PATH = Path(gap_ui.__file__)


def test_gap_ui_importable() -> None:
  assert callable(gap_ui.render_v8_gap_next_actions_tab)


def test_render_single_report_defines_refresh_cached_before_use() -> None:
  text = GAP_UI_PATH.read_text(encoding="utf-8")
  tree = ast.parse(text)
  func = next(
    n for n in ast.walk(tree)
    if isinstance(n, ast.FunctionDef) and n.name == "_render_single_report"
  )
  assigns_before_use: list[int] = []
  refresh_use_lines: list[int] = []
  for node in ast.walk(func):
    if isinstance(node, ast.Name) and node.id == "refresh_cached":
      if isinstance(getattr(node, "ctx", None), ast.Store):
        assigns_before_use.append(node.lineno)
      elif isinstance(getattr(node, "ctx", None), ast.Load):
        refresh_use_lines.append(node.lineno)
  assert assigns_before_use, "_render_single_report must assign refresh_cached"
  if refresh_use_lines:
    assert min(assigns_before_use) < min(refresh_use_lines)


def test_refresh_cached_session_state_lookup() -> None:
  text = GAP_UI_PATH.read_text(encoding="utf-8")
  assert 'st.session_state.get("v8_manual_claim_refresh_result")' in text
  assert "refresh_cached = st.session_state" in text


def test_artifact_missing_distinction_preserved() -> None:
  text = GAP_UI_PATH.read_text(encoding="utf-8")
  assert "artifact missing" in text
  assert "true zero" in text


def test_gap_not_invalidity_notice_preserved() -> None:
  text = GAP_UI_PATH.read_text(encoding="utf-8")
  assert "Gap is not invalidity" in text or "弱点" in text
  assert "FTO" in text
  assert "use_container_width" not in text
  assert "UI骨格 Phase27B" not in text


def test_manual_refresh_missing_caption() -> None:
  text = GAP_UI_PATH.read_text(encoding="utf-8")
  assert "Manual Claim Refresh" in text
