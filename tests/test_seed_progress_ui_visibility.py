"""UI visibility tests for seed validation progress dashboard (Phase 24.4A.4.1)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.ui import theme_validation_ui
from tech_cartography.validation.seed_progress import inspect_seed_progress_many, progress_to_display_dataframe
from tech_cartography.validation.theme_validation import ThemeValidationCase, parse_keyword_text


def test_ui_source_has_seed_progress_section() -> None:
  text = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  assert "Seed別 検証進捗 / Seed Validation Progress" in text
  assert "Seed進捗を更新する" in text
  assert "Seed進捗レポートを保存する" in text
  assert "seed publication numbersを入力してください" in text
  assert "theme_validation_seed_progress" in text


def test_seed_progress_dashboard_before_theme_name_gate() -> None:
  text = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  section = text.split("def render_theme_validation_section", 1)[1]
  seed_idx = section.index("seed publication numbers（カンマ区切り")
  progress_idx = section.index("progress_list = render_seed_progress_dashboard")
  theme_gate_idx = section.index("if not theme_name.strip():")
  assert seed_idx < progress_idx < theme_gate_idx


def test_buttons_not_hidden_by_empty_seed_early_return() -> None:
  text = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  dashboard = text.split("def render_seed_progress_dashboard", 1)[1].split("def _default_publication_with_manual_claims", 1)[0]
  update_idx = dashboard.index("Seed進捗を更新する")
  save_idx = dashboard.index("Seed進捗レポートを保存する")
  empty_seed_idx = dashboard.index("if not seeds:")
  assert update_idx < empty_seed_idx
  assert save_idx < empty_seed_idx


def test_progress_table_generation_with_seeds(tmp_path: Path) -> None:
  items = inspect_seed_progress_many(
    ["JP2022090764A", "JP2023163084A"],
    tmp_path,
  )
  df = progress_to_display_dataframe(items)
  assert len(df) == 2
  assert "next_action" in df.columns


def test_manual_claims_editor_selectbox_lists_all_seeds() -> None:
  text = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  editor = text.split("def render_manual_claims_editor", 1)[1].split("def _show_stage_delta", 1)[0]
  assert 'options=seeds' in editor
  assert "default_index" in editor


def test_evidence_map_builder_selectbox_lists_all_seeds() -> None:
  text = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  builder = text.split("def render_evidence_map_builder", 1)[1].split("def render_theme_validation_intro_card", 1)[0]
  assert 'options=seeds' in builder
  assert "default_index" in builder


def test_next_action_headings_present() -> None:
  text = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  assert "### 次にやること" in text
  assert "### 完了済みseed" in text


def test_render_seed_progress_dashboard_callable() -> None:
  assert callable(theme_validation_ui.render_seed_progress_dashboard)


def test_parse_three_jp_seeds() -> None:
  seeds = parse_keyword_text("JP2022090764A, JP2023163084A, JP2018084002A")
  assert seeds == ["JP2022090764A", "JP2023163084A", "JP2018084002A"]


def test_ui_has_no_automatic_external_api_in_seed_progress() -> None:
  text = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  progress_block = text.split("def render_seed_progress_dashboard", 1)[1].split("def _default_publication", 1)[0]
  assert "openalex" not in progress_block.lower()
  assert "tavily" not in progress_block.lower()
  assert "bigquery" not in progress_block.lower()
