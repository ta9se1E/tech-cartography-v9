"""Tests for synthesis agent."""

from tech_cartography.agents.synthesis_agent import (
  build_executive_summary,
  build_key_findings,
  run_synthesis_report,
)


def _fixture_inputs() -> dict:
  cluster_summary = [
    {
      "cluster_id": "bundle_prepreg",
      "name": "bundle_prepreg",
      "description": "Carbon fiber bundle and prepreg",
      "patent_count": 5,
      "representative_terms": ["prepreg", "tow"],
      "top_assignees": ["TORAY"],
      "representative_patents": ["US1", "US2"],
    },
  ]
  top20 = [
    {
      "publication_number": "US1",
      "title": "Carbon fiber prepreg",
      "assignee": "TORAY",
      "primary_cluster_id": "bundle_prepreg",
      "rank": 1,
      "noise_score": 0.0,
    },
    {
      "publication_number": "US2",
      "title": "Surface treatment",
      "assignee": "TEIJIN",
      "primary_cluster_id": "surface_interface",
      "rank": 8,
      "noise_score": 0.1,
    },
  ]
  top5 = [{"publication_number": "US1"}]
  technical_assessments = [
    {
      "publication_number": "US1",
      "overall_technical_confidence": "high",
      "overall_technical_score": 0.8,
      "strongest_supported_points": ["paper evidence candidate for interface"],
      "recommended_reader_action": "read_patent_and_examples_first",
    },
  ]
  patent_technical_summary = [
    {
      "publication_number": "US1",
      "patent_title": "Carbon fiber prepreg",
      "assignee": "TORAY",
      "primary_cluster_id": "bundle_prepreg",
      "overall_technical_confidence": "high",
      "overall_technical_score": 0.8,
      "strongest_supported_points": ["paper evidence candidate for interface"],
      "key_evidence_gaps": [],
    },
    {
      "publication_number": "US2",
      "patent_title": "Surface treatment",
      "overall_technical_confidence": "low",
      "overall_technical_score": 0.2,
    },
  ]
  business_assessments = [
    {
      "publication_number": "US1",
      "assignee": "TORAY",
      "primary_cluster_id": "bundle_prepreg",
      "overall_business_confidence": "high",
      "overall_business_score": 0.75,
      "commercialization_signals": ["production expansion signal candidate"],
      "sme_opportunity_points": [],
      "design_around_or_differentiation_hints": [],
      "recommended_reader_action": "monitor_company_signals",
      "assessment_items": [],
    },
  ]
  patent_business_summary = [
    {
      "publication_number": "US1",
      "overall_business_confidence": "high",
      "recommended_reader_action": "monitor_company_signals",
      "primary_cluster_id": "bundle_prepreg",
    },
    {
      "publication_number": "US2",
      "overall_business_confidence": "low",
      "recommended_reader_action": "monitor_only",
    },
  ]
  return {
    "cluster_summary": cluster_summary,
    "top20": top20,
    "top5": top5,
    "technical_assessments": technical_assessments,
    "patent_technical_summary": patent_technical_summary,
    "business_assessments": business_assessments,
    "patent_business_summary": patent_business_summary,
  }


def test_run_synthesis_report_priority_and_findings() -> None:
  data = _fixture_inputs()
  result = run_synthesis_report(
    data["cluster_summary"],
    data["top20"],
    data["top5"],
    data["technical_assessments"],
    data["patent_technical_summary"],
    data["business_assessments"],
    data["patent_business_summary"],
    claim_paper_summary={"supporting_evidence_candidates": 2, "background_evidence": 1},
    web_signals_by_company=[{"normalized_company": "TORAY", "signal_count": 2, "linked_patents": "US1"}],
    theme="PAN系炭素繊維",
  )
  assert result["status"] == "ok"
  assert result["priority_patents"][0]["publication_number"] == "US1"
  finding_types = {f["finding_type"] for f in result["key_findings"]}
  assert "priority_patent" in finding_types
  assert "business_signal_candidate" in finding_types


def test_human_review_finding_with_gaps() -> None:
  data = _fixture_inputs()
  gaps = [
    {"publication_number": "US1", "gap_type": "no_paper_found"},
    {"publication_number": "US1", "gap_type": "weak_only"},
    {"publication_number": "US1", "gap_type": "background_only"},
  ]
  result = run_synthesis_report(
    data["cluster_summary"],
    data["top20"],
    data["top5"],
    data["technical_assessments"],
    data["patent_technical_summary"],
    data["business_assessments"],
    data["patent_business_summary"],
    evidence_gaps=gaps,
  )
  finding_types = {f["finding_type"] for f in result["key_findings"]}
  assert "human_review_required" in finding_types


def test_executive_summary_avoids_proof_language() -> None:
  data = _fixture_inputs()
  result = run_synthesis_report(
    data["cluster_summary"],
    data["top20"],
    data["top5"],
    data["technical_assessments"],
    data["patent_technical_summary"],
    data["business_assessments"],
    data["patent_business_summary"],
  )
  summary = build_executive_summary(result)
  assert "事業化を証明" not in summary
  assert "参入できる" not in summary
  assert "候補" in summary or "candidate" in summary.lower() or "確認" in summary


def test_sme_action_plan_present() -> None:
  data = _fixture_inputs()
  data["business_assessments"][0]["design_around_or_differentiation_hints"] = ["differentiation candidate"]
  result = run_synthesis_report(
    data["cluster_summary"],
    data["top20"],
    data["top5"],
    data["technical_assessments"],
    data["patent_technical_summary"],
    data["business_assessments"],
    data["patent_business_summary"],
  )
  categories = {section["action_category"] for section in result["sme_action_plan"]}
  assert "今すぐ読むべき特許" in categories
