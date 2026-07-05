"""Tests for study demo search plan status normalization."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from services_v9.study_demo_search.cost_preview import (
  BYTES_PER_TIB,
  build_normalized_dry_run_view,
  enrich_patent_plan_with_dry_run,
  evaluate_bigquery_execution_allowed,
  normalize_study_demo_patent_validation_rows,
  reference_cost_usd,
)
from services_v9.study_demo_search.paper_provider import build_study_demo_paper_plan
from services_v9.study_demo_search.patent_provider import build_study_demo_patent_plan
from services_v9.study_demo_search.plan import build_search_plan_preview
from services_v9.study_demo_search.request import parse_search_request
from services_v9.study_demo_search.web_provider import _web_query_parts, build_study_demo_web_plan

SEARCH_ENV = {
  "V9_STUDY_DEMO_MODE": "true",
  "V9_STUDY_DEMO_SEARCH_ENABLED": "true",
  "V9_STUDY_DEMO_ENABLE_PATENT_SEARCH": "true",
  "V9_STUDY_DEMO_ENABLE_PAPER_SEARCH": "true",
  "V9_STUDY_DEMO_ENABLE_WEB_SEARCH": "true",
  "V9_STUDY_DEMO_BIGQUERY_MAX_BYTES_BILLED": "2199023255552",
  "V9_STUDY_DEMO_BIGQUERY_PRICE_PER_TIB_USD": "6.25",
  "V9_STUDY_DEMO_OPENALEX_API_KEY": "test-openalex-key",
  "V9_STUDY_DEMO_TAVILY_API_KEY": "test-tavily-key",
  "V9_STUDY_DEMO_DISABLE_EXTERNAL_EXECUTION": "true",
}

ESTIMATED_BYTES = 261_061_747_822
MAX_BYTES = 2_199_023_255_552
PRICE = 6.25
EXPECTED_COST = reference_cost_usd(ESTIMATED_BYTES, price_per_tib=PRICE)


def _request(**overrides: object):
  base = {
    "theme": "carbon fiber sizing agent",
    "keywords_en": "carbon fiber sizing agent, carbon fiber tow, aqueous sizing, epoxy",
    "exact_phrase": "carbon fiber sizing agent",
    "enable_patent": True,
    "enable_paper": True,
    "enable_web": True,
  }
  base.update(overrides)
  return parse_search_request(base)


def _raw_dry_run(**overrides: object) -> dict[str, object]:
  payload = {
    "dry_run_status": "ok",
    "estimated_bytes": ESTIMATED_BYTES,
    "maximum_bytes_billed": 0,
    "would_be_blocked_by_max_bytes": False,
    "query_validation": [
      {"status": "warning", "message": "maximum_bytes_billed が未設定です。dry-run 実行は拒否されます。"}
    ],
    "execute_enabled": False,
    "execution_allowed": False,
    "job_id": "dry-job-test",
    "total_bytes_processed": ESTIMATED_BYTES,
  }
  payload.update(overrides)
  return payload


def test_successful_dry_run_sets_all_execution_allowed_true() -> None:
  enriched = enrich_patent_plan_with_dry_run(
    build_study_demo_patent_plan(_request(), environ=SEARCH_ENV),
    _raw_dry_run(),
    dry_run_fingerprint="fp1",
    environ=SEARCH_ENV,
  )
  assert enriched["bigquery_execution_allowed"] is True
  assert enriched["dry_run"]["execution_allowed"] is True
  assert enriched["dry_run"]["execution_performed"] is False
  assert "execute_enabled" not in enriched["dry_run"]


def test_execution_performed_and_allowed_are_separate() -> None:
  view = build_normalized_dry_run_view(
    _raw_dry_run(),
    max_bytes=MAX_BYTES,
    price_per_tib=PRICE,
    validation_rows=[{"status": "ok", "message": "validation passed"}],
    execution_allowed=True,
  )
  assert view["execution_performed"] is False
  assert view["execution_allowed"] is True


def test_max_bytes_configured_removes_unset_warning() -> None:
  rows = normalize_study_demo_patent_validation_rows(
    [{"status": "warning", "message": "maximum_bytes_billed が未設定です。dry-run 実行は拒否されます。"}],
    max_bytes=MAX_BYTES,
  )
  assert rows == [{"status": "ok", "message": "validation passed"}]


def test_max_bytes_unset_blocks_execution() -> None:
  rows = normalize_study_demo_patent_validation_rows([], max_bytes=0)
  assert any(row["status"] == "error" for row in rows)
  assert evaluate_bigquery_execution_allowed(
    dry_run_status="ok",
    estimated_bytes=ESTIMATED_BYTES,
    max_bytes=0,
    validation_rows=rows,
  ) is False


def test_over_two_tib_blocks_execution() -> None:
  over = MAX_BYTES + 1
  assert evaluate_bigquery_execution_allowed(
    dry_run_status="ok",
    estimated_bytes=over,
    max_bytes=MAX_BYTES,
    validation_rows=[{"status": "ok", "message": "validation passed"}],
    would_be_blocked_by_max_bytes=True,
  ) is False
  enriched = enrich_patent_plan_with_dry_run(
    {"status": "ready", "provider": "patent", "validation_rows": []},
    _raw_dry_run(estimated_bytes=over, would_be_blocked_by_max_bytes=True),
    dry_run_fingerprint="fp1",
    environ=SEARCH_ENV,
  )
  assert enriched["bigquery_execution_allowed"] is False
  assert enriched["dry_run"]["execution_allowed"] is False


def test_dry_run_failure_blocks_execution() -> None:
  enriched = enrich_patent_plan_with_dry_run(
    {"status": "ready", "provider": "patent", "validation_rows": []},
    _raw_dry_run(dry_run_status="error"),
    dry_run_fingerprint="fp1",
    environ=SEARCH_ENV,
  )
  assert enriched["status"] == "dry_run_failed"
  assert enriched["bigquery_execution_allowed"] is False
  assert enriched["dry_run"]["execution_allowed"] is False


def test_cost_fields_match_at_625_usd_per_tib() -> None:
  enriched = enrich_patent_plan_with_dry_run(
    {"status": "ready", "provider": "patent", "validation_rows": []},
    _raw_dry_run(),
    dry_run_fingerprint="fp1",
    environ=SEARCH_ENV,
  )
  assert enriched["bigquery_reference_cost_usd"] == EXPECTED_COST
  assert enriched["dry_run"]["estimated_cost_usd"] == EXPECTED_COST
  assert EXPECTED_COST == pytest.approx(1.484, rel=0, abs=0.001)
  assert reference_cost_usd(ESTIMATED_BYTES, price_per_tib=5.0) != EXPECTED_COST


def test_exact_phrase_appears_once_in_web_query() -> None:
  request = _request()
  query, meta = _web_query_parts(request)
  assert meta["exact_phrase_applied"] is True
  assert meta["exact_phrase_method"] == "quoted_query"
  assert query.count('"carbon fiber sizing agent"') == 1
  assert "carbon fiber tow" in query
  assert " aqueous sizing" in query or "aqueous sizing" in query


def test_openalex_plan_unaffected_by_web_dedupe() -> None:
  request = _request()
  with patch.dict("os.environ", SEARCH_ENV, clear=False):
    paper = build_study_demo_paper_plan(request, environ=SEARCH_ENV)
  assert paper["status"] in {"ready", "blocked"}
  assert "openalex" in str(paper.get("provider", "")).lower() or paper.get("request_summary")


def test_plan_preview_has_no_secret_values() -> None:
  def runner(*args, **kwargs):
    return _raw_dry_run()

  with patch.dict("os.environ", SEARCH_ENV, clear=False):
    plan = build_search_plan_preview(_request(), patent_dry_run_runner=runner)
  blob = json.dumps(plan)
  assert "test-tavily-key" not in blob
  assert "test-openalex-key" not in blob


def test_patent_plan_validation_ok_when_max_bytes_configured() -> None:
  with patch.dict("os.environ", SEARCH_ENV, clear=False):
    patent = build_study_demo_patent_plan(_request(), environ=SEARCH_ENV)
  assert patent["validation_rows"] == [{"status": "ok", "message": "validation passed"}]


def test_build_plan_does_not_execute_live_providers() -> None:
  def runner(*args, **kwargs):
    return _raw_dry_run()

  with patch.dict("os.environ", SEARCH_ENV, clear=False):
    with patch("services_v9.paper_openalex_retrieval.execute_openalex_paper_retrieval") as openalex:
      with patch("services_v9.web_company_retrieval.execute_global_web_retrieval") as tavily:
        build_search_plan_preview(_request(), patent_dry_run_runner=runner)
  openalex.assert_not_called()
  tavily.assert_not_called()


def test_web_plan_keeps_credit_hint_unavailable() -> None:
  with patch.dict("os.environ", SEARCH_ENV, clear=False):
    web = build_study_demo_web_plan(_request(), environ=SEARCH_ENV)
  assert web["credit_hint"] is None
  assert web["credit_estimate_status"] == "unavailable_before_execution"
