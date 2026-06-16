"""Tests for evidence map report."""

from tech_cartography.curation.technology_classifier import classify_patent_record
from tech_cartography.curation.patent_ranker import rank_patent_records, select_fulltext_candidates, select_top_patents
from tech_cartography.reports.case_study_pipeline import run_case_study_pipeline
from tech_cartography.reports.evidence_map_report import (
  build_evidence_map_summary,
  render_evidence_map_markdown,
)


def _sample_records() -> list[dict]:
  records = []
  for index in range(6):
    record = classify_patent_record(
      {
        "publication_number": f"US-2024-{index:06d}",
        "title": f"PAN carbon fiber carbonization prepreg {index}",
        "abstract": "High modulus composite for aerospace pressure vessel",
        "assignee": "Toray Industries" if index % 2 == 0 else "Teijin Limited",
        "country": "US",
        "publication_date": f"202{index}0101",
        "claims_source": "not_fetched",
        "search_intents": ["core_manufacturing", "bundle_prepreg"],
        "matched_terms": ["PAN", "carbon fiber", "carbonization"],
      },
    )
    record["noise_score"] = 0.0
    record["noise_signals"] = []
    records.append(record)
  return records


def test_evidence_map_markdown_contains_top_sections() -> None:
  records = _sample_records()
  ranked = rank_patent_records(records)
  top20 = select_top_patents(ranked, top_n=20)
  top5 = select_fulltext_candidates(ranked, top_n=5)
  summary = build_evidence_map_summary(records, ranked, top_records=top20, fulltext_candidates=top5)
  markdown = render_evidence_map_markdown(summary)
  assert "Carbon Fiber Evidence Map v1" in markdown
  assert "## 3. 重要特許Top20" in markdown
  assert "## 4. Top5全文取得候補" in markdown


def test_case_study_pipeline_runs() -> None:
  result = run_case_study_pipeline(_sample_records(), top_n=5, fulltext_top_n=3)
  assert result["classified_records"]
  assert result["ranked_records"]
  assert len(result["top_records"]) <= 5
  assert len(result["fulltext_candidates"]) <= 3
