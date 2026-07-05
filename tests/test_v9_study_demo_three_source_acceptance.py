"""Unit tests for study demo three-source acceptance helper."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from scripts import run_v9_study_demo_three_source_acceptance as acceptance


def test_validate_acceptance_result_success() -> None:
  result = {
    "status": "success",
    "provider_status": {
      "patent": {"status": "success"},
      "paper": {"status": "success"},
      "web": {"status": "success"},
    },
    "patent_results": {"rows": [{"publication_number": "US-1"}], "estimated_bytes": 1, "processed_bytes": 2, "billed_bytes": 3},
    "paper_results": {"rows": [{"openalex_id": "W1", "title": "Paper"}], "request_count": 1, "pagination_count": 1},
    "web_results": {"rows": [{"canonical_url": "https://example.com"}], "request_count": 1, "usage_credits": 1},
    "integrated_signals": {
      "signals": [
        {"source_type": "patent"},
        {"source_type": "paper"},
        {"source_type": "web_company"},
      ],
      "ranked_count": 3,
    },
    "keyword_suggestions": {"add_keywords": ["epoxy"]},
    "export": {"integrated_csv": "a,b"},
  }
  artifacts = {name: {"ok": True} for name in acceptance.REQUIRED_ARTIFACTS}
  artifacts["search_report.md"] = "# report"
  validation = acceptance.validate_acceptance_result(result, artifacts=artifacts)
  assert validation["passed"] is True


def test_validate_acceptance_result_partial_success_fails() -> None:
  result = {
    "status": "partial_success",
    "provider_status": {"patent": {"status": "success"}, "paper": {"status": "failed"}, "web": {"status": "success"}},
    "patent_results": {"rows": [{}]},
    "paper_results": {"rows": []},
    "web_results": {"rows": [{}], "request_count": 1},
    "integrated_signals": {"signals": [{"source_type": "patent"}], "ranked_count": 1},
    "keyword_suggestions": {"add_keywords": []},
    "export": {},
  }
  validation = acceptance.validate_acceptance_result(result, artifacts={})
  assert validation["passed"] is False


def test_build_acceptance_request_has_theme_and_keywords() -> None:
  request = acceptance.build_acceptance_request()
  assert "PAN" in request.theme
  assert "carbon fiber sizing agent" in request.keywords_en
  assert request.enable_patent is True
  assert request.enable_paper is True
  assert request.enable_web is True
