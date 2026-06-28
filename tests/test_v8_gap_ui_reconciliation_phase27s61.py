"""Tests for Phase27S.6.1 gap UI reconciliation."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from tech_cartography.runtime.v8_evidence_gap_schema import (
  FORBIDDEN_GAP_WORDS,
  EvidenceAwareGapSummary,
)
from tech_cartography.runtime.v8_top5_pdf_pipeline_status_schema import Top5PdfPipelineStatus
from tech_cartography.services.v8_evidence_gap_next_actions import (
  _dedupe_evidence_snippets,
  build_evidence_aware_gap_report,
  build_top3_next_actions_from_evidence_gaps,
  evidence_aware_gap_primary_available,
  export_evidence_aware_gap_next_actions,
  gaps_for_claim_link_row,
  human_review_checklist_markdown,
)
from tech_cartography.services.v8_top5_pdf_pipeline_status import infer_next_action, infer_pipeline_status_label
from tech_cartography.ui.v8_gap_next_actions_ui import _render_single_report  # noqa: F401 — module import check

CASE_ID = "test_case_gap_ui_s61"
PUB_CN108 = "CN108286090A"
PUB_CN105 = "CN105401262A"


def _cn108_row() -> dict[str, str]:
  return {
    "case_id": CASE_ID,
    "publication_number": PUB_CN108,
    "claim_no": "1",
    "support_type": "mixed_support_candidate",
    "support_level": "high_candidate",
    "matched_fact_types": "process_condition|property_value|structure_property|table_candidate",
    "linked_fact_ids": "f1|f2",
    "top_evidence_snippets": "拉伸强度 4.38GPa|表1性能对比",
    "needs_human_review": "True",
    "binding_version": "phase27s54",
    "gap_label": "x",
    "gap_description": "x",
    "next_action": "x",
  }


def _cn105_row() -> dict[str, str]:
  return {
    "case_id": CASE_ID,
    "publication_number": PUB_CN105,
    "claim_no": "1",
    "support_type": "no_example_support_candidate",
    "support_level": "none",
    "linked_fact_ids": "",
    "top_evidence_snippets": "",
    "needs_human_review": "True",
    "warning": "no example facts",
  }


def test_evidence_primary_available(tmp_path: Path):
  bind_dir = tmp_path / "outputs" / "local_v8_claim_example_links" / f"{CASE_ID}_t_abcd"
  bind_dir.mkdir(parents=True)
  (bind_dir / "claim_example_binding_summary.csv").write_text("case_id\n", encoding="utf-8")
  links = bind_dir / "claim_example_links.csv"
  with links.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(_cn108_row().keys()))
    writer.writeheader()
    writer.writerow(_cn108_row())

  gap_dir = tmp_path / "outputs" / "local_v8_gap_next_actions" / f"{CASE_ID}_t_efgh"
  gap_dir.mkdir(parents=True)
  (gap_dir / "evidence_gap_manifest.json").write_text(
    '{"generation_method":"claim_example_evidence_phase27s6"}',
    encoding="utf-8",
  )
  (gap_dir / "gap_next_actions.csv").write_text("generation_method,gap_severity\nx,y\n", encoding="utf-8")

  assert evidence_aware_gap_primary_available(CASE_ID, tmp_path)


def test_cn108_review_ready_no_run_ocr():
  status = Top5PdfPipelineStatus(
    case_id=CASE_ID,
    publication_number=PUB_CN108,
    pdf_uploaded=True,
    pdf_text_extracted=True,
    vision_ocr_text_extracted=True,
    sections_extracted=True,
    has_examples=True,
    examples_count=2,
    example_facts_extracted=True,
    claim_example_links_generated=True,
    evidence_aware_gaps_generated=True,
    evidence_ready_for_review=True,
    needs_ocr=True,
  )
  action = infer_next_action(status)
  assert "Run Google Vision OCR" not in action
  assert "PDF原文" in action or "Review OCR-derived" in action or "human review" in action.lower()
  label, _ = infer_pipeline_status_label(status)
  assert label == "Review-ready candidate"


def test_top3_actions_not_duplicated():
  rows = [_cn108_row()]
  for claim_no in ("2", "3", "4", "5", "6", "7", "8"):
    row = dict(_cn108_row())
    row["claim_no"] = claim_no
    rows.append(row)
  rows.append(_cn105_row())

  report = build_evidence_aware_gap_report(CASE_ID, project_root=Path("/none"))
  report.gaps = []
  for row in rows:
    report.gaps.extend(gaps_for_claim_link_row(row, source_links_csv="/tmp/links.csv"))
  report.summaries = [
    EvidenceAwareGapSummary(
      case_id=CASE_ID,
      publication_number=PUB_CN108,
      claim_count=8,
      ready_for_human_review_count=8,
    ),
    EvidenceAwareGapSummary(
      case_id=CASE_ID,
      publication_number=PUB_CN105,
      no_example_facts_gap_count=1,
    ),
  ]

  top3 = build_top3_next_actions_from_evidence_gaps(report)
  assert len(top3) == 3
  titles = [a.action_title for a in top3]
  assert len(set(titles)) == 3
  types = {a.action_type for a in top3}
  assert "review_property_table_candidates" in types
  assert "review_process_conditions" in types
  assert "complete_example_fact_pipeline" in types
  blob = " ".join(titles).lower()
  for word in FORBIDDEN_GAP_WORDS:
    assert word.lower() not in blob


def test_checklist_dedupes_evidence():
  gaps = gaps_for_claim_link_row(_cn108_row(), source_links_csv="/tmp/links.csv")
  dup_gap = gaps[0]
  gaps.append(dup_gap)
  deduped = _dedupe_evidence_snippets(gaps)
  keys = {(p, c, s) for p, c, s in deduped}
  assert len(keys) == len(deduped)

  report = build_evidence_aware_gap_report(CASE_ID, project_root=Path("/none"))
  report.gaps = gaps_for_claim_link_row(_cn108_row(), source_links_csv="/tmp/links.csv")
  md = human_review_checklist_markdown(report)
  assert "重複除去" in md
  assert PUB_CN108 in md
  assert "次PhaseでGapロジック更新" not in md


def test_export_includes_watch_and_digest(tmp_path: Path):
  bind_dir = tmp_path / "outputs" / "local_v8_claim_example_links" / f"{CASE_ID}_t_abcd"
  bind_dir.mkdir(parents=True)
  fields = list(_cn108_row().keys()) + ["example_id", "claim_text", "binding_method"]
  with (bind_dir / "claim_example_links.csv").open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerow(_cn108_row())
  (bind_dir / "claim_example_binding_summary.csv").write_text(
    "case_id,publication_number,claim_count,linked_claim_count,needs_human_review,status\n"
    f"{CASE_ID},{PUB_CN108},1,1,True,ok\n",
    encoding="utf-8",
  )

  report = build_evidence_aware_gap_report(CASE_ID, project_root=tmp_path)
  out_dir = export_evidence_aware_gap_next_actions(report, project_root=tmp_path)
  assert (out_dir / "watch_profile_update_proposal.md").exists()
  assert (out_dir / "digest_summary.md").exists()
  digest = (out_dir / "digest_summary.md").read_text(encoding="utf-8")
  assert "Top 3 Next Actions" in digest


def test_gap_ui_module_has_legacy_label():
  text = Path("src/tech_cartography/ui/v8_gap_next_actions_ui.py").read_text(encoding="utf-8")
  assert "Legacy Gap artifact" in text
  assert "Evidence-aware Gap" in text
