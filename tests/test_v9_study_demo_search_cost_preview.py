"""Tests for study demo search cost preview (Step 1 dry-run)."""

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
  bytes_to_gib,
  bytes_to_tib,
  enrich_patent_plan_with_dry_run,
  reference_cost_usd,
)
from services_v9.study_demo_search.execute import execute_three_source_search
from services_v9.study_demo_search.plan import build_search_plan_preview
from services_v9.study_demo_search.request import parse_search_request, request_fingerprint
from services_v9.study_demo_search.usage import accumulate_usage_metrics, init_usage_metrics
from services_v9.study_demo_search.web_provider import build_study_demo_web_plan

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


def _request(**overrides: object):
  base = {
    "theme": "carbon fiber sizing agent",
    "keywords_en": "epoxy polyurethane",
    "exact_phrase": "carbon fiber sizing agent",
    "enable_patent": True,
    "enable_paper": True,
    "enable_web": True,
  }
  base.update(overrides)
  return parse_search_request(base)


def _ok_dry_run(*, estimated_bytes: int = ESTIMATED_BYTES, blocked: bool = False) -> dict[str, object]:
  return {
    "dry_run_status": "ok",
    "estimated_bytes": estimated_bytes,
    "estimated_gb": bytes_to_gib(estimated_bytes),
    "estimated_cost_usd": reference_cost_usd(estimated_bytes, price_per_tib=6.25),
    "maximum_bytes_billed": MAX_BYTES,
    "would_be_blocked_by_max_bytes": blocked,
    "query_validation": [{"status": "ok"}],
    "job_id": "dry-job-test",
    "total_bytes_processed": estimated_bytes,
    "total_bytes_billed": 0,
    "cache_hit": False,
    "project_id": "demo-project",
    "location": "US",
  }


def _fake_dry_run_runner(request, *, environ=None, client_factory=None):
  return _ok_dry_run()


def test_step1_runs_bigquery_dry_run_for_patent() -> None:
  request = _request()
  calls: list[str] = []

  def runner(*args, **kwargs):
    calls.append("dry_run")
    return _ok_dry_run()

  with patch.dict("os.environ", SEARCH_ENV, clear=False):
    plan = build_search_plan_preview(request, patent_dry_run_runner=runner)
  assert calls == ["dry_run"]
  patent = plan["providers"]["patent"]
  assert patent["estimated_bytes"] == ESTIMATED_BYTES
  assert plan["cost_estimate"]["bigquery_estimated_bytes"] == ESTIMATED_BYTES


def test_step1_does_not_execute_live_patent_paper_web() -> None:
  request = _request()
  with patch.dict("os.environ", SEARCH_ENV, clear=False):
    with patch("services_v9.study_demo_search.execute.run_study_demo_patent_execute") as patent_exec:
      with patch("services_v9.paper_openalex_retrieval.execute_openalex_paper_retrieval") as paper_exec:
        with patch("services_v9.web_company_retrieval.execute_global_web_retrieval") as web_exec:
          build_search_plan_preview(request, patent_dry_run_runner=_fake_dry_run_runner)
  patent_exec.assert_not_called()
  paper_exec.assert_not_called()
  web_exec.assert_not_called()


def test_cost_estimate_and_provider_reflect_estimated_bytes() -> None:
  request = _request()
  with patch.dict("os.environ", SEARCH_ENV, clear=False):
    plan = build_search_plan_preview(request, patent_dry_run_runner=_fake_dry_run_runner)
  assert plan["cost_estimate"]["bigquery_estimated_bytes"] == ESTIMATED_BYTES
  assert plan["providers"]["patent"]["estimated_bytes"] == ESTIMATED_BYTES
  assert plan["providers"]["patent"]["bigquery_estimated_bytes"] == ESTIMATED_BYTES


def test_gib_tib_and_reference_cost() -> None:
  request = _request()
  with patch.dict("os.environ", SEARCH_ENV, clear=False):
    plan = build_search_plan_preview(request, patent_dry_run_runner=_fake_dry_run_runner)
  cost = plan["cost_estimate"]
  assert cost["bigquery_estimated_gib"] == bytes_to_gib(ESTIMATED_BYTES)
  assert cost["bigquery_estimated_tib"] == bytes_to_tib(ESTIMATED_BYTES)
  assert cost["bigquery_reference_cost_usd"] == reference_cost_usd(ESTIMATED_BYTES, price_per_tib=6.25)


def test_two_tib_guard_blocks_execution() -> None:
  request = _request()
  over = MAX_BYTES + 1

  def runner(*args, **kwargs):
    return _ok_dry_run(estimated_bytes=over, blocked=True)

  with patch.dict("os.environ", SEARCH_ENV, clear=False):
    plan = build_search_plan_preview(request, patent_dry_run_runner=runner)
  assert plan["cost_estimate"]["bigquery_execution_allowed"] is False
  assert plan["providers"]["patent"]["bigquery_execution_allowed"] is False


def test_dry_run_failure_sets_patent_status_and_keeps_other_plans() -> None:
  request = _request()

  def runner(*args, **kwargs):
    return {"dry_run_status": "error", "estimated_bytes": 0, "error": "boom", "job_id": ""}

  with patch.dict("os.environ", SEARCH_ENV, clear=False):
    plan = build_search_plan_preview(request, patent_dry_run_runner=runner)
  assert plan["providers"]["patent"]["status"] == "dry_run_failed"
  assert plan["providers"]["paper"]["status"] == "ready"
  assert plan["providers"]["web"]["status"] == "ready"


