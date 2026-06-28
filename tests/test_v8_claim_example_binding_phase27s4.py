"""Tests for Phase27S.4 claim-example binding."""

from __future__ import annotations

import ast
import csv
from pathlib import Path

import pytest

from tech_cartography.runtime.v8_extraction_vocabulary_schema import ExtractionVocabulary
from tech_cartography.services.v8_claim_example_binding import (
  bind_claims_to_example_facts,
  find_latest_example_facts_output,
  group_example_facts_by_publication_and_example,
  load_example_facts,
  score_claim_example_candidate,
  write_claim_example_binding_outputs,
)

CASE_ID = "test_case_cebind"
PUB_A = "CN108286090A"
PUB_B = "CN117987966A"


def _write_example_facts_csv(path: Path) -> None:
  fields = [
    "case_id", "publication_number", "section_id", "section_type", "example_id", "example_label",
    "fact_id", "fact_type", "material", "process_step", "condition_name", "condition_value",
    "condition_unit", "property_name", "property_value", "property_unit", "comparison_type",
    "comparison_target", "table_id", "evidence_text", "matched_user_keywords", "page_start",
    "page_end", "confidence", "needs_human_review", "extraction_method", "warning",
  ]
  rows = [
    {
      "case_id": CASE_ID,
      "publication_number": PUB_A,
      "section_id": "s1",
      "section_type": "examples",
      "example_id": "Example 1",
      "example_label": "Example 1",
      "fact_id": "f1",
      "fact_type": "process_condition",
      "material": "PAN precursor",
      "process_step": "carbonization",
      "condition_name": "temperature",
      "condition_value": "1200",
      "condition_unit": "C",
      "property_name": "",
      "property_value": "",
      "property_unit": "",
      "comparison_type": "",
      "comparison_target": "",
      "table_id": "",
      "evidence_text": "The PAN precursor was carbonized at 1200 C.",
      "matched_user_keywords": "PAN|carbonization",
      "page_start": "1",
      "page_end": "1",
      "confidence": "0.75",
      "needs_human_review": "True",
      "extraction_method": "gemini",
      "warning": "",
    },
    {
      "case_id": CASE_ID,
      "publication_number": PUB_B,
      "section_id": "s2",
      "section_type": "examples",
      "example_id": "Example 1",
      "example_label": "Example 1",
      "fact_id": "f2",
      "fact_type": "property_value",
      "material": "",
      "process_step": "",
      "condition_name": "",
      "condition_value": "",
      "condition_unit": "",
      "property_name": "tensile strength",
      "property_value": "5.3",
      "property_unit": "GPa",
      "comparison_type": "",
      "comparison_target": "",
      "table_id": "",
      "evidence_text": "tensile strength of 5.3GPa",
      "matched_user_keywords": "tensile strength",
      "page_start": "2",
      "page_end": "2",
      "confidence": "0.75",
      "needs_human_review": "True",
      "extraction_method": "gemini",
      "warning": "",
    },
    {
      "case_id": CASE_ID,
      "publication_number": PUB_A,
      "section_id": "s3",
      "section_type": "examples",
      "example_id": "Example 2",
      "example_label": "Example 2",
      "fact_id": "f3",
      "fact_type": "comparison_example",
      "material": "",
      "process_step": "",
      "condition_name": "",
      "condition_value": "",
      "condition_unit": "",
      "property_name": "",
      "property_value": "",
      "property_unit": "",
      "comparison_type": "comparative",
      "comparison_target": "control",
      "table_id": "",
      "evidence_text": "",
      "matched_user_keywords": "",
      "page_start": "3",
      "page_end": "3",
      "confidence": "0.5",
      "needs_human_review": "True",
      "extraction_method": "gemini",
      "warning": "",
    },
  ]
  with path.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)


def _setup_case(tmp_path: Path) -> Path:
  case_dir = tmp_path / "cases" / CASE_ID
  case_dir.mkdir(parents=True)
  claims_path = case_dir / "claims_input.csv"
  claims_path.write_text(
    "case_id,publication_number,patent_title,claim_no,claim_text,claim_source_type,claim_source_url,claim_source_path,notes\n"
    f"{CASE_ID},{PUB_A},Title,1,\"A PAN precursor carbonization method at 1200 C.\",manual,,,\n"
    f"{CASE_ID},{PUB_B},Title,1,\"A fiber with tensile strength 5.3GPa.\",manual,,,\n",
    encoding="utf-8",
  )
  facts_dir = tmp_path / "outputs" / "local_v8_example_facts" / f"{CASE_ID}_test_abc12345"
  facts_dir.mkdir(parents=True)
  _write_example_facts_csv(facts_dir / "example_facts.csv")
  (facts_dir / "example_facts_summary.csv").write_text(
    "case_id,publication_number,status,fact_count\n"
    f"{CASE_ID},{PUB_A},ok,1\n"
    f"{CASE_ID},{PUB_B},ok,1\n",
    encoding="utf-8",
  )
  return facts_dir


