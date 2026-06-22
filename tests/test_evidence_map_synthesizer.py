"""Tests for evidence map synthesizer (Phase 20)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tech_cartography.evidence.evidence_map_synthesizer import (
  build_evidence_map_items,
  build_evidence_map_synthesis,
  classify_synthesis_status,
)
from tech_cartography.reports.project_export import save_records_csv

PUBLICATION_NUMBER = "US-12565719-B2"


@pytest.fixture
def claim_elements() -> list[dict]:
  return [
    {
      "element_id": "e1",
      "element_type": "material",
      "element_text": "PAN precursor carbon fiber carbonization",
      "publication_number": PUBLICATION_NUMBER,
    },
    {
      "element_id": "e2",
      "element_type": "property",
      "element_text": "tensile strength elastic modulus",
      "publication_number": PUBLICATION_NUMBER,
    },
  ]


def _write_claim_elements(workspace: Path, claim_elements: list[dict]) -> None:
  claims_dir = workspace / "outputs" / "claims_paper_query_plans" / PUBLICATION_NUMBER
  claims_dir.mkdir(parents=True, exist_ok=True)
  save_records_csv(claim_elements, claims_dir / "claim_elements.csv")


def _write_manual_input(workspace: Path, *, claims_text: str, description_text: str | None = None) -> None:
  manual_dir = workspace / "outputs" / "manual_fulltext_inputs"
  manual_dir.mkdir(parents=True, exist_ok=True)
  payload = {
    "publication_number": PUBLICATION_NUMBER,
    "claims_text": claims_text,
    "description_text": description_text,
  }
  (manual_dir / f"{PUBLICATION_NUMBER}.json").write_text(
    json.dumps(payload, ensure_ascii=False),
    encoding="utf-8",
  )


@pytest.fixture
def openalex_dir(tmp_path: Path, claim_elements: list[dict]) -> Path:
  papers = [
    {
      "paper_id": "https://openalex.org/W2116590770",
      "openalex_id": "https://openalex.org/W2116590770",
      "title": "Fabrication and Properties of Carbon Fibers",
      "abstract": "polyacrylonitrile stabilization carbonization",
      "doi": "10.3390/ma2042369",
      "source": "Materials",
      "publication_year": 2009,
      "cited_by_count": 931,
      "relevance_bucket": "strong_material_process_background",
      "relevance_score": 0.9,
    },
    {
      "paper_id": "https://openalex.org/W888",
      "openalex_id": "https://openalex.org/W888",
      "title": "Effect of amorphous carbon on tensile behavior of PAN-based carbon fibers",
      "abstract": "tensile strength elastic modulus mechanical properties",
      "doi": "10.1000/example",
      "source": "Composites Science",
      "publication_year": 2015,
      "cited_by_count": 120,
      "relevance_bucket": "property_background",
      "relevance_score": 0.95,
    },
  ]
  all_papers = papers + [
    {
      "paper_id": "https://openalex.org/W999",
      "title": "Natural Fiber Reinforced Composites review",
      "abstract": "hemp fiber",
      "relevance_bucket": "broad_composite_background",
    },
  ]
  oa_dir = tmp_path / "openalex"
  oa_dir.mkdir()
  save_records_csv(all_papers, oa_dir / "openalex_paper_records.csv")
  save_records_csv(papers, oa_dir / "selected_evidence_papers.csv")
  relevance = [
    {
      "work_id": "https://openalex.org/W2116590770",
      "title": papers[0]["title"],
      "relevance_bucket": "strong_material_process_background",
      "relevance_score": 0.9,
      "confidence": "low",
    },
    {
      "work_id": "W2",
      "title": "Natural Fiber Reinforced Composites review",
      "relevance_bucket": "broad_composite_background",
      "relevance_score": 0.0,
      "confidence": "weak",
    },
  ]
  save_records_csv(relevance, oa_dir / "paper_candidate_relevance.csv")
  links = [
    {
      "element_id": "e1",
      "claim_element_id": "e1",
      "element_type": "material",
      "paper_id": "https://openalex.org/W2116590770",
      "paper_title": papers[0]["title"],
      "paper_doi": "10.3390/ma2042369",
      "paper_source": "Materials",
      "paper_year": 2009,
      "cited_by_count": 931,
      "link_type": "material_process_background",
      "confidence": "low",
      "relevance_bucket": "strong_material_process_background",
      "link_score": 0.5,
      "evidence_role": "supporting_evidence_candidate",
    },
  ]
  save_records_csv(links, oa_dir / "claim_paper_candidate_links.csv")
  _write_claim_elements(tmp_path, claim_elements)
  _write_manual_input(tmp_path, claims_text="1. A carbon fiber.")
  return oa_dir


@pytest.fixture
def isolated_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
  monkeypatch.chdir(tmp_path)
  return tmp_path


def test_synthesis_with_selected_papers(
  isolated_workspace: Path,
  openalex_dir: Path,
) -> None:
  synthesis = build_evidence_map_synthesis(
    None,
    PUBLICATION_NUMBER,
    openalex_dir,
  )
  assert synthesis.synthesis_status == "ready_with_selected_papers"
  assert synthesis.selected_evidence_paper_count == 2
  assert synthesis.paper_candidate_count >= 2
  assert all(item.confidence != "high" for item in synthesis.evidence_map_items)
  assert synthesis.caveats_japanese


def test_build_items_from_elements_and_papers(claim_elements: list[dict], openalex_dir: Path) -> None:
  from tech_cartography.reports.project_export import load_records_csv

  selected = load_records_csv(str(openalex_dir / "selected_evidence_papers.csv"))
  items = build_evidence_map_items(claim_elements, [], selected, publication_number=PUBLICATION_NUMBER)
  assert len(items) == 2
  assert any(item.best_paper_title for item in items)


def test_weak_no_selected_papers(
  isolated_workspace: Path,
  claim_elements: list[dict],
) -> None:
  _write_claim_elements(isolated_workspace, claim_elements)
  _write_manual_input(isolated_workspace, claims_text="1. A carbon fiber.")
  synthesis = build_evidence_map_synthesis(None, PUBLICATION_NUMBER, None)
  assert synthesis.synthesis_status in {
    "weak_no_selected_papers",
    "manual_description_recommended",
    "ready_limited_claims_only",
  }


def test_blocked_no_claims(isolated_workspace: Path) -> None:
  status = classify_synthesis_status(
    claim_element_count=0,
    paper_candidate_count=0,
    selected_evidence_paper_count=0,
    has_claims=False,
    has_description=False,
  )
  assert status == "blocked_no_claims"
  synthesis = build_evidence_map_synthesis(None, PUBLICATION_NUMBER, None)
  assert synthesis.synthesis_status == "blocked_no_claims"


def test_manual_description_in_next_actions(
  isolated_workspace: Path,
  openalex_dir: Path,
) -> None:
  synthesis = build_evidence_map_synthesis(None, PUBLICATION_NUMBER, openalex_dir)
  joined = " ".join(synthesis.next_actions_japanese)
  assert "description" in joined.lower() or "明細書" in joined


def test_no_high_confidence_in_items(claim_elements: list[dict]) -> None:
  items = build_evidence_map_items(
    claim_elements,
    [
      {
        "element_id": "e1",
        "confidence": "medium",
        "paper_title": "Fabrication and Properties of Carbon Fibers",
        "paper_doi": "10.3390/ma2042369",
        "paper_source": "Materials",
        "cited_by_count": 931,
        "link_type": "material_process_background",
        "relevance_bucket": "strong_material_process_background",
        "link_score": 0.6,
      },
    ],
    [],
    publication_number=PUBLICATION_NUMBER,
  )
  assert all(item.confidence != "high" for item in items)


def test_items_use_claim_paper_links_with_real_metadata(
  openalex_dir: Path,
  claim_elements: list[dict],
) -> None:
  from tech_cartography.reports.project_export import load_records_csv

  links = load_records_csv(str(openalex_dir / "claim_paper_candidate_links.csv"))
  selected = load_records_csv(str(openalex_dir / "selected_evidence_papers.csv"))
  items = build_evidence_map_items(claim_elements, links, selected, publication_number=PUBLICATION_NUMBER)
  material_item = next(item for item in items if item.element_type == "material")
  assert "Fabrication and Properties of Carbon Fibers" in (material_item.best_paper_title or "")
  assert material_item.best_paper_doi == "10.3390/ma2042369"
  assert material_item.best_paper_cited_by_count == 931


def test_no_claim_paper_gap_when_links_exist(
  isolated_workspace: Path,
  openalex_dir: Path,
) -> None:
  from tech_cartography.evidence.evidence_map_synthesizer import build_evidence_gaps_japanese

  synthesis = build_evidence_map_synthesis(None, PUBLICATION_NUMBER, openalex_dir)
  gaps = build_evidence_gaps_japanese(
    has_description=False,
    has_examples=False,
    retrieval_route="manual",
    selected_count=synthesis.selected_evidence_paper_count,
    link_count=synthesis.claim_paper_link_count,
    claim_element_count=synthesis.claim_element_count,
  )
  assert synthesis.claim_paper_link_count > 0
  assert not any("Claim × Paper linkが未作成" in gap for gap in gaps)