def test_fingerprint_change_invalidates_stored_dry_run_on_execute() -> None:
  request = _request()
  with patch.dict("os.environ", SEARCH_ENV, clear=False):
    plan = build_search_plan_preview(request, patent_dry_run_runner=_fake_dry_run_runner)
    changed = _request(theme="different theme")
    result = execute_three_source_search(changed, plan=plan, confirmed=True)
  assert result["status"] == "blocked"
  assert "regenerate plan" in str(result.get("errors", []))


def test_execute_reuses_plan_dry_run_not_rerun() -> None:
  request = _request()
  with patch.dict("os.environ", SEARCH_ENV, clear=False):
    plan = build_search_plan_preview(request, patent_dry_run_runner=_fake_dry_run_runner)
    with patch("services_v9.study_demo_search.execute.run_study_demo_patent_execute", return_value={"rows": [], "status": "success", "provider_status": "success"}) as execute:
      with patch("services_v9.study_demo_search.execute.run_study_demo_paper_execute", return_value={"rows": [], "status": "success"}):
        with patch("services_v9.study_demo_search.execute.run_study_demo_web_execute", return_value={"rows": [], "status": "success"}):
          with patch("services_v9.study_demo_search.execute.save_search_run"):
            with patch("services_v9.study_demo_search.execute.acquire_search_lock", return_value={"acquired": True}):
              with patch("services_v9.study_demo_search.execute.release_search_lock"):
                execute_three_source_search(request, plan=plan, confirmed=True)
  execute.assert_called_once()
  assert execute.call_args.kwargs["dry_run_result"]["job_id"] == "dry-job-test"


def test_tavily_credit_hint_not_copied_from_max_results() -> None:
  request = _request(web_max_results=10)
  with patch.dict("os.environ", SEARCH_ENV, clear=False):
    web_plan = build_study_demo_web_plan(request)
    plan = build_search_plan_preview(request, patent_dry_run_runner=_fake_dry_run_runner)
  assert web_plan["credit_hint"] is None
  assert web_plan["credit_estimate_status"] == "unavailable_before_execution"
  assert plan["cost_estimate"]["tavily_credit_hint"] is None
  assert plan["cost_estimate"]["tavily_credit_estimate_status"] == "unavailable_before_execution"


def test_web_usage_without_credits_stays_null() -> None:
  metrics = accumulate_usage_metrics(init_usage_metrics(), patent={}, paper={}, web={"rows": [{}], "usage_credits": None}, search_run_id="r1")
  assert metrics["web"]["total_credits"] is None


def test_exact_phrase_applied_to_web_plan() -> None:
  request = _request(exact_phrase="carbon fiber sizing agent")
  with patch.dict("os.environ", SEARCH_ENV, clear=False):
    web_plan = build_study_demo_web_plan(request)
  summary = web_plan["request_summary"]
  assert summary["exact_phrase"] == "carbon fiber sizing agent"
  assert summary["exact_phrase_applied"] is True
  assert summary["exact_phrase_method"] == "quoted_query"
  assert '"carbon fiber sizing agent"' in summary["query_preview"]


def test_plan_does_not_call_openalex_or_tavily_execute() -> None:
  request = _request()
  with patch.dict("os.environ", SEARCH_ENV, clear=False):
    with patch("services_v9.study_demo_search.paper_provider.execute_openalex_paper_retrieval") as openalex:
      with patch("services_v9.study_demo_search.web_provider.execute_global_web_retrieval") as tavily:
        build_search_plan_preview(request, patent_dry_run_runner=_fake_dry_run_runner)
  openalex.assert_not_called()
  tavily.assert_not_called()


def test_plan_output_has_no_secret_values(capsys) -> None:
  request = _request()
  with patch.dict("os.environ", SEARCH_ENV, clear=False):
    plan = build_search_plan_preview(request, patent_dry_run_runner=_fake_dry_run_runner)
  blob = json.dumps(plan)
  assert "test-tavily-key" not in blob
  assert "test-openalex-key" not in blob
  assert "password" not in blob.lower()


def test_enrich_patent_plan_zero_bytes_not_success() -> None:
  enriched = enrich_patent_plan_with_dry_run(
    {"status": "ready", "provider": "patent"},
    _ok_dry_run(estimated_bytes=0),
    dry_run_fingerprint="abc",
    environ=SEARCH_ENV,
  )
  assert enriched["status"] == "dry_run_zero_bytes"
  assert enriched["bigquery_execution_allowed"] is False


def test_different_fingerprint_dry_run_not_reused_on_execute() -> None:
  request_a = _request(theme="alpha")
  request_b = _request(theme="beta")
  with patch.dict("os.environ", SEARCH_ENV, clear=False):
    plan = build_search_plan_preview(request_a, patent_dry_run_runner=_fake_dry_run_runner)
    plan["providers"]["patent"]["dry_run_fingerprint"] = request_fingerprint(request_b)
    result = execute_three_source_search(request_a, plan=plan, confirmed=True)
  assert result["status"] == "blocked"


def test_execute_blocks_when_dry_run_failed() -> None:
  request = _request()
  with patch.dict("os.environ", SEARCH_ENV, clear=False):
    plan = build_search_plan_preview(request, patent_dry_run_runner=_fake_dry_run_runner)
    plan["providers"]["patent"]["status"] = "dry_run_failed"
    result = execute_three_source_search(request, plan=plan, confirmed=True)
  assert result["status"] == "blocked"
