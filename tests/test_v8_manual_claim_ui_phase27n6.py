"""Tests for Phase27N.6 manual claim UI hotfix."""

from __future__ import annotations

import ast
from pathlib import Path

from tech_cartography.ui.v8_text_rendering import normalize_text_items, render_next_action_card

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLAIM_MAP_UI = PROJECT_ROOT / "src/tech_cartography/ui/v8_claim_map_ui.py"


def test_render_next_action_card_title_and_list() -> None:
  html = render_next_action_card(
    "次にやること",
    [
      "保存したclaim本文を使ってClaim Mapを再生成してください。",
      "次にEvidence Mapを再生成してください。",
    ],
  )
  assert "<b>次にやること</b>" in html
  assert "Claim Map" in html
  assert html.count("<li>") == 2


def test_render_next_action_card_str_not_split() -> None:
  text = "保存後はClaim Mapを再生成してください。"
  items = normalize_text_items(text)
  assert len(items) == 1
  html = render_next_action_card("次にやること", text)
  assert html.count("<li>") == 1
  assert "Claim Map" in html


def test_claim_map_ui_importable() -> None:
  import tech_cartography.ui.v8_claim_map_ui as claim_map_ui

  assert hasattr(claim_map_ui, "render_v8_claim_map_tab")


def test_claim_map_ui_render_next_action_card_has_two_args() -> None:
  text = CLAIM_MAP_UI.read_text(encoding="utf-8")
  assert 'render_next_action_card("次にやること"' in text or 'render_next_action_card(\n    "次にやること"' in text
  tree = ast.parse(text)
  bad_calls: list[str] = []
  for node in ast.walk(tree):
    if not isinstance(node, ast.Call):
      continue
    func = node.func
    if isinstance(func, ast.Name) and func.id == "render_next_action_card":
      positional = [a for a in node.args if not isinstance(a, ast.keyword)]
      if len(positional) < 2:
        bad_calls.append(f"line {node.lineno}: only {len(positional)} positional arg(s)")
  assert not bad_calls, "render_next_action_card missing next_actions:\n" + "\n".join(bad_calls)
  assert "use_container_width" not in text
  assert "UI骨格 Phase27B" not in text
