"""Tests for Reproducibility Smoke Run UI loader and display helpers (Phase 22.1)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from tech_cartography.ui.reproducibility_smoke_ui import (
  MANUAL_CHECKLIST_NOTICE,
  ONE_OFF_ANSWER_BODY,
  REPRODUCIBILITY_CAUTION,
  ReproducibilitySmokeArtifacts,
  get_reproducibility_status_counts,
  load_reproducibility_smoke_artifacts,
  prepare_reproducibility_summary_display_df,
  render_one_off_answer_card_html,
  render_reproducibility_brief_card_html,
  safe_read_csv,
  safe_read_json,
  safe_read_text,
)


def _write_smoke_outputs(root: Path) -> None:
  smoke_dir = root / "outputs/reproducibility_smoke"
  smoke_dir.mkdir(parents=True, exist_ok=True)
  rows = [
    {
      "publication_number": "US-12565719-B2",
      "title": "Demo patent",
      "status": "complete_existing_demo",
      "retrieval_route": "manual_route_required",
      "manual_input_exists": True,
      "evidence_map_exists": True,
    },
    {
      "publication_number": "US-12435451-B2",
      "title": "",
      "status": "blocked_missing_manual_claims",
      "retrieval_route": "manual_route_required",
      "manual_input_exists": False,
      "evidence_map_exists": False,
    },
    {
      "publication_number": "US-12516451-B2",
      "status": "blocked_missing_manual_claims",
      "retrieval_route": "manual_route_required",
    },
  ]
  csv_path = smoke_dir / "reproducibility_summary.csv"
  pd.DataFrame(rows).to_csv(csv_path, index=False)
  (smoke_dir / "reproducibility_summary.json").write_text(
    json.dumps({"summary": rows, "dry_run": False}),
    encoding="utf-8",
  )
  (smoke_dir / "reproducibility_summary.md").write_text("# Phase22\n", encoding="utf-8")
  (smoke_dir / "next_manual_claims_checklist.md").write_text(
    "# checklist\nimport_manual_fulltext.py\n",
    encoding="utf-8",
  )


def test_safe_read_text_missing(tmp_path: Path) -> None:
  text, err = safe_read_text(tmp_path / "missing.md")
  assert text is None
  assert "not found" in err


def test_safe_read_json_broken(tmp_path: Path) -> None:
  bad = tmp_path / "bad.json"
  bad.write_text("{broken", encoding="utf-8")
  data, err = safe_read_json(bad)
  assert data is None
  assert "json parse error" in err


def test_loader_missing_files_does_not_raise(tmp_path: Path) -> None:
  artifacts = load_reproducibility_smoke_artifacts(tmp_path)
  assert isinstance(artifacts, ReproducibilitySmokeArtifacts)
  assert artifacts.status in {"missing", "partial", "error"}
  assert artifacts.summary_df.empty


def test_loader_reads_smoke_outputs(tmp_path: Path) -> None:
  _write_smoke_outputs(tmp_path)
  artifacts = load_reproducibility_smoke_artifacts(tmp_path)
  assert artifacts.status == "ready"
  assert len(artifacts.summary_df) == 3
  assert artifacts.summary_md is not None
  assert artifacts.manual_claims_checklist_md is not None


def test_prepare_display_df_fills_missing_columns_and_nan() -> None:
  df = pd.DataFrame(
    [
      {
        "publication_number": "US-12435451-B2",
        "title": None,
        "status": "blocked_missing_manual_claims",
      },
    ],
  )
  display = prepare_reproducibility_summary_display_df(df)
  assert display.iloc[0]["title"] == "not available"
  assert display.iloc[0]["assignee"] == "not available"
  assert "publication_number" in display.columns


def test_prepare_display_empty_df() -> None:
  display = prepare_reproducibility_summary_display_df(pd.DataFrame())
  assert display.empty
  assert list(display.columns)


def test_status_counts() -> None:
  df = pd.DataFrame(
    [
      {"status": "complete_existing_demo"},
      {"status": "blocked_missing_manual_claims"},
      {"status": "manual_route_required"},
    ],
  )
  counts = get_reproducibility_status_counts(df)
  assert counts["checked_patents"] == 3
  assert counts["evidence_map_ready"] == 1
  assert counts["manual_claims_required"] == 2
  assert counts["next_manual_actions"] == 2


def test_status_counts_include_evidence_map_ready() -> None:
  df = pd.DataFrame([{"status": "evidence_map_ready"}])
  counts = get_reproducibility_status_counts(df)
  assert counts["evidence_map_ready"] == 1


def test_safe_read_csv_empty_file(tmp_path: Path) -> None:
  empty = tmp_path / "empty.csv"
  empty.write_text("publication_number,status\n", encoding="utf-8")
  df, err = safe_read_csv(empty)
  assert df.empty
  assert err == ""


def test_manual_checklist_notice_and_caution_text() -> None:
  assert "supporting evidence candidate" in REPRODUCIBILITY_CAUTION
  assert "FTO、侵害、有効性判断ではありません" in REPRODUCIBILITY_CAUTION
  assert "Synthetic demo signal" in REPRODUCIBILITY_CAUTION
  assert "自動スクレイピング" in MANUAL_CHECKLIST_NOTICE


def test_one_off_answer_card_html() -> None:
  html = render_one_off_answer_card_html()
  assert "1件だけの偶然" in html
  assert ONE_OFF_ANSWER_BODY.split("。")[0] in html


def test_brief_card_html() -> None:
  html = render_reproducibility_brief_card_html(
    {
      "evidence_map_ready": 1,
      "manual_claims_required": 2,
    },
  )
  assert "再現性確認の現在地" in html
  assert "Evidence Map ready" in html


def test_loader_reads_checklist_markdown(tmp_path: Path) -> None:
  _write_smoke_outputs(tmp_path)
  artifacts = load_reproducibility_smoke_artifacts(tmp_path)
  assert artifacts.manual_claims_checklist_md is not None
  assert "import_manual_fulltext.py" in artifacts.manual_claims_checklist_md
