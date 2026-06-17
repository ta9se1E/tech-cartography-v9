"""Tests for evidence map synthesis report (Phase 20)."""

from __future__ import annotations

import json
from pathlib import Path

from tech_cartography.evidence.evidence_map_synthesizer import EvidenceMapItem, EvidenceMapSynthesis
from tech_cartography.reports.evidence_map_synthesis_report import (
  render_evidence_map_synthesis_markdown,
  save_evidence_map_synthesis_artifacts,
)


def _sample_synthesis() -> EvidenceMapSynthesis:
  return EvidenceMapSynthesis(
    publication_number="US-12565719-B2",
    title="Carbon fiber manufacturing",
    assignee="Toray",
    retrieval_route="manual_claims_loaded",
    evidence_level="low_fulltext_evidence",
    claim_element_count=2,
    paper_query_count=10,
    paper_candidate_count=5,
    selected_evidence_paper_count=3,
    claim_paper_link_count=2,
    synthesis_status="ready_with_selected_papers",
    key_findings_japanese=["manual claimsからClaim Elementを抽出しました。"],
    evidence_gaps_japanese=["明細書が未入力です。"],
    next_actions_japanese=["descriptionをmanualで追加する"],
    caveats_japanese=["論文候補は supporting evidence candidate です。"],
    selected_evidence_papers=[
      {
        "title": "Fabrication and Properties of Carbon Fibers",
        "doi": "10.3390/ma2042369",
        "source": "Materials",
        "cited_by_count": 931,
        "relevance_bucket": "strong_material_process_background",
      },
    ],
    evidence_map_items=[
      EvidenceMapItem(
        publication_number="US-12565719-B2",
        claim_element_id="e1",
        element_type="material",
        element_text="PAN precursor",
        best_paper_title="Fabrication and Properties of Carbon Fibers",
        best_paper_doi="10.3390/ma2042369",
        best_paper_source="Materials",
        best_paper_cited_by_count=931,
        confidence="low",
        evidence_role="supporting_evidence_candidate",
      ),
    ],
    element_type_counts={"material": 1, "property": 1},
  )


def test_markdown_generation() -> None:
  md = render_evidence_map_synthesis_markdown(_sample_synthesis())
  assert "# Evidence Map Synthesis" in md
  assert "supporting evidence candidate" in md.lower()
  assert "US-12565719-B2" in md
  assert "Evidence Gaps" in md


def test_save_json_and_csv(tmp_path: Path) -> None:
  paths = save_evidence_map_synthesis_artifacts(_sample_synthesis(), tmp_path)
  assert Path(paths["evidence_map_synthesis_json"]).exists()
  assert Path(paths["evidence_map_synthesis_md"]).exists()
  assert Path(paths["evidence_map_items_csv"]).exists()
  payload = json.loads(Path(paths["evidence_map_synthesis_json"]).read_text(encoding="utf-8"))
  assert payload["synthesis_status"] == "ready_with_selected_papers"


def test_no_monetary_amounts_in_report() -> None:
  md = render_evidence_map_synthesis_markdown(_sample_synthesis())
  assert "$" not in md
  assert "usd" not in md.lower()


def test_real_paper_title_and_doi_in_report() -> None:
  md = render_evidence_map_synthesis_markdown(_sample_synthesis())
  assert "Fabrication and Properties of Carbon Fibers" in md
  assert "10.3390/ma2042369" in md
  assert "931" in md
  assert "supporting evidence candidate" in md.lower()
