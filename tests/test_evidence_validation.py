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
