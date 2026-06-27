"""Regression tests for Phase27N.8 UI defensive rendering."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

from tech_cartography.ui.v8_text_rendering import normalize_text_items, render_next_action_card

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPORT_UI_PATH = PROJECT_ROOT / "src/tech_cartography/ui/v8_export_ui.py"
GAP_UI_PATH = PROJECT_ROOT / "src/tech_cartography/ui/v8_gap_next_actions_ui.py"
CLAIM_MAP_UI_PATH = PROJECT_ROOT / "src/tech_cartography/ui/v8_claim_map_ui.py"

UI_MODULES = (
  "tech_cartography.ui.v8_intro_ui",
  "tech_cartography.ui.v8_input_ui",
  "tech_cartography.ui.v8_sources_ui",
  "tech_cartography.ui.v8_patent_shortlist_ui",
  "tech_cartography.ui.v8_claim_map_ui",
  "tech_cartography.ui.v8_evidence_map_ui",
  "tech_cartography.ui.v8_gap_next_actions_ui",
  "tech_cartography.ui.v8_fixed_point_observation_ui",
  "tech_cartography.ui.v8_export_ui",
  "tech_cartography.ui.v8_admin_settings_ui",
)


def test_render_next_action_card_correct_args() -> None:
  html = render_next_action_card("次にやること", ["Claim Map を再生成", "Evidence Map を確認"])
  assert "<b>次にやること</b>" in html
  assert html.count("<li>") == 2


def test_render_next_action_card_str_not_char_split() -> None:
  text = "保存後はClaim Mapを再生成してください。"
  assert len(normalize_text_items(text)) == 1
  html = render_next_action_card("次にやること", text)
  assert html.count("<li>") == 1
  assert "Claim Map" in html


def test_claim_map_ui_render_next_action_card_two_args() -> None:
  text = CLAIM_MAP_UI_PATH.read_text(encoding="utf-8")
  tree = ast.parse(text)
  bad_calls: list[str] = []
  for node in ast.walk(tree):
    if not isinstance(node, ast.Call):
      continue
    func = node.func
    if isinstance(func, ast.Name) and func.id == "render_next_action_card":
      positional = [a for a in node.args if not isinstance(a, ast.keyword)]
      if len(positional) < 2:
        bad_calls.append(f"line {node.lineno}")
  assert not bad_calls


def test_gap_ui_refresh_cached_defined_before_use() -> None:
  text = GAP_UI_PATH.read_text(encoding="utf-8")
  assert "refresh_cached = st.session_state" in text
  tree = ast.parse(text)
  func = next(
    n for n in ast.walk(tree)
    if isinstance(n, ast.FunctionDef) and n.name == "_render_single_report"
  )
  assign_lines = [
    node.lineno for node in ast.walk(func)
    if isinstance(node, ast.Name) and node.id == "refresh_cached" and isinstance(node.ctx, ast.Store)
  ]
  use_lines = [
    node.lineno for node in ast.walk(func)
    if isinstance(node, ast.Name) and node.id == "refresh_cached" and isinstance(node.ctx, ast.Load)
  ]
  assert assign_lines
  if use_lines:
    assert min(assign_lines) < min(use_lines)


def test_export_ui_no_case_id_none_in_path_builders() -> None:
  text = EXPORT_UI_PATH.read_text(encoding="utf-8")
  assert "find_latest_large_shortlist_dir(None" not in text
  assert "get_large_shortlist_dir(None" not in text
  assert "find_latest_large_shortlist_dir(_export_case_filter" in text or "safe_find_latest_large_shortlist_dir" in text


@pytest.mark.parametrize("module_name", UI_MODULES)
def test_main_ui_modules_importable(module_name: str) -> None:
  mod = importlib.import_module(module_name)
  assert mod is not None
