"""Tests for paper candidate relevance filter (Phase 19.1)."""

from __future__ import annotations

from tech_cartography.evidence.paper_candidate_relevance_filter import (
  apply_relevance_to_paper_records,
  build_selected_evidence_paper_row,
  evaluate_paper_candidate_relevance,
  filter_and_rank_paper_candidates,
  is_synthetic_paper_id,
  load_openalex_paper_records,
  render_paper_candidate_relevance_report,
  save_paper_candidate_relevance_artifacts,
)


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


def _openalex_like_paper() -> dict:
  return {
    "paper_id": "https://openalex.org/W2116590770",
    "openalex_id": "https://openalex.org/W2116590770",
    "title": "Fabrication and Properties of Carbon Fibers",
    "abstract": "polyacrylonitrile precursor carbonization stabilization",
    "doi": "10.3390/ma2042369",
    "publication_year": 2009,
    "source_name": "Materials",
    "cited_by_count": 931,
    "is_open_access": True,
    "concepts": ["Carbon fibers", "Polyacrylonitrile"],
    "keywords": ["carbonization"],
    "query": "PAN carbon fiber",
    "query_type": "material_process",
  }


def test_selected_evidence_papers_keep_real_openalex_fields() -> None:
  paper = _openalex_like_paper()
  result = apply_relevance_to_paper_records([paper], top_n=5)
  selected = result["selected_papers"]
  assert len(selected) == 1
  row = selected[0]
  assert row["title"] == "Fabrication and Properties of Carbon Fibers"
  assert row["doi"] == "10.3390/ma2042369"
  assert row["source"] == "Materials"
  assert int(row["cited_by_count"]) == 931
  assert not is_synthetic_paper_id(str(row["paper_id"]))
  assert "openalex.org" in str(row["paper_id"])


def test_selected_evidence_papers_do_not_use_w1_style_ids() -> None:
  paper = _openalex_like_paper()
  paper["paper_id"] = "W1"
  row = build_selected_evidence_paper_row(paper, {"relevance_bucket": "property_background", "confidence": "low"})
  assert row["paper_id"] == "https://openalex.org/W2116590770"
  assert not is_synthetic_paper_id(row["paper_id"])


def test_broad_composite_background_excluded_from_selected() -> None:
  papers = [
    _openalex_like_paper(),
    {
      "paper_id": "https://openalex.org/W999",
      "title": "Natural Fiber Reinforced Composites: A Review",
      "abstract": "hemp fiber jute fiber general composite applications review",
    },
  ]
  selected = filter_and_rank_paper_candidates(papers, top_n=5)
  buckets = {row["relevance_bucket"] for row in selected}
  assert "broad_composite_background" not in buckets


def test_likely_off_topic_excluded_from_selected() -> None:
  papers = [
    _openalex_like_paper(),
    {
      "paper_id": "https://openalex.org/W888",
      "title": "Quantum computing error correction",
      "abstract": "qubit decoherence",
    },
  ]
  selected = filter_and_rank_paper_candidates(papers, top_n=5)
  buckets = {row["relevance_bucket"] for row in selected}
  assert "likely_off_topic" not in buckets


def test_load_openalex_paper_records_prefers_json_over_synthetic_csv(tmp_path) -> None:
  csv_path = tmp_path / "openalex_paper_records.csv"
  csv_path.write_text(
    "paper_id,title,abstract\nW1,sample title,sample abstract\n",
    encoding="utf-8",
  )
  json_path = tmp_path / "openalex_paper_records.json"
  json_path.write_text(
    '[{"paper_id":"https://openalex.org/W2116590770","title":"Fabrication and Properties of Carbon Fibers","abstract":"pan carbon fiber"}]',
    encoding="utf-8",
  )
  records = load_openalex_paper_records(csv_path)
  assert len(records) == 1
  assert records[0]["title"] == "Fabrication and Properties of Carbon Fibers"
  assert "openalex.org" in records[0]["paper_id"]
