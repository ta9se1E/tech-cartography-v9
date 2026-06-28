"""Tests for Phase27S.6 evidence-aware gap / next actions."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from tech_cartography.runtime.v8_evidence_gap_schema import (
  FORBIDDEN_GAP_WORDS,
  GAP_TYPE_NO_EXAMPLE_FACTS,
  GAP_TYPE_OCR_HUMAN_REVIEW,
  GAP_TYPE_PROCESS_CONDITION_REVIEW,
  GAP_TYPE_PROPERTY_VALUE_REVIEW,
  GAP_TYPE_READY_FOR_HUMAN_REVIEW,
  GAP_TYPE_STRUCTURE_PROPERTY_REVIEW,
  GAP_TYPE_TABLE_REVIEW,
)
from tech_cartography.services.v8_evidence_gap_next_actions import (
  build_evidence_aware_gap_report,
  export_evidence_aware_gap_next_actions,
  gaps_for_claim_link_row,
  human_review_checklist_markdown,
)

CASE_ID = "test_case_ev_gap_s6"
PUB_CN108 = "CN108286090A"
PUB_CN105 = "CN105401262A"


def _cn108_row() -> dict[str, str]:
  return {
    "case_id": CASE_ID,
    "publication_number": PUB_CN108,
    "claim_no": "1",
    "claim_text": "PAN graphitization claim",
    "support_type": "mixed_support_candidate",
    "support_level": "high_candidate",
    "matched_fact_types": "process_condition|property_value|structure_property|table_candidate",
    "matched_elements": "graphitization|tensile strength",
    "missing_elements": "",
    "linked_fact_ids": "f_proc1|f_prop1|f_struct1|f_table1",
    "top_evidence_snippets": "石墨化温度2480℃|拉伸强度 4.38GPa|取向角15.50°|表1性能对比",
    "needs_human_review": "True",
    "binding_version": "phase27s54",
    "source_example_facts_csv": "/tmp/example_facts.csv",
    "warning": "",
  }


def _cn105_row() -> dict[str, str]:
  return {
    "case_id": CASE_ID,
    "publication_number": PUB_CN105,
    "claim_no": "1",
    "claim_text": "claim without facts",
    "support_type": "no_example_support_candidate",
    "support_level": "none",
    "matched_fact_types": "",
    "matched_elements": "",
    "missing_elements": "example",
    "linked_fact_ids": "",
    "top_evidence_snippets": "",
    "needs_human_review": "True",
    "binding_version": "phase27s54",
    "warning": "no example facts for publication",
  }


def test_cn108_generates_review_and_type_gaps():
  gaps = gaps_for_claim_link_row(_cn108_row(), source_links_csv="/tmp/links.csv")
  types = {g.gap_type for g in gaps}
  assert GAP_TYPE_READY_FOR_HUMAN_REVIEW in types
  assert GAP_TYPE_PROPERTY_VALUE_REVIEW in types
  assert GAP_TYPE_TABLE_REVIEW in types
  assert GAP_TYPE_PROCESS_CONDITION_REVIEW in types
  assert GAP_TYPE_STRUCTURE_PROPERTY_REVIEW in types
  assert all(g.needs_human_review for g in gaps)


def test_cn105_no_example_facts_gap():
  gaps = gaps_for_claim_link_row(_cn105_row(), source_links_csv="/tmp/links.csv")
  assert len(gaps) == 1
  assert gaps[0].gap_type == GAP_TYPE_NO_EXAMPLE_FACTS
  assert "PDF" in gaps[0].next_action or "OCR" in gaps[0].next_action
  assert "ファクト" in gaps[0].next_action or "facts" in gaps[0].next_action.lower()


def test_ocr_human_review_gap_without_forbidden_words():
  gaps = gaps_for_claim_link_row(_cn108_row(), source_links_csv="/tmp/links.csv")
  ocr_gaps = [g for g in gaps if g.gap_type == GAP_TYPE_OCR_HUMAN_REVIEW]
  assert ocr_gaps
  blob = " ".join(
    f"{g.gap_label} {g.gap_description} {g.next_action}" for g in gaps
  ).lower()
  for word in FORBIDDEN_GAP_WORDS:
    assert word.lower() not in blob


def test_export_and_summary_counts(tmp_path: Path):
  bind_dir = tmp_path / "outputs" / "local_v8_claim_example_links" / f"{CASE_ID}_t_abcd1234"
  bind_dir.mkdir(parents=True)
  links_csv = bind_dir / "claim_example_links.csv"
  fields = list(_cn108_row().keys()) + ["example_id", "example_label", "binding_method"]
  rows = [_cn108_row(), _cn105_row()]
  with links_csv.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
      writer.writerow(row)

  summary_csv = bind_dir / "claim_example_binding_summary.csv"
  with summary_csv.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=[
      "case_id", "publication_number", "claim_count", "linked_claim_count",
      "needs_human_review", "status", "warning",
    ])
    writer.writeheader()
    writer.writerow({
      "case_id": CASE_ID,
      "publication_number": PUB_CN108,
      "claim_count": 1,
      "linked_claim_count": 1,
      "needs_human_review": "True",
      "status": "ok",
      "warning": "",
    })
    writer.writerow({
      "case_id": CASE_ID,
      "publication_number": PUB_CN105,
      "claim_count": 1,
      "linked_claim_count": 0,
      "needs_human_review": "True",
      "status": "no_facts_for_pub",
      "warning": "no example facts",
    })

  report = build_evidence_aware_gap_report(CASE_ID, project_root=tmp_path)
  assert report.gap_count > 0
  out_dir = export_evidence_aware_gap_next_actions(report, project_root=tmp_path)

  gap_csv = out_dir / "gap_next_actions.csv"
  summary_csv_out = out_dir / "gap_next_actions_summary.csv"
  checklist = out_dir / "human_review_checklist.md"
  assert gap_csv.exists()
  assert summary_csv_out.exists()
  assert checklist.exists()

  with gap_csv.open(encoding="utf-8", newline="") as handle:
    gap_rows = list(csv.DictReader(handle))
  assert all(r.get("source_claim_example_links_csv") for r in gap_rows)
  assert all(r.get("needs_human_review") == "True" for r in gap_rows)

  with summary_csv_out.open(encoding="utf-8", newline="") as handle:
    summaries = list(csv.DictReader(handle))
  cn108 = next(s for s in summaries if s["publication_number"] == PUB_CN108)
  cn105 = next(s for s in summaries if s["publication_number"] == PUB_CN105)
  assert int(cn108["ready_for_human_review_count"]) > 0
  assert int(cn108["property_value_review_gap_count"]) > 0
  assert int(cn105["no_example_facts_gap_count"]) > 0

  checklist_text = checklist.read_text(encoding="utf-8")
  assert PUB_CN108 in checklist_text
  assert "未確認事項" in checklist_text


def test_human_review_checklist_generated():
  report = build_evidence_aware_gap_report(
    CASE_ID,
    project_root=Path("/nonexistent"),
    claim_example_links_dir=Path("/nonexistent"),
  )
  report.gaps = gaps_for_claim_link_row(_cn108_row(), source_links_csv="/tmp/links.csv")
  md = human_review_checklist_markdown(report)
  assert "Human Review Checklist" in md
  assert "claim" in md.lower()