def test_find_latest_example_facts_output(tmp_path: Path) -> None:
  _setup_case(tmp_path)
  found = find_latest_example_facts_output(CASE_ID, tmp_path / "outputs")
  assert found is not None
  assert (found / "example_facts.csv").exists()


def test_group_by_publication_only_same_pub(tmp_path: Path) -> None:
  facts_dir = _setup_case(tmp_path)
  facts = load_example_facts(facts_dir / "example_facts.csv")
  grouped = group_example_facts_by_publication_and_example(facts)
  assert PUB_A in grouped
  assert PUB_B in grouped
  assert len(grouped[PUB_A]["Example 1"]) == 1


def test_no_cross_publication_binding(tmp_path: Path) -> None:
  _setup_case(tmp_path)
  results = bind_claims_to_example_facts(CASE_ID, tmp_path, tmp_path / "outputs")
  by_pub = {r.publication_number: r for r in results if r.publication_number}
  assert PUB_A in by_pub
  assert PUB_B in by_pub
  link_a = by_pub[PUB_A].links[0]
  assert all("PAN" in ev or "carbon" in ev.lower() for ev in link_a.evidence_texts) or link_a.support_level != "none"


def test_property_support_candidate(tmp_path: Path) -> None:
  _setup_case(tmp_path)
  results = bind_claims_to_example_facts(CASE_ID, tmp_path, tmp_path / "outputs")
  pub_b = next(r for r in results if r.publication_number == PUB_B)
  link = pub_b.links[0]
  assert link.support_type == "property_support_candidate"


def test_process_condition_candidate(tmp_path: Path) -> None:
  vocab = ExtractionVocabulary(case_id=CASE_ID, material_keywords=["PAN"], process_keywords=["carbonization"])
  claim = {
    "case_id": CASE_ID,
    "publication_number": PUB_A,
    "claim_no": "1",
    "claim_text": "PAN precursor carbonization at high temperature",
  }
  facts = [{
    "publication_number": PUB_A,
    "fact_id": "f1",
    "fact_type": "process_condition",
    "material": "PAN precursor",
    "process_step": "carbonization",
    "evidence_text": "PAN precursor carbonized",
    "matched_user_keywords": "PAN|carbonization",
  }]
  score, link = score_claim_example_candidate(claim, facts, vocab)
  assert score >= 2
  assert link.support_type == "process_support_candidate"


def test_no_match_no_example_support(tmp_path: Path) -> None:
  vocab = ExtractionVocabulary(case_id=CASE_ID)
  claim = {
    "case_id": CASE_ID,
    "publication_number": PUB_A,
    "claim_no": "99",
    "claim_text": "unrelated quantum widget",
  }
  _, link = score_claim_example_candidate(claim, [], vocab)
  assert link.support_type == "no_example_support_candidate"
  assert link.support_level == "none"


def test_missing_elements_created() -> None:
  vocab = ExtractionVocabulary(
    case_id=CASE_ID,
    property_keywords=["tensile modulus"],
    process_keywords=["graphitization"],
  )
  claim = {
    "case_id": CASE_ID,
    "publication_number": PUB_A,
    "claim_no": "1",
    "claim_text": "graphitization and tensile modulus control",
  }
  facts = [{
    "publication_number": PUB_A,
    "fact_id": "f1",
    "fact_type": "process_condition",
    "process_step": "graphitization",
    "evidence_text": "graphitization step",
    "matched_user_keywords": "graphitization",
  }]
  _, link = score_claim_example_candidate(claim, facts, vocab)
  assert "tensile modulus" in link.missing_elements or any("tensile" in m for m in link.missing_elements)


def test_write_outputs(tmp_path: Path) -> None:
  _setup_case(tmp_path)
  results = bind_claims_to_example_facts(CASE_ID, tmp_path, tmp_path / "outputs")
  out_dir = write_claim_example_binding_outputs(CASE_ID, results, tmp_path / "outputs")
  assert (out_dir / "claim_example_links.csv").exists()
  assert (out_dir / "claim_example_links.json").exists()
  assert (out_dir / "claim_example_links.md").exists()
  assert (out_dir / "claim_example_binding_summary.csv").exists()
  assert (out_dir / "claim_example_review_prompts.md").exists()


def test_facts_without_evidence_excluded(tmp_path: Path) -> None:
  facts_dir = _setup_case(tmp_path)
  grouped = group_example_facts_by_publication_and_example(load_example_facts(facts_dir / "example_facts.csv"))
  assert "Example 2" not in grouped.get(PUB_A, {})


def test_no_llm_imports() -> None:
  import tech_cartography.services.v8_claim_example_binding as mod

  tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
  modules: set[str] = set()
  for node in ast.walk(tree):
    if isinstance(node, ast.Import):
      modules.update(alias.name for alias in node.names)
    elif isinstance(node, ast.ImportFrom) and node.module:
      modules.add(node.module)
  joined = " ".join(modules).lower()
  assert "openai" not in joined
  assert "v8_llm_provider_gemini" not in joined
