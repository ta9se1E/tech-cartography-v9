"""Tests for Phase27S.3 Gemini example facts extraction."""

from __future__ import annotations

import ast
import csv
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tech_cartography.runtime.v8_extraction_vocabulary_schema import ExtractionVocabulary
from tech_cartography.services.v8_extraction_vocabulary import get_default_extraction_vocabulary
from tech_cartography.services.v8_gemini_example_facts import (
  build_example_facts_prompt,
  export_gemini_prompts_only,
  load_target_sections,
  parse_example_facts_json,
  validate_example_fact,
  write_example_facts_outputs,
)
from tech_cartography.services.v8_llm_provider_gemini import (
  is_gemini_example_facts_enabled,
  set_gemini_json_generator_for_tests,
)
from tech_cartography.runtime.v8_example_facts_schema import ExampleFact

CASE_ID = "test_case_efacts"
PUB = "CN108286090A"


def _sections_csv(tmp_path: Path) -> Path:
  path = tmp_path / "publication_fulltext_sections.csv"
  fields = [
    "case_id", "publication_number", "section_id", "section_type", "section_title",
    "section_text", "page_start", "page_end", "text_length", "confidence",
    "needs_human_review", "detection_method", "warning",
  ]
  rows = [
    {
      "case_id": CASE_ID,
      "publication_number": PUB,
      "section_id": f"{PUB}_examples_1",
      "section_type": "examples",
      "section_title": "Example 1",
      "section_text": "The PAN precursor was carbonized at 1200 °C. Tensile strength was 3.5 GPa.",
      "page_start": "5",
      "page_end": "5",
      "text_length": "80",
      "confidence": "0.85",
      "needs_human_review": "False",
      "detection_method": "heading_regex",
      "warning": "",
    },
    {
      "case_id": CASE_ID,
      "publication_number": PUB,
      "section_id": f"{PUB}_claims_1",
      "section_type": "claims",
      "section_title": "Claims",
      "section_text": "1. A carbon fiber...",
      "page_start": "1",
      "page_end": "1",
      "text_length": "20",
      "confidence": "0.85",
      "needs_human_review": "False",
      "detection_method": "heading_regex",
      "warning": "",
    },
    {
      "case_id": CASE_ID,
      "publication_number": PUB,
      "section_id": f"{PUB}_unknown_1",
      "section_type": "unknown",
      "section_title": "",
      "section_text": "misc",
      "page_start": "2",
      "page_end": "2",
      "text_length": "4",
      "confidence": "0.3",
      "needs_human_review": "True",
      "detection_method": "page_fallback",
      "warning": "",
    },
  ]
  with path.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
  return path


def test_load_target_sections_filters(tmp_path: Path) -> None:
  csv_path = _sections_csv(tmp_path)
  targets = load_target_sections(csv_path)
  types = {r["section_type"] for r in targets}
  assert "examples" in types
  assert "claims" not in types
  assert "unknown" not in types


def test_build_example_facts_prompt_includes_vocabulary_and_rules() -> None:
  vocab = get_default_extraction_vocabulary("case_01_pan_graphitization")
  section = {
    "publication_number": PUB,
    "section_id": "sec1",
    "section_type": "examples",
    "section_title": "Example 1",
    "section_text": "PAN precursor carbonized at 1200 °C",
    "page_start": "1",
    "page_end": "1",
  }
  prompt = build_example_facts_prompt(section, vocab)
  assert "PAN" in prompt
  assert "carbonization" in prompt
  assert "Do not invent" in prompt
  assert "not a legal analysis" in prompt
  assert "evidence_text" in prompt


def test_parse_and_validate_example_facts() -> None:
  vocab = get_default_extraction_vocabulary("case_01_pan_graphitization")
  source = "The PAN precursor was carbonized at 1200 °C."
  raw = json.dumps({
    "facts": [
      {
        "example_id": "Example 1",
        "fact_type": "process_condition",
        "condition_value": "1200",
        "condition_unit": "°C",
        "evidence_text": "carbonized at 1200 °C",
        "matched_user_keywords": ["PAN"],
        "confidence": 0.9,
      },
      {
        "fact_type": "property_value",
        "evidence_text": "",
        "property_value": "999",
      },
      {
        "fact_type": "bogus_type",
        "evidence_text": "not in source at all",
        "confidence": 1.0,
      },
    ],
  })
  section = {
    "publication_number": PUB,
    "section_id": "sec1",
    "section_type": "examples",
    "section_text": source,
    "page_start": "1",
    "page_end": "1",
  }
  facts = parse_example_facts_json(raw, case_id=CASE_ID, publication_number=PUB, section=section, vocabulary=vocab)
  assert len(facts) == 2  # empty evidence discarded
  assert facts[0].fact_type == "process_condition"
  assert facts[0].needs_human_review is True
  assert "PAN" in facts[0].matched_user_keywords or "carbonization" in facts[0].matched_user_keywords
  assert facts[1].fact_type == "unknown"
  assert facts[1].warning is not None
  assert facts[1].confidence < 1.0


