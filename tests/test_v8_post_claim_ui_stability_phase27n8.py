"""Tests for Phase27N.8 post-claim demo UI stability hotfix."""

from __future__ import annotations

from pathlib import Path

import pytest

import tech_cartography.ui.v8_export_ui as export_ui
from tech_cartography.services.v8_large_candidate_shortlist import (
  find_latest_large_shortlist_dir,
  find_latest_large_shortlist_dir_for_any_case,
  find_latest_large_shortlist_dirs_for_all_cases,
  get_large_shortlist_dir,
  safe_find_latest_large_shortlist_dir,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPORT_UI_PATH = PROJECT_ROOT / "src/tech_cartography/ui/v8_export_ui.py"


def test_v8_export_ui_importable() -> None:
  assert callable(export_ui.render_v8_export_tab)


def test_find_latest_large_shortlist_dir_none_does_not_crash(tmp_path: Path) -> None:
  assert find_latest_large_shortlist_dir(None, tmp_path) is None
  assert safe_find_latest_large_shortlist_dir(None, tmp_path) is None
  assert find_latest_large_shortlist_dir_for_any_case(tmp_path) is None
  assert find_latest_large_shortlist_dirs_for_all_cases(tmp_path) == []


def test_get_large_shortlist_dir_rejects_none() -> None:
  with pytest.raises(ValueError, match="case_id"):
    get_large_shortlist_dir(None)  # type: ignore[arg-type]
  with pytest.raises(ValueError, match="case_id"):
    get_large_shortlist_dir("")


def test_artifact_link_handles_none() -> None:
  export_ui._artifact_link(None)
  export_ui._artifact_link(None, label="large_shortlist")


def test_export_case_filter_helpers() -> None:
  assert export_ui._export_case_filter("all") is None
  assert export_ui._export_case_filter("case_01_pan_graphitization") == "case_01_pan_graphitization"
  assert export_ui._primary_case_id("all") == "case_01_pan_graphitization"
  assert export_ui._primary_case_id("case_02_sizing_interface") == "case_02_sizing_interface"


def test_export_ui_no_none_passed_to_get_large_shortlist_dir() -> None:
  text = EXPORT_UI_PATH.read_text(encoding="utf-8")
  assert "find_latest_large_shortlist_dir(None" not in text
  assert "get_large_shortlist_dir(None" not in text
  assert "safe_find_latest_large_shortlist_dir" in text
  assert "_export_case_filter" in text


def test_export_ui_artifact_missing_distinction() -> None:
  text = EXPORT_UI_PATH.read_text(encoding="utf-8")
  assert "artifact missing" in text or "artifact_missing" in text
  assert "true zero" in text or "true_zero" in text
  assert "（未生成）" in text


def test_export_ui_no_deprecated_patterns() -> None:
  text = EXPORT_UI_PATH.read_text(encoding="utf-8")
  assert "use_container_width" not in text
  assert "UI骨格 Phase27B" not in text
  assert "Cloud Build" not in text or "実行しません" in text
  assert "Cloud Run deploy" not in text or "実行しません" in text
