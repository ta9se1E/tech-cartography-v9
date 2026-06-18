"""Tests for Strategic Watch Brief builder (Phase 23.5)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from tech_cartography.reports.project_export import save_records_csv
from tech_cartography.strategic_watch.brief_builder import (
  build_strategic_watch_brief,
  build_watch_items_from_web_signal_links,
  dry_run_strategic_watch_brief,
  infer_watch_priority,
  infer_watch_theme,
  infer_watch_type,
  render_strategic_watch_brief_md,
  safe_read_csv,
)
from tech_cartography.strategic_watch.schema import BRIEF_CAUTION, ITEM_CAVEAT, WATCH_PRIORITY_NOTE
from tech_cartography.strategic_watch.store import save_strategic_watch_brief


def _link_row(**overrides: object) -> dict[str, object]:
  base = {
    "link_id": "wlink-test-1",
    "publication_number": "US-12565719-B2",
    "claim_element_text": "",
    "paper_title": "Carbon fiber composite paper",
    "web_signal_id": "wsig-1",
    "web_signal_type": "national_project",
    "web_signal_title": "NEDO CFRP project",
    "web_signal_domain": "nedo.go.jp",
    "source_quality": "high",
    "link_type": "project_context_match",
    "link_score": 75,
    "matched_terms": "carbon fiber; polyacrylonitrile",
    "matched_strong_terms": "polyacrylonitrile",
    "matched_moderate_terms": "carbon fiber",
    "matched_broad_terms": "",
    "evidence_sentence": "Carbon fiber CFRP project",
    "confidence": "low",
    "web_signal_url": "https://www.nedo.go.jp/project/1",
    "next_verification_action": "Verify project page",
  }
  base.update(overrides)
  return base


def _write_fixture(root: Path) -> None:
  pub = "US-12565719-B2"
  link_dir = root / "outputs" / "web_signal_links" / pub
  ev_dir = root / "outputs" / "evidence_map_synthesis" / pub
  link_dir.mkdir(parents=True, exist_ok=True)
  ev_dir.mkdir(parents=True, exist_ok=True)

  rows = [
    _link_row(),
    _link_row(
      link_id="wlink-test-2",
      web_signal_type="grant",
      web_signal_title="JST grant",
      web_signal_domain="jst.go.jp",
      link_score=65,
    ),
    _link_row(
      link_id="wlink-test-3",
      web_signal_type="ir_disclosure",
      web_signal_title="IR report",
      web_signal_domain="example.co.jp",
      link_type="company_context_match",
      matched_terms="carbon fiber",
      link_score=55,
      confidence="weak",
      web_signal_url="https://example.co.jp/ir",
    ),
    _link_row(
      link_id="wlink-test-4",
      web_signal_type="national_project",
      matched_terms="pan",
      matched_broad_terms="pan",
      matched_moderate_terms="",
      matched_strong_terms="",
      link_score=40,
      confidence="weak",
      evidence_sentence="",
      web_signal_url="",
    ),
  ]
  save_records_csv(rows, link_dir / "web_signal_link_candidates.csv")
  save_records_csv([], link_dir / "top_priority_web_signal_links.csv")
  (ev_dir / "evidence_map_synthesis.json").write_text(
    json.dumps({"evidence_gaps": ["claims_only route"]}),
    encoding="utf-8",
  )


def test_empty_input_brief_builds(tmp_path: Path) -> None:
  brief = build_strategic_watch_brief("US-12565719-B2", project_root=tmp_path)
  assert brief.publication_number == "US-12565719-B2"
  assert isinstance(brief.watch_items, list)


def test_watch_priority_from_link_score() -> None:
  medium_row = pd.Series(_link_row(link_score=75, confidence="low"))
  low_row = pd.Series(_link_row(link_score=40, confidence="weak", matched_terms="pan", matched_broad_terms="pan"))
  assert infer_watch_priority(medium_row) == "medium"
  assert infer_watch_priority(low_row) == "low"


def test_national_project_signal_classification() -> None:
  row = pd.Series(_link_row(web_signal_type="national_project", paper_title="", link_type="project_context_match"))
  assert infer_watch_type(row) == "national_project_signal"


def test_patent_paper_web_signal_classification() -> None:
  row = pd.Series(_link_row(web_signal_type="national_project", link_type="project_context_match"))
  assert infer_watch_type(row) == "patent_paper_web_signal"


def test_money_signal_classification() -> None:
  row = pd.Series(_link_row(web_signal_type="grant", paper_title=""))
  assert infer_watch_type(row) == "money_signal"


def test_ir_disclosure_signal_classification() -> None:
  row = pd.Series(_link_row(web_signal_type="ir_disclosure", paper_title=""))
  assert infer_watch_type(row) == "ir_disclosure_signal"


def test_why_it_matters_not_empty() -> None:
  df = pd.DataFrame([_link_row()])
  items = build_watch_items_from_web_signal_links(df, "US-12565719-B2")
  assert items
  assert all(item.why_it_matters.strip() for item in items)


def test_evidence_basis_not_empty() -> None:
  df = pd.DataFrame([_link_row()])
  items = build_watch_items_from_web_signal_links(df, "US-12565719-B2")
  assert all(item.evidence_basis.strip() for item in items)


def test_caveat_not_empty() -> None:
  df = pd.DataFrame([_link_row()])
  items = build_watch_items_from_web_signal_links(df, "US-12565719-B2")
  assert all(ITEM_CAVEAT.split(".")[0] in item.caveat for item in items)


def test_markdown_contains_not_final_conclusion(tmp_path: Path) -> None:
  _write_fixture(tmp_path)
  brief = build_strategic_watch_brief("US-12565719-B2", project_root=tmp_path)
  md = render_strategic_watch_brief_md(brief)
  assert "Strategic Watch Brief, not a final conclusion" in md
  assert "FTO, infringement, or validity analysis" in md
  assert WATCH_PRIORITY_NOTE in md
  assert BRIEF_CAUTION.splitlines()[0] in md


def test_dry_run_no_output(tmp_path: Path) -> None:
  _write_fixture(tmp_path)
  out = tmp_path / "outputs/strategic_watch_briefs/US-12565719-B2"
  result = dry_run_strategic_watch_brief("US-12565719-B2", project_root=tmp_path)
  assert result["input_counts"]["link_candidates"] >= 1
  assert not out.exists()


def test_missing_files_no_crash(tmp_path: Path) -> None:
  result = dry_run_strategic_watch_brief("US-MISSING", project_root=tmp_path)
  assert result["artifact_checks"]["web_signal_link_candidates"] is False
  brief = build_strategic_watch_brief("US-MISSING", project_root=tmp_path)
  assert brief.watch_items == [] or isinstance(brief.watch_items, list)


def test_save_outputs(tmp_path: Path) -> None:
  _write_fixture(tmp_path)
  brief = build_strategic_watch_brief("US-12565719-B2", project_root=tmp_path, top_n=3)
  out = tmp_path / "outputs/strategic_watch_briefs/US-12565719-B2"
  paths = save_strategic_watch_brief(brief, out)
  for name in (
    "strategic_watch_brief.json",
    "strategic_watch_items.csv",
    "top_strategic_watch_items.csv",
    "strategic_watch_brief.md",
    "strategic_watch_next_actions.md",
  ):
    assert (out / name).exists(), name
  assert paths["strategic_watch_brief_md"].exists()


def test_infer_watch_theme() -> None:
  row = pd.Series(_link_row(matched_terms="carbon fiber; cfrp"))
  theme = infer_watch_theme(row)
  assert "carbon fiber" in theme.lower() or "cfrp" in theme.lower()


def test_safe_read_csv_missing(tmp_path: Path) -> None:
  df = safe_read_csv(tmp_path / "missing.csv")
  assert df.empty
