"""Phase27Q.1 structured theme / BigQuery UI tests."""

from __future__ import annotations

from pathlib import Path

import tech_cartography.ui.v8_input_ui as input_ui
import tech_cartography.ui.v8_research_theme_ui as theme_ui
import tech_cartography.ui.v8_bigquery_admin_ui as bq_ui


def test_input_ui_has_theme_section() -> None:
  text = Path(input_ui.__file__).read_text(encoding="utf-8")
  assert "render_research_theme_section" in text
  assert "render_bigquery_admin_section" in text


def test_theme_ui_importable() -> None:
  assert callable(theme_ui.render_research_theme_section)


def test_bigquery_ui_safety_caption() -> None:
  text = Path(bq_ui.__file__).read_text(encoding="utf-8")
  input_text = Path(input_ui.__file__).read_text(encoding="utf-8")
  theme_text = Path(theme_ui.__file__).read_text(encoding="utf-8")
  assert "ENABLE_BIGQUERY_RUN" in text
  assert "公開デモ" in text
  assert "claim 本文" in text
  assert "use_container_width" not in text
  assert "render_bigquery_admin_section" in input_text
  assert "BigQuery" in theme_text and "直接実行しません" in theme_text
