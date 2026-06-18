"""Tests for Web Signal Review Pack UI (Phase 23.3)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tech_cartography.reports.project_export import save_records_csv
from tech_cartography.ui.web_signal_review_ui import (
  get_web_signal_caution_text,
  get_web_signal_status_counts,
  is_ir_disclosure_empty,
  load_web_signal_review_artifacts,
  prepare_web_signal_display_df,
  safe_read_csv,
)


def _write_review_pack_fixture(root: Path, *, with_data: bool = True) -> Path:
  batch_dir = root / "outputs" / "web_signals" / "tavily_pan_carbon_fiber" / "review_pack"
  batch_dir.mkdir(parents=True, exist_ok=True)

  if with_data:
    high_rows = [
      {
        "signal_id": "wsig-1",
        "review_priority": 85,
        "signal_type": "national_project",
        "source_title": "NEDO 次世代航空機向けCFRP高レート生産技術",
        "source_domain": "nedo.go.jp",
        "source_quality": "high",
        "source_category": "national_project",
        "disclosure_type": "",
        "evidence_sentences": "炭素繊維 composite project",
        "confidence": "medium",
        "verification_status": "needs_human_review",
        "next_verification_action": "Verify project page",
        "source_url": "https://www.nedo.go.jp/project/1",
      },
      {
        "signal_id": "wsig-2",
        "review_priority": 70,
        "signal_type": "grant",
        "source_title": "JST PAN系炭素繊維",
        "source_domain": "jst.go.jp",
        "source_quality": "high",
        "source_category": "public_funding",
        "disclosure_type": "",
        "evidence_sentences": "['PAN carbon fiber research']",
        "confidence": "medium",
        "verification_status": "needs_human_review",
        "next_verification_action": "Verify grant page",
        "source_url": "",
      },
    ]
    money_rows = high_rows
    company_rows = [
      {
        "signal_id": "wsig-3",
        "review_priority": 55,
        "signal_type": "company",
        "source_title": "Company press release",
        "source_domain": "example.co.jp",
        "source_quality": "medium_high",
        "evidence_sentences": "",
        "confidence": "low",
        "verification_status": "needs_human_review",
        "next_verification_action": "Review press release",
        "source_url": "https://example.co.jp/news/1",
      },
    ]
    rejected_rows = [
      {
        "signal_id": "wsig-bad",
        "review_priority": 10,
        "signal_type": "other",
        "source_title": "",
        "source_domain": "",
        "source_quality": "low",
        "evidence_sentences": "",
        "rejection_reason": "missing_source_url",
        "source_url": "",
      },
    ]
  else:
    high_rows = []
    money_rows = []
    company_rows = []
    rejected_rows = []

  save_records_csv(high_rows, batch_dir / "high_priority_web_signals.csv")
  save_records_csv(high_rows, batch_dir / "web_signal_review_items.csv")
  save_records_csv([], batch_dir / "ir_disclosure_candidates.csv")
  save_records_csv(money_rows, batch_dir / "money_national_project_candidates.csv")
  save_records_csv(company_rows, batch_dir / "company_local_news_candidates.csv")
  save_records_csv(rejected_rows, batch_dir / "rejected_or_low_quality_sources.csv")
  (batch_dir / "web_signal_review_summary.md").write_text(
    "# Summary\n\nWeb signals are signal candidates.\n",
    encoding="utf-8",
  )
  (batch_dir / "web_signal_review_pack.json").write_text("{}", encoding="utf-8")
  return batch_dir


def test_missing_files_loader_does_not_crash(tmp_path: Path) -> None:
  artifacts = load_web_signal_review_artifacts(tmp_path)
  assert artifacts.status in {"missing", "partial", "error"}
  assert isinstance(artifacts.review_items_df, pd.DataFrame)


def test_loader_reads_fixture(tmp_path: Path) -> None:
  _write_review_pack_fixture(tmp_path)
  artifacts = load_web_signal_review_artifacts(tmp_path)
  assert artifacts.status in {"ready", "partial"}
  assert len(artifacts.high_priority_df) == 2
  assert len(artifacts.money_national_project_df) == 2


def test_empty_csv_prepare_display_df() -> None:
  df = prepare_web_signal_display_df(pd.DataFrame())
  assert isinstance(df, pd.DataFrame)
  assert "signal_id" in df.columns


def test_prepare_display_without_expected_columns() -> None:
  raw = pd.DataFrame([{"foo": "bar", "review_priority": 10}])
  display = prepare_web_signal_display_df(raw)
  assert display.iloc[0]["source_title"] == "not available"


@pytest.mark.parametrize(
  "value",
  [
    "PAN carbon fiber project",
    "['炭素繊維', 'NEDO project']",
    "",
    float("nan"),
  ],
)
def test_prepare_display_evidence_sentences_variants(value: object) -> None:
  raw = pd.DataFrame(
    [
      {
        "signal_id": "x",
        "review_priority": 50,
        "signal_type": "national_project",
        "source_title": "title",
        "source_domain": "nedo.go.jp",
        "source_quality": "high",
        "source_category": "national_project",
        "disclosure_type": "",
        "evidence_sentences": value,
        "confidence": "medium",
        "verification_status": "needs_human_review",
        "next_verification_action": "check",
        "source_url": "https://example.com",
      },
    ],
  )
  display = prepare_web_signal_display_df(raw)
  assert "evidence_sentences" in display.columns


def test_source_url_link_column() -> None:
  raw = pd.DataFrame(
    [
      {
        "signal_id": "x",
        "review_priority": 90,
        "signal_type": "national_project",
        "source_title": "NEDO project",
        "source_domain": "nedo.go.jp",
        "source_quality": "high",
        "source_category": "national_project",
        "disclosure_type": "",
        "evidence_sentences": "carbon fiber",
        "confidence": "medium",
        "verification_status": "needs_human_review",
        "next_verification_action": "check",
        "source_url": "https://www.nedo.go.jp/project/1",
      },
    ],
  )
  display = prepare_web_signal_display_df(raw)
  assert display.iloc[0]["source_url"].startswith("[")
  assert "nedo.go.jp" in display.iloc[0]["source_url"]


def test_source_url_missing_does_not_crash() -> None:
  raw = pd.DataFrame(
    [
      {
        "signal_id": "x",
        "review_priority": 1,
        "signal_type": "other",
        "source_title": "t",
        "source_domain": "",
        "source_quality": "unknown",
        "source_category": "search_result",
        "disclosure_type": "",
        "evidence_sentences": "",
        "confidence": "low",
        "verification_status": "needs_human_review",
        "next_verification_action": "check",
        "source_url": "",
      },
    ],
  )
  display = prepare_web_signal_display_df(raw)
  assert display.iloc[0]["source_url"] == "not available"


def test_status_counts() -> None:
  counts = get_web_signal_status_counts(
    review_items_df=pd.DataFrame([{"a": 1}, {"a": 2}]),
    high_priority_df=pd.DataFrame([{"a": 1}]),
    ir_disclosure_df=pd.DataFrame(),
    money_national_project_df=pd.DataFrame([{"a": 1}, {"a": 2}, {"a": 3}]),
    company_local_news_df=pd.DataFrame([{"a": 1}]),
    rejected_df=pd.DataFrame([{"a": 1}]),
  )
  assert counts["total_review_signals"] == 2
  assert counts["high_priority_signals"] == 1
  assert counts["money_national_project_signals"] == 3
  assert counts["ir_disclosure_signals"] == 0


def test_ir_disclosure_empty_state(tmp_path: Path) -> None:
  _write_review_pack_fixture(tmp_path)
  artifacts = load_web_signal_review_artifacts(tmp_path)
  assert is_ir_disclosure_empty(artifacts) is True


def test_caution_text_contains_required_phrases() -> None:
  caution_en, caution_ja = get_web_signal_caution_text()
  assert "Web signals are signal candidates" in caution_en
  assert "This is not FTO, infringement, or validity analysis" in caution_en
  assert "Synthetic demo signal must be clearly labeled" in caution_en
  assert "最終結論ではなく" in caution_ja


def test_safe_read_csv_missing() -> None:
  df, err = safe_read_csv(Path("/nonexistent/path.csv"))
  assert df.empty
  assert err


def test_empty_batch_review_pack_loader(tmp_path: Path) -> None:
  _write_review_pack_fixture(tmp_path, with_data=False)
  artifacts = load_web_signal_review_artifacts(tmp_path)
  assert artifacts.high_priority_df.empty
  assert artifacts.status in {"ready", "partial", "missing"}
