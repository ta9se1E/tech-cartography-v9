"""Tests for core validation gate (Phase 24.4)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tech_cartography.reports.project_export import save_records_csv
from tech_cartography.validation.core_validation import (
  VALIDATION_CAUTION,
  analyze_link_score_calibration,
  build_core_validation_summary,
  build_freeze_readiness_judgement,
  build_reproducibility_patent_status,
)
from tech_cartography.validation.store import save_core_validation_pack
from tech_cartography.web_signals.linker import LINK_CSV_COLUMNS


def _link_row(**overrides: object) -> dict[str, object]:
  base = {col: "" for col in LINK_CSV_COLUMNS}
  base.update(
    {
      "link_id": "wlink-1",
      "publication_number": "US-12565719-B2",
      "link_score": 75,
      "link_type": "project_context_match",
      "score_cap_reason": "claim_element_missing_cap_75",
      "needs_manual_review": True,
      "matched_terms": "carbon fiber; polyacrylonitrile",
      "matched_broad_terms": "",
    },
  )
  base.update(overrides)
  return base


def _write_demo_fixture(root: Path) -> None:
  pub = "US-12565719-B2"
  link_dir = root / "outputs" / "web_signal_links" / pub
  ev_dir = root / "outputs" / "evidence_map_synthesis" / pub
  watch_dir = root / "outputs" / "strategic_watch_briefs" / pub
  delivery_dir = root / "outputs" / "delivery"
  manual_dir = root / "inputs" / "manual"
  link_dir.mkdir(parents=True, exist_ok=True)
  ev_dir.mkdir(parents=True, exist_ok=True)
  watch_dir.mkdir(parents=True, exist_ok=True)
  delivery_dir.mkdir(parents=True, exist_ok=True)
  manual_dir.mkdir(parents=True, exist_ok=True)

  rows = [
    _link_row(link_id="a", link_score=75),
    _link_row(link_id="b", link_score=55, link_type="weak_keyword_overlap", score_cap_reason="broad_only_cap_45"),
    _link_row(link_id="c", link_score=40, matched_terms="pan", matched_broad_terms="pan"),
    _link_row(link_id="d", link_score=100, link_type="manual_review_required"),
  ]
  save_records_csv(rows, link_dir / "web_signal_link_candidates.csv")

  (ev_dir / "evidence_map_synthesis.md").write_text("# map", encoding="utf-8")
  (ev_dir / "evidence_map_synthesis.json").write_text("{}", encoding="utf-8")
  (manual_dir / f"{pub}_claims.txt").write_text("claim 1", encoding="utf-8")
  (watch_dir / "strategic_watch_brief.md").write_text("# watch", encoding="utf-8")
  (delivery_dir / f"weekly_digest_preview_{pub}.md").write_text("# digest", encoding="utf-8")

  oa_dir = root / "outputs" / "openalex_limited_execution"
  oa_dir.mkdir(parents=True, exist_ok=True)
  save_records_csv(
    [{"publication_number": pub, "title": "paper", "paper_id": "p1"}],
    oa_dir / "selected_evidence_papers.csv",
  )
  save_records_csv(
    [{"publication_number": pub, "claim_element_text": "CE-1", "paper_title": "paper"}],
    oa_dir / "claim_paper_candidate_links.csv",
  )


def test_link_score_distribution_multi_range_resolved(tmp_path: Path) -> None:
  _write_demo_fixture(tmp_path)
  summary = analyze_link_score_calibration(tmp_path, "US-12565719-B2")
  assert summary is not None
  assert summary.total_link_candidates == 4
  assert summary.all_100_problem_resolved is True
  assert summary.score_distribution["40-59"] >= 1


def test_all_100_scores_not_resolved(tmp_path: Path) -> None:
  pub = "US-TEST-ALL100"
  link_dir = tmp_path / "outputs" / "web_signal_links" / pub
  link_dir.mkdir(parents=True, exist_ok=True)
  save_records_csv(
    [_link_row(publication_number=pub, link_id=f"x{i}", link_score=100) for i in range(3)],
    link_dir / "web_signal_link_candidates.csv",
  )
  summary = analyze_link_score_calibration(tmp_path, pub)
  assert summary is not None
  assert summary.all_100_problem_resolved is False
  assert summary.score_100_count == 3


def test_blocked_missing_manual_claims_status(tmp_path: Path) -> None:
  status = build_reproducibility_patent_status(tmp_path, "US-12435451-B2")
  assert status.status == "blocked_missing_manual_claims"
  assert status.manual_fulltext_input_exists is False
  assert "Manual Claims" in status.status_note


def test_complete_existing_demo_status(tmp_path: Path) -> None:
  _write_demo_fixture(tmp_path)
  status = build_reproducibility_patent_status(tmp_path, "US-12565719-B2")
  assert status.status == "complete_existing_demo"
  assert status.evidence_map_exists is True
  assert status.web_signal_links_exists is True


def test_core_validation_summary_counts(tmp_path: Path) -> None:
  _write_demo_fixture(tmp_path)
  summary = build_core_validation_summary(
    tmp_path,
    ["US-12565719-B2", "US-12435451-B2", "US-12516451-B2"],
  )
  assert summary.complete_count == 1
  assert summary.blocked_manual_claims_count == 2
  assert "US-12565719-B2" in summary.link_calibration


def test_freeze_readiness_and_patch_notes(tmp_path: Path) -> None:
  _write_demo_fixture(tmp_path)
  summary = build_core_validation_summary(tmp_path, ["US-12565719-B2", "US-12435451-B2"])
  judgement = build_freeze_readiness_judgement(summary)
  assert "Freeze ready with declared limitations" in judgement
  assert "manual claims" in judgement.lower() or "Manual Claims" in judgement

  paths = save_core_validation_pack(summary, tmp_path / "outputs" / "validation" / "core_validation")
  assert paths["freeze_judgement_md"].exists()
  assert paths["readme_patch_md"].exists()
  assert paths["demo_patch_md"].exists()
  assert paths["limitations_patch_md"].exists()
  assert VALIDATION_CAUTION in paths["freeze_judgement_md"].read_text(encoding="utf-8")
  assert "FTO" in paths["limitations_patch_md"].read_text(encoding="utf-8")


def test_link_score_summary_json_roundtrip(tmp_path: Path) -> None:
  _write_demo_fixture(tmp_path)
  summary = analyze_link_score_calibration(tmp_path, "US-12565719-B2")
  assert summary is not None
  payload = summary.to_dict()
  assert payload["median_score"] is not None
  assert "link_type_counts" in payload
