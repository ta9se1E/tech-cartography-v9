from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from tech_cartography.validation.evidence_validation import run_evidence_validation


def test_zero_ready_records_returns_limited_no_fulltext(tmp_path: Path) -> None:
  records = [
    {
      "publication_number": "US-1",
      "country": "US",
      "retrieval_status": "dry_run_only",
      "evidence_level": "metadata_only",
    },
  ]
  manual = [{"publication_number": "CN-1", "country": "CN", "title": "PAN fiber"}]
  result = run_evidence_validation(
    records,
    manual_candidates=manual,
    output_dir=str(tmp_path / "out"),
  )
  assert result["status"] == "limited_no_fulltext"
  assert result["manual_candidates"] == manual
  assert result["output_paths"]


def test_ready_records_generate_claim_elements(tmp_path: Path) -> None:
  records = [
    {
      "publication_number": "US-2",
      "title": "Carbon fiber",
      "country": "US",
      "retrieval_status": "retrieved",
      "claims": "1. A carbon fiber bundle comprising PAN precursor fibers.",
      "description": "The bundle is carbonized in nitrogen atmosphere.",
      "evidence_level": "high_fulltext_evidence",
    },
  ]
  result = run_evidence_validation(records, output_dir=str(tmp_path / "ready"))
  assert result["status"] in {"success", "partial_success"}
  assert len(result["claim_element_result"]["elements"]) > 0
  assert Path(result["output_paths"]["claim_elements_csv"]).exists()


def test_execute_openalex_false_does_not_call_api(tmp_path: Path) -> None:
  records = [
    {
      "publication_number": "US-3",
      "title": "Carbon fiber process",
      "country": "US",
      "retrieval_status": "retrieved",
      "claims": "1. A method for manufacturing carbon fiber by stabilization and carbonization.",
      "description": "The method uses PAN precursor and heat treatment.",
      "evidence_level": "medium_fulltext_evidence",
    },
  ]
  with patch("tech_cartography.retrieval.openalex_retriever._fetch_openalex_json") as fetch_mock:
    result = run_evidence_validation(records, execute_openalex=False, output_dir=str(tmp_path / "plan"))
  fetch_mock.assert_not_called()
  assert result["openalex_result"]["mode"] == "plan_only"
  assert result["openalex_result"]["executed_queries"] == 0


def test_manual_claims_loaded_is_ready_for_claim_extraction(tmp_path: Path) -> None:
  records = [
    {
      "publication_number": "US-12565719-B2",
      "title": "Carbon fiber",
      "country": "US",
      "retrieval_status": "manual_claims_loaded",
      "claims": "1. A carbon fiber comprising PAN precursor fibers with tensile strength above 5 GPa.",
      "evidence_level": "low_fulltext_evidence",
      "evidence_coverage": {
        "description_support": "limited_no_description",
        "examples_support": "not_available",
      },
    },
  ]
  result = run_evidence_validation(records, output_dir=str(tmp_path / "manual"))
  readiness = result["fulltext_readiness"]
  assert readiness["ready_count"] >= 1
  assert len(result["claim_element_result"]["elements"]) > 0
  assert Path(result["output_paths"]["claim_elements_from_manual_fulltext_csv"]).exists()


def test_manual_claims_without_description_uses_limited_no_description(tmp_path: Path) -> None:
  records = [
    {
      "publication_number": "US-4",
      "country": "US",
      "retrieval_status": "manual_claims_loaded",
      "claims": "1. A carbon fiber bundle.",
      "evidence_level": "low_fulltext_evidence",
      "evidence_coverage": {
        "description_support": "limited_no_description",
        "examples_support": "not_available",
      },
    },
  ]
  result = run_evidence_validation(records, output_dir=str(tmp_path / "limited"))
  classified = result["fulltext_readiness"]["classified_records"][0]
  assert classified["readiness_status"] == "ready_for_claim_extraction"
  coverage = records[0]["evidence_coverage"]
  assert coverage["description_support"] == "limited_no_description"
  assert coverage["examples_support"] == "not_available"


def test_manual_claims_loaded_emits_claims_paper_query_candidates(tmp_path: Path) -> None:
  records = [
    {
      "publication_number": "US-12565719-B2",
      "title": "Carbon fiber",
      "country": "US",
      "retrieval_status": "manual_claims_loaded",
      "claims": (
        "1. A carbon fiber comprising PAN precursor fibers subjected to oxidation and carbonization, "
        "wherein the carbon fiber has a tensile strength and elastic modulus."
      ),
      "evidence_level": "low_fulltext_evidence",
      "manual_route": True,
    },
  ]
  result = run_evidence_validation(records, output_dir=str(tmp_path / "claims_queries"))
  plan = result.get("claims_paper_query_plan") or {}
  assert plan.get("total_queries", 0) > 0
  assert Path(result["output_paths"]["paper_query_candidates_from_claims_csv"]).exists()
  assert Path(result["output_paths"]["paper_query_quality_report_md"]).exists()
  assert result["claims_paper_query_plan"].get("plan_ready_for_openalex") is True
  joined = " ".join(plan.get("query_examples", [])).lower()
  assert "carbon" in joined or "pan" in joined


def test_metadata_only_claims_plan_uses_low_confidence_fallback(tmp_path: Path) -> None:
  records = [
    {
      "publication_number": "US-9",
      "title": "PAN carbon fiber manufacturing",
      "abstract": "oxidation carbonization tensile strength",
      "country": "US",
      "retrieval_status": "dry_run_only",
      "evidence_level": "metadata_only",
    },
  ]
  plan = run_evidence_validation(records, output_dir=str(tmp_path / "meta"))["claims_paper_query_plan"]
  if plan.get("queries"):
    assert all(row.get("confidence") == "low" for row in plan["queries"])
