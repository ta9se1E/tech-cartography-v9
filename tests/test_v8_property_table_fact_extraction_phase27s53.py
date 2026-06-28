"""Tests for Phase27S.5.3 Chinese OCR property / table fact extraction hardening."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from tech_cartography.runtime.v8_example_facts_schema import ExampleFact
from tech_cartography.runtime.v8_extraction_vocabulary_schema import ExtractionVocabulary
from tech_cartography.services.v8_extraction_vocabulary import get_default_extraction_vocabulary
from tech_cartography.services.v8_gemini_example_facts import (
  _aggregate_result,
  build_example_facts_prompt,
  classify_property_candidate,
  normalize_example_fact_type,
  normalize_property_name,
  normalize_property_unit,
  parse_example_facts_json,
)
from tech_cartography.services.v8_patent_section_extract import detect_patent_sections_for_publication

CASE_ID = "test_case_s53"
PUB = "CN108286090A"

CN_TABLE_SECTION = """
表1.与日本东丽公司高强高模碳纤维性能对比表
实施例5
石墨化温度2480℃
停留时间2.5min
相对拉伸倍率120%
拉伸强度 4.38GPa
拉伸模量 591GPa
M55J 4.02 540
M60J 4.10 560
"""

CN_ORIENTATION = "所得高温碳化纤维中碳微晶的取向角为15.50°"


def _vocab() -> ExtractionVocabulary:
  return get_default_extraction_vocabulary(CASE_ID)


def _section(text: str, *, section_type: str = "examples", section_id: str = "sec1") -> dict[str, str]:
  return {
    "publication_number": PUB,
    "section_id": section_id,
    "section_type": section_type,
    "section_title": "实施例5",
    "section_text": text,
    "page_start": "3",
    "page_end": "4",
  }


def test_detect_table_candidate_section_from_chinese_ocr_text() -> None:
  result = detect_patent_sections_for_publication(
    CASE_ID, PUB, CN_TABLE_SECTION, page_texts=None,
  )
  types = {s.section_type for s in result.sections}
  assert "table_candidate" in types or result.tables_count > 0
  table_sections = [s for s in result.sections if s.section_type == "table_candidate"]
  if table_sections:
    assert table_sections[0].needs_human_review is True


def test_normalize_property_name_strength_modulus() -> None:
  assert normalize_property_name("拉伸强度") == "tensile_strength"
  assert normalize_property_name("拉伸模量") == "tensile_modulus"
  assert normalize_property_name("orientation angle") == "orientation_angle"


def test_normalize_property_unit() -> None:
  assert normalize_property_unit("gpa") == "GPa"
  assert normalize_property_unit("°C") == "℃"
  assert normalize_property_unit("分钟") == "min"


def test_reclassify_unknown_with_property_fields() -> None:
  fact = ExampleFact(
    case_id=CASE_ID,
    publication_number=PUB,
    section_id="sec1",
    section_type="examples",
    fact_id="f1",
    evidence_text="拉伸强度 4.38GPa",
    fact_type="unknown",
    property_name="拉伸强度",
    property_value="4.38",
    property_unit="GPa",
  )
  normalized = normalize_example_fact_type(fact)
  assert normalized.fact_type == "property_value"
  assert normalized.property_name == "tensile_strength"
  assert normalized.needs_human_review is True


def test_orientation_angle_structure_property() -> None:
  fact = ExampleFact(
    case_id=CASE_ID,
    publication_number=PUB,
    section_id="sec2",
    section_type="examples",
    fact_id="f2",
    evidence_text=CN_ORIENTATION,
    fact_type="unknown",
  )
  normalized = normalize_example_fact_type(fact)
  assert normalized.fact_type == "structure_property"
  assert normalized.property_name == "orientation_angle"
  assert normalized.property_value == "15.50"


def test_table_candidate_from_evidence_markers() -> None:
  fact = ExampleFact(
    case_id=CASE_ID,
    publication_number=PUB,
    section_id="sec3",
    section_type="table_candidate",
    fact_id="f3",
    evidence_text="表1 性能对比表 M55J 4.02 540 M60J 4.10 560",
    fact_type="unknown",
  )
  normalized = normalize_example_fact_type(fact)
  assert normalized.fact_type in {"table_candidate", "comparison_candidate"}
  assert normalized.needs_human_review is True
  assert normalized.confidence <= 0.75


def test_parse_json_applies_post_processing() -> None:
  payload = json.dumps({
    "facts": [
      {
        "fact_type": "unknown",
        "evidence_text": "拉伸模量 591GPa",
        "property_name": "模量",
        "property_value": "591",
        "property_unit": "GPa",
        "needs_human_review": True,
      },
    ],
  })
  facts = parse_example_facts_json(
    payload,
    case_id=CASE_ID,
    publication_number=PUB,
    section=_section("拉伸模量 591GPa"),
    vocabulary=_vocab(),
  )
  assert len(facts) == 1
  assert facts[0].fact_type == "property_value"
  assert facts[0].property_name == "tensile_modulus"


def test_summary_counts_include_table_and_structure(tmp_path: Path) -> None:
  facts = [
    ExampleFact(
      case_id=CASE_ID, publication_number=PUB, section_id="s1", section_type="examples",
      fact_id="f1", evidence_text="石墨化温度2480℃", fact_type="process_condition",
      condition_name="temperature", condition_value="2480", condition_unit="℃",
    ),
    ExampleFact(
      case_id=CASE_ID, publication_number=PUB, section_id="s2", section_type="table_candidate",
      fact_id="f2", evidence_text="表1 M55J 4.02 540", fact_type="table_candidate",
    ),
    ExampleFact(
      case_id=CASE_ID, publication_number=PUB, section_id="s3", section_type="examples",
      fact_id="f3", evidence_text=CN_ORIENTATION, fact_type="structure_property",
      property_name="orientation_angle", property_value="15.50", property_unit="°",
    ),
    ExampleFact(
      case_id=CASE_ID, publication_number=PUB, section_id="s4", section_type="examples",
      fact_id="f4", evidence_text="拉伸强度 4.38GPa", fact_type="property_value",
      property_name="tensile_strength", property_value="4.38", property_unit="GPa",
    ),
  ]
  result = _aggregate_result(
    CASE_ID, PUB, [_section(CN_TABLE_SECTION)], facts, source_sections_csv="sections.csv",
    status="ok",
  )
  assert result.process_condition_fact_count == 1
  assert result.table_candidate_count == 1
  assert result.structure_property_fact_count == 1
  assert result.property_fact_count == 1


def test_prompt_mentions_chinese_ocr_property_rules() -> None:
  prompt = build_example_facts_prompt(_section(CN_TABLE_SECTION), _vocab())
  assert "Chinese OCR" in prompt
  assert "table_candidate" in prompt
  assert "tensile_strength" in prompt


def test_no_fact_without_evidence_text() -> None:
  payload = json.dumps({
    "facts": [{"fact_type": "property_value", "property_name": "tensile_strength", "property_value": "9.9"}],
  })
  facts = parse_example_facts_json(
    payload, case_id=CASE_ID, publication_number=PUB,
    section=_section(CN_TABLE_SECTION), vocabulary=_vocab(),
  )
  assert facts == []


def test_classify_does_not_invent_missing_values() -> None:
  fact = ExampleFact(
    case_id=CASE_ID,
    publication_number=PUB,
    section_id="s",
    section_type="examples",
    fact_id="f",
    evidence_text="实施例5 石墨化",
    fact_type="unknown",
  )
  normalized = classify_property_candidate(fact)
  assert normalized.property_value is None
  assert normalized.fact_type in {"unknown", "property_candidate"}
