"""Tests for paper candidate relevance filter (Phase 19.1)."""

from __future__ import annotations

from tech_cartography.evidence.paper_candidate_relevance_filter import (
  evaluate_paper_candidate_relevance,
  filter_and_rank_paper_candidates,
  render_paper_candidate_relevance_report,
  save_paper_candidate_relevance_artifacts,
)
from tech_cartography.evidence.paper_candidate_relevance_filter import apply_relevance_to_paper_records


def test_pan_carbonization_is_strong_material_process_background() -> None:
  paper = {
    "title": "PAN precursor oxidation and carbonization for high performance carbon fiber",
    "abstract": "polyacrylonitrile stabilization heat treatment manufacturing",
  }
  result = evaluate_paper_candidate_relevance(paper)
  assert result["relevance_bucket"] == "strong_material_process_background"
  assert result["confidence"] != "high"
  assert "carbonization" in result["matched_positive_terms"] or "pan" in result["matched_positive_terms"]


def test_tensile_modulus_is_property_background() -> None:
  paper = {
    "title": "Tensile strength and elastic modulus of carbon fiber bundles",
    "abstract": "mechanical properties measurement of carbon fiber",
  }
  result = evaluate_paper_candidate_relevance(paper)
  assert result["relevance_bucket"] == "property_background"


def test_surface_interphase_is_surface_interface_background() -> None:
  paper = {
    "title": "Fiber/matrix interphase engineering and sizing for carbon fiber composites",
    "abstract": "surface treatment interfacial adhesion modification",
  }
  result = evaluate_paper_candidate_relevance(paper)
  assert result["relevance_bucket"] == "surface_interface_background"


def test_natural_fiber_review_is_broad_or_weak() -> None:
  paper = {
    "title": "Natural Fiber Reinforced Composites: A Review",
    "abstract": "hemp fiber jute fiber general composite applications",
  }
  result = evaluate_paper_candidate_relevance(paper)
  assert result["relevance_bucket"] in {"broad_composite_background", "weak_background", "likely_off_topic"}


def test_glass_fiber_review_is_broad_background() -> None:
  paper = {
    "title": "Carbon/Glass Fiber-Reinforced Polymer Composites review",
    "abstract": "glass fiber reinforced polymer composites review",
  }
  result = evaluate_paper_candidate_relevance(paper)
  assert result["relevance_bucket"] in {"broad_composite_background", "weak_background"}


def test_unrelated_paper_is_likely_off_topic() -> None:
  paper = {
    "title": "Quantum computing error correction algorithms",
    "abstract": "qubit decoherence machine learning drug discovery",
  }
  result = evaluate_paper_candidate_relevance(paper)
  assert result["relevance_bucket"] == "likely_off_topic"


def test_selected_evidence_papers_respect_top_n() -> None:
  papers = [
    {
      "title": "PAN carbonization carbon fiber oxidation",
      "abstract": "polyacrylonitrile precursor stabilization",
    },
    {
      "title": "Tensile strength elastic modulus carbon fiber",
      "abstract": "mechanical properties",
    },
    {
      "title": "Natural Fiber Reinforced Composites review",
      "abstract": "natural fiber hemp",
    },
    {
      "title": "Quantum computing",
      "abstract": "qubit",
    },
    {
      "title": "Surface sizing interfacial adhesion carbon fiber",
      "abstract": "surface treatment",
    },
    {
      "title": "Carbon fiber microstructure defects",
      "abstract": "microstructure crystallite",
    },
  ]
  selected = filter_and_rank_paper_candidates(papers, top_n=3)
  assert len(selected) <= 3
  buckets = {row["relevance_bucket"] for row in selected}
  assert "likely_off_topic" not in buckets


def test_no_high_confidence() -> None:
  paper = {
    "title": "PAN carbon fiber carbonization oxidation stabilization",
    "abstract": "polyacrylonitrile precursor heat treatment",
  }
  result = evaluate_paper_candidate_relevance(paper, has_description=False)
  assert result["confidence"] in {"medium", "low", "weak"}
  assert result["confidence"] != "high"


def test_caveat_present() -> None:
  paper = {"title": "PAN carbon fiber", "abstract": "carbonization"}
  result = evaluate_paper_candidate_relevance(paper)
  assert result.get("caveat_japanese")
  report = render_paper_candidate_relevance_report([result], [paper])
  assert "supporting evidence" in report.lower() or "Evidence Map" in report
  assert "$" not in report


def test_save_artifacts(tmp_path) -> None:
  papers = [{"title": "PAN carbon fiber carbonization", "abstract": "oxidation"}]
  result = apply_relevance_to_paper_records(papers, top_n=5)
  paths = save_paper_candidate_relevance_artifacts(result, tmp_path)
  assert paths["selected_evidence_papers_csv"]
  assert paths["paper_candidate_relevance_report_md"]