def test_validate_recomputes_matched_keywords() -> None:
  vocab = ExtractionVocabulary(case_id=CASE_ID, material_keywords=["PAN"], process_keywords=["carbonization"])
  fact = ExampleFact(
    case_id=CASE_ID,
    publication_number=PUB,
    section_id="s1",
    section_type="examples",
    fact_id="f1",
    evidence_text="PAN precursor carbonized",
    matched_user_keywords=["fake"],
  )
  validated = validate_example_fact(fact, "PAN precursor carbonized", vocab)
  assert "PAN" in validated.matched_user_keywords


def test_write_example_facts_outputs(tmp_path: Path) -> None:
  from tech_cartography.runtime.v8_example_facts_schema import ExampleFactsExtractionResult

  vocab = get_default_extraction_vocabulary(CASE_ID)
  fact = ExampleFact(
    case_id=CASE_ID,
    publication_number=PUB,
    section_id="s1",
    section_type="examples",
    fact_id="f1",
    evidence_text="test evidence",
    fact_type="property_value",
    property_value="3.5",
    property_unit="GPa",
    matched_user_keywords=["PAN"],
  )
  result = ExampleFactsExtractionResult(
    case_id=CASE_ID,
    publication_number=PUB,
    fact_count=1,
    property_fact_count=1,
    matched_user_keyword_count=1,
    facts=[fact],
    status="ok",
  )
  out_dir = write_example_facts_outputs(CASE_ID, [result], tmp_path / "outputs", vocab, [("s1", "prompt")])
  assert (out_dir / "example_facts.csv").exists()
  assert (out_dir / "example_facts.json").exists()
  assert (out_dir / "example_facts.md").exists()
  assert (out_dir / "example_facts_summary.csv").exists()
  assert (out_dir / "gemini_prompts.md").exists()
  assert (out_dir / "extraction_vocabulary.json").exists()


def test_gemini_disabled_does_not_call_live_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv("ENABLE_GEMINI_EXAMPLE_FACTS", raising=False)
  assert is_gemini_example_facts_enabled() is False
  csv_path = _sections_csv(tmp_path)
  called = {"n": 0}

  def _boom(_prompt: str) -> str:
    called["n"] += 1
    return '{"facts": []}'

  set_gemini_json_generator_for_tests(_boom)
  try:
    out_dir = export_gemini_prompts_only(CASE_ID, csv_path, tmp_path / "outputs", tmp_path)
    assert (out_dir / "gemini_prompts.md").exists()
    assert called["n"] == 0
  finally:
    set_gemini_json_generator_for_tests(None)


def test_fake_provider_parses_facts(tmp_path: Path) -> None:
  from tech_cartography.services.v8_gemini_example_facts import extract_example_facts_from_sections

  csv_path = _sections_csv(tmp_path)
  payload = json.dumps({
    "facts": [{
      "fact_type": "process_condition",
      "evidence_text": "carbonized at 1200 °C",
      "condition_value": "1200",
    }],
  })

  set_gemini_json_generator_for_tests(lambda _p: payload)
  try:
    with patch(
      "tech_cartography.services.v8_gemini_example_facts.is_gemini_example_facts_enabled",
      return_value=True,
    ):
      results, prompts, _vocab = extract_example_facts_from_sections(
        CASE_ID, csv_path, tmp_path / "outputs", tmp_path, use_gemini=True,
      )
    assert prompts
    assert any(r.fact_count >= 1 for r in results)
  finally:
    set_gemini_json_generator_for_tests(None)


def test_no_openai_imports() -> None:
  import tech_cartography.services.v8_gemini_example_facts as mod

  tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
  modules: set[str] = set()
  for node in ast.walk(tree):
    if isinstance(node, ast.Import):
      modules.update(alias.name for alias in node.names)
    elif isinstance(node, ast.ImportFrom) and node.module:
      modules.add(node.module)
  joined = " ".join(modules).lower()
  assert "openai" not in joined
