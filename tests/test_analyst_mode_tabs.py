"""Tab routing tests for analyst mode (Phase 24.5D)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.ui import demo_safe_ui, v7_easy_app

PROJECT_ROOT = Path(__file__).resolve().parent.parent
V7_EASY_APP = PROJECT_ROOT / "src" / "tech_cartography" / "ui" / "v7_easy_app.py"
DEMO_SAFE_UI = PROJECT_ROOT / "src" / "tech_cartography" / "ui" / "demo_safe_ui.py"


def test_analyst_tab_order_matches_demo_style() -> None:
  analyst_ids = demo_safe_ui.ANALYST_TAB_IDS
  demo_ids = demo_safe_ui.DEMO_TAB_IDS
  assert analyst_ids == (
    "analyst_input",
    "start",
    "evidence",
    "market",
    "reports",
    "settings",
  )
  assert analyst_ids[1:] == ("start", "evidence", "market", "reports", "settings")
  assert set(analyst_ids) - set(demo_ids) == {"analyst_input"}
  assert "patents" not in analyst_ids
  assert "fulltext" not in analyst_ids
  assert "theme_validation" not in analyst_ids


def test_analyst_tab_labels() -> None:
  labels = demo_safe_ui.tab_labels_for_ui_mode(demo_safe_ui.UI_MODE_ANALYST)
  assert labels == [
    "入力・実行",
    "はじめる",
    "技術の裏取り",
    "企業・市場シグナル",
    "レポート",
    "設定",
  ]


def test_hidden_tabs_not_in_analyst_routing() -> None:
  text = V7_EASY_APP.read_text(encoding="utf-8")
  render_section = text.split("def _render_tab_by_id", 1)[1].split("def render_tabbed_easy_app", 1)[0]
  assert 'tab_id == "patents"' in render_section
  assert 'tab_id == "analyst_input"' in render_section
  assert demo_safe_ui.tab_ids_for_ui_mode(demo_safe_ui.UI_MODE_ANALYST).count("patents") == 0


def test_analyst_input_contains_manual_claims_and_e2e_sections() -> None:
  text = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  section = text.split("def render_analyst_input_execution_section", 1)[1].split(
    "def render_theme_validation_section",
    1,
  )[0]
  assert "render_manual_claims_editor" in section
  assert "render_evidence_map_builder" in section
  assert "render_end_to_end_chain_section" in section
  assert "render_final_validation_builder" in section


def test_demo_tab_labels_unchanged() -> None:
  labels = v7_easy_app._main_tab_labels(ui_mode="demo")
  assert labels == ["はじめる", "技術の裏取り", "企業・市場シグナル", "レポート", "設定"]
