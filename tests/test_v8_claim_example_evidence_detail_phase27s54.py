"""Tests for Phase27S.5.4 claim-example binding evidence detail."""

from __future__ import annotations

import csv
import time
from pathlib import Path

import pytest

from tech_cartography.runtime.v8_extraction_vocabulary_schema import ExtractionVocabulary
from tech_cartography.services.v8_claim_example_binding import (
  bind_claims_to_example_facts,
  score_claim_example_candidate,
  should_rerun_claim_example_binding,
  write_claim_example_binding_outputs,
)

CASE_ID = "test_case_cebind_s54"
PUB = "CN108286090A"

CLAIM_TEXT = (
  "A PAN precursor pre-oxidation carbonization graphitization method with dwelling time "
  "stretch ratio tensile strength tensile modulus orientation angle performance comparison table."
)

EXAMPLE_5_FACTS = [
  {
    "publication_number": PUB,
    "example_id": "Example 5",
    "example_label": "实施例5",
    "fact_id": "f_proc1",
    "fact_type": "process_condition",
    "process_step": "graphitization",
    "condition_name": "temperature",
    "condition_value": "2480",
    "condition_unit": "℃",
    "evidence_text": "石墨化温度2480℃",
    "matched_user_keywords": "graphitization",
  },
  {
    "publication_number": PUB,
    "example_id": "Example 5",
    "example_label": "实施例5",
    "fact_id": "f_proc2",
    "fact_type": "process_condition",
    "condition_name": "time",
    "condition_value": "2.5",
    "condition_unit": "min",
    "evidence_text": "停留时间2.5min",
    "matched_user_keywords": "",
  },
  {
    "publication_number": PUB,
    "example_id": "Example 5",
    "example_label": "实施例5",
    "fact_id": "f_proc3",
    "fact_type": "process_condition",
    "condition_name": "stretch ratio",
    "condition_value": "120",
    "condition_unit": "%",
    "evidence_text": "相对拉伸倍率120%",
    "matched_user_keywords": "",
  },
  {
    "publication_number": PUB,
    "example_id": "Example 5",
    "example_label": "实施例5",
    "fact_id": "f_prop1",
    "fact_type": "property_value",
    "property_name": "tensile_strength",
    "property_value": "4.38",
    "property_unit": "GPa",
    "evidence_text": "拉伸强度 4.38GPa",
    "matched_user_keywords": "tensile strength",
  },
  {
    "publication_number": PUB,
    "example_id": "Example 5",
    "example_label": "实施例5",
    "fact_id": "f_prop2",
    "fact_type": "property_value",
    "property_name": "tensile_modulus",
    "property_value": "591",
    "property_unit": "GPa",
    "evidence_text": "拉伸模量 591GPa",
    "matched_user_keywords": "tensile modulus",
  },
  {
    "publication_number": PUB,
    "example_id": "Example 5",
    "example_label": "实施例5",
    "fact_id": "f_struct1",
    "fact_type": "structure_property",
    "property_name": "orientation_angle",
    "property_value": "15.50",
    "property_unit": "°",
    "evidence_text": "所得高温碳化纤维中碳微晶的取向角为15.50°",
    "matched_user_keywords": "",
  },
  {
    "publication_number": PUB,
    "example_id": "Example 5",
    "example_label": "实施例5",
    "fact_id": "f_table1",
    "fact_type": "table_candidate",
    "evidence_text": "表1.与日本东丽公司高强高模碳纤维性能对比表 M55J 4.02 540",
    "matched_user_keywords": "",
  },
]

EXAMPLE_3_FACTS = [
  {
    "publication_number": PUB,
    "example_id": "Example 3",
    "example_label": "实施例3",
    "fact_id": "f3_proc",
    "fact_type": "process_condition",
    "process_step": "pre-oxidation",
    "evidence_text": "预氧化处理",
    "matched_user_keywords": "pre-oxidation",
  },
]


def _vocab() -> ExtractionVocabulary:
  return ExtractionVocabulary(
    case_id=CASE_ID,
    material_keywords=["PAN", "precursor"],
    process_keywords=["carbonization", "graphitization", "pre-oxidation"],
    property_keywords=["tensile strength", "tensile modulus"],
    structure_keywords=["orientation angle"],
  )


def _claim() -> dict:
  return {
    "case_id": CASE_ID,
    "publication_number": PUB,
    "claim_no": "1",
    "claim_text": CLAIM_TEXT,
  }


def test_example_5_selected_over_example_3() -> None:
  vocab = _vocab()
  score5, link5 = score_claim_example_candidate(
    _claim(), EXAMPLE_5_FACTS, vocab, group_key="Example 5",
  )
  score3, _link3 = score_claim_example_candidate(
    _claim(), EXAMPLE_3_FACTS, vocab, group_key="Example 3",
  )
  assert score5 > score3
  assert link5.example_id == "Example 5"


def test_mixed_support_with_fact_types_and_evidence() -> None:
  _, link = score_claim_example_candidate(
    _claim(), EXAMPLE_5_FACTS, _vocab(), group_key="Example 5",
  )
  assert link.support_type == "mixed_support_candidate"
  assert link.support_level == "high_candidate"
  assert link.example_id == "Example 5"
  assert link.linked_fact_ids
  assert link.evidence_texts
  assert link.matched_fact_count >= 5
  assert "process_condition" in link.matched_fact_types
  assert "property_value" in link.matched_fact_types
  assert "structure_property" in link.matched_fact_types
  assert "table_candidate" in link.matched_fact_types
  assert link.needs_human_review is True


def test_reason_contains_example_and_evidence_not_forbidden() -> None:
  _, link = score_claim_example_candidate(
    _claim(), EXAMPLE_5_FACTS, _vocab(), group_key="Example 5",
  )
  assert "Example 5" in link.reason
  assert "対応する可能性があります" in link.reason
  assert "根拠候補" in link.reason
  assert "人手確認" in link.reason
  forbidden = ["支えています", "証明しています", "裏取り完了", "権利範囲"]
  for word in forbidden:
    assert word not in link.reason


def test_no_cross_publication_facts() -> None:
  facts = EXAMPLE_5_FACTS + [{
    "publication_number": "CN999999A",
    "example_id": "Example 9",
    "fact_id": "other",
    "fact_type": "property_value",
    "property_name": "tensile_strength",
    "property_value": "9.9",
    "evidence_text": "tensile strength 9.9 GPa",
    "matched_user_keywords": "",
  }]
  _, link = score_claim_example_candidate(
    _claim(), facts, _vocab(), group_key="Example 5",
  )
  assert all("CN999999A" not in ev for ev in link.evidence_texts)


def test_summary_linked_counts(tmp_path: Path) -> None:
  case_dir = tmp_path / "cases" / CASE_ID
  case_dir.mkdir(parents=True)
  (case_dir / "claims_input.csv").write_text(
    "case_id,publication_number,patent_title,claim_no,claim_text,claim_source_type,claim_source_url,claim_source_path,notes\n"
    f"{CASE_ID},{PUB},Title,1,\"{CLAIM_TEXT}\",manual,,,\n",
    encoding="utf-8",
  )
  facts_dir = tmp_path / "outputs" / "local_v8_example_facts" / f"{CASE_ID}_test_s54"
  facts_dir.mkdir(parents=True)
  fields = [
    "case_id", "publication_number", "section_id", "section_type", "example_id", "example_label",
    "fact_id", "fact_type", "material", "process_step", "condition_name", "condition_value",
    "condition_unit", "property_name", "property_value", "property_unit", "comparison_type",
    "comparison_target", "table_id", "evidence_text", "matched_user_keywords", "page_start",
    "page_end", "confidence", "needs_human_review", "extraction_method", "warning",
  ]
  rows = []
  for fact in EXAMPLE_5_FACTS + EXAMPLE_3_FACTS:
    rows.append({
      "case_id": CASE_ID,
      "section_id": "s1",
      "section_type": "examples",
      "material": "",
      "process_step": fact.get("process_step", ""),
      "comparison_type": "",
      "comparison_target": "",
      "table_id": "",
      "page_start": "1",
      "page_end": "1",
      "confidence": "0.75",
      "needs_human_review": "True",
      "extraction_method": "gemini",
      "warning": "",
      **fact,
    })
  with (facts_dir / "example_facts.csv").open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
  (facts_dir / "example_facts_summary.csv").write_text(
    f"case_id,publication_number,status,fact_count\n{CASE_ID},{PUB},ok,{len(rows)}\n",
    encoding="utf-8",
  )

  results = bind_claims_to_example_facts(CASE_ID, tmp_path, tmp_path / "outputs")
  out_dir = write_claim_example_binding_outputs(CASE_ID, results, tmp_path / "outputs")
  summary = list(csv.DictReader((out_dir / "claim_example_binding_summary.csv").open(encoding="utf-8")))
  assert summary
  row = summary[0]
  assert int(row["linked_claim_count"]) >= 1
  assert int(row["linked_example_count"]) >= 1
  assert int(row["linked_fact_count"]) >= 1

  links = list(csv.DictReader((out_dir / "claim_example_links.csv").open(encoding="utf-8")))
  assert links[0]["example_id"] == "Example 5"
  assert links[0]["linked_fact_ids"]
  assert links[0]["top_evidence_snippets"]


def test_should_rerun_when_facts_newer(tmp_path: Path) -> None:
  case_dir = tmp_path / "cases" / CASE_ID
  case_dir.mkdir(parents=True)
  (case_dir / "claims_input.csv").write_text(
    f"case_id,publication_number,patent_title,claim_no,claim_text,claim_source_type,claim_source_url,claim_source_path,notes\n"
    f"{CASE_ID},{PUB},Title,1,text,manual,,,\n",
    encoding="utf-8",
  )
  facts_dir = tmp_path / "outputs" / "local_v8_example_facts" / f"{CASE_ID}_old"
  facts_dir.mkdir(parents=True)
  facts_csv = facts_dir / "example_facts.csv"
  facts_csv.write_text("case_id,publication_number,fact_id,fact_type,evidence_text\n", encoding="utf-8")
  bind_dir = tmp_path / "outputs" / "local_v8_claim_example_links" / f"{CASE_ID}_oldbind"
  bind_dir.mkdir(parents=True)
  (bind_dir / "claim_example_binding_summary.csv").write_text(
    f"case_id,publication_number,status,source_example_facts_csv\n"
    f"{CASE_ID},{PUB},ok,{facts_csv}\n",
    encoding="utf-8",
  )
  (bind_dir / "claim_example_links.csv").write_text("case_id\n", encoding="utf-8")
  past = time.time() - 7200
  import os
  os.utime(bind_dir / "claim_example_links.csv", (past, past))
  facts_csv.write_text(
    "case_id,publication_number,fact_id,fact_type,evidence_text,example_id\n"
    f"{CASE_ID},{PUB},f1,process_condition,graphitization step,Example 5\n",
    encoding="utf-8",
  )
  os.utime(facts_csv, (time.time(), time.time()))
  should, latest_facts, _ = should_rerun_claim_example_binding(CASE_ID, tmp_path)
  assert should is True
  assert latest_facts is not None
