"""Tests for study demo three-source search (Stage C1)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from services_v9.study_demo_guard import StudyDemoExternalExecutionBlocked, assert_external_execution_allowed
from services_v9.study_demo_search import (
  StudyDemoSearchRequest,
  build_export_bundle,
  build_keyword_suggestions,
  build_search_plan_preview,
  build_similar_patents,
  execute_three_source_search,
  integrate_search_results,
  parse_search_request,
  validate_search_request,
)
from services_v9.study_demo_search.lock import acquire_search_lock, release_search_lock
from services_v9.study_demo_search.request import request_fingerprint
from services_v9.study_demo_search.web_classify import classify_web_activity

SEARCH_ENV = {
  "V9_STUDY_DEMO_MODE": "true",
  "V9_STUDY_DEMO_SEARCH_ENABLED": "true",
  "V9_STUDY_DEMO_ENABLE_PATENT_SEARCH": "true",
  "V9_STUDY_DEMO_ENABLE_PAPER_SEARCH": "true",
  "V9_STUDY_DEMO_ENABLE_WEB_SEARCH": "true",
  "V9_STUDY_DEMO_OPENALEX_API_KEY": "test-openalex-key",
  "V9_STUDY_DEMO_TAVILY_API_KEY": "test-tavily-key",
  "V9_STUDY_DEMO_DISABLE_EXTERNAL_EXECUTION": "true",
}


def _request(**overrides: object) -> StudyDemoSearchRequest:
  base = {
    "theme": "carbon fiber sizing",
    "keywords_en": "epoxy polyurethane",
    "enable_patent": True,
    "enable_paper": True,
    "enable_web": True,
  }
  base.update(overrides)
  return parse_search_request(base)


def test_read_only_mode_still_blocks_smtp_and_scheduler() -> None:
  with patch.dict("os.environ", SEARCH_ENV, clear=False):
    with pytest.raises(StudyDemoExternalExecutionBlocked):
      assert_external_execution_allowed("smtp_send")
    with pytest.raises(StudyDemoExternalExecutionBlocked):
      assert_external_execution_allowed("cloud_scheduler")


def test_search_enabled_allows_provider_operations() -> None:
  with patch.dict("os.environ", SEARCH_ENV, clear=False):
    assert_external_execution_allowed("bigquery_dry_run")
    assert_external_execution_allowed("openalex_execute")
    assert_external_execution_allowed("tavily_execute")


def test_search_disabled_blocks_provider_operations() -> None:
  env = {**SEARCH_ENV, "V9_STUDY_DEMO_SEARCH_ENABLED": "false"}
  with patch.dict("os.environ", env, clear=False):
    with pytest.raises(StudyDemoExternalExecutionBlocked):
      assert_external_execution_allowed("openalex_execute")


def test_empty_search_rejected() -> None:
  request = parse_search_request({"theme": "", "keywords_ja": "", "keywords_en": ""})
  assert len(validate_search_request(request)) > 0


def test_sql_like_input_rejected() -> None:
  with pytest.raises(ValueError):
    parse_search_request({"theme": "select * from patents", "keywords_en": "x"})


def test_plan_does_not_execute_providers() -> None:
  request = _request()

  def runner(*args, **kwargs):
    return {
      "dry_run_status": "ok",
      "estimated_bytes": 1000,
      "would_be_blocked_by_max_bytes": False,
      "job_id": "dry",
      "total_bytes_processed": 1000,
    }

  with patch.dict("os.environ", SEARCH_ENV, clear=False):
    plan = build_search_plan_preview(request, patent_dry_run_runner=runner)
  assert plan["status"] == "plan"
  assert plan["execution_blocked"] is True
  assert plan["providers"]["patent"]["estimated_bytes"] == 1000


def test_execute_requires_confirmation() -> None:
  request = _request()

  def runner(*args, **kwargs):
    return {
      "dry_run_status": "ok",
      "estimated_bytes": 1000,
      "would_be_blocked_by_max_bytes": False,
      "job_id": "dry",
      "total_bytes_processed": 1000,
    }

  with patch.dict("os.environ", SEARCH_ENV, clear=False):
    plan = build_search_plan_preview(request, patent_dry_run_runner=runner)
    result = execute_three_source_search(request, plan=plan, confirmed=False)
  assert result["status"] == "blocked"


def test_duplicate_plan_id_blocked() -> None:
  request = _request()

  def runner(*args, **kwargs):
    return {
      "dry_run_status": "ok",
      "estimated_bytes": 1000,
      "would_be_blocked_by_max_bytes": False,
      "job_id": "dry",
      "total_bytes_processed": 1000,
    }

  with patch.dict("os.environ", SEARCH_ENV, clear=False):
    plan = build_search_plan_preview(request, patent_dry_run_runner=runner)
    executed = {str(plan["search_plan_id"])}
    result = execute_three_source_search(request, plan=plan, confirmed=True, executed_plan_ids=executed)
  assert "duplicate" in str(result.get("errors", []))


def test_integrate_partial_success() -> None:
  integrated = integrate_search_results(
    patent_rows=[{"publication_number": "JP-1", "title": "A", "abstract": "fiber"}],
    paper_rows=[],
    web_rows=[{"canonical_url": "https://example.com/a", "original_title": "News", "original_snippet": "plant"}],
    search_run_id="run1",
    query_provenance={"theme": "test"},
  )
  assert integrated["patent_count"] == 1
  assert integrated["web_count"] == 1


def test_web_classification_local_rules() -> None:
  assert classify_web_activity("新工場稼働", "生産能力を拡大") == "投資・生産"


def test_keyword_suggestions_local_only() -> None:
  suggestions = build_keyword_suggestions(
    [{"title": "carbon fiber epoxy sizing", "summary": "spreadability impregnation", "source_type": "patent", "metadata": {}}]
  )
  assert suggestions["add_keywords"]


def test_similar_patents_seed_excluded() -> None:
  signals = [
    {"source_type": "patent", "source_id": "US-1", "title": "epoxy sizing", "summary": "fiber", "family_id": "F1"},
    {"source_type": "patent", "source_id": "US-2", "title": "epoxy composite sizing", "summary": "fiber tow", "family_id": "F2"},
  ]
  result = build_similar_patents(signals, seed_patent="US-1")
  assert all(item["publication_number"] != "US-1" for item in result["items"])


def test_export_has_no_secret_fields() -> None:
  export = build_export_bundle([], {}, {}, {})
  blob = json.dumps(export)
  assert "api_key" not in blob.lower()
  assert "password" not in blob.lower()


def test_provider_secrets_plan() -> None:
  completed = subprocess.run(
    [sys.executable, str(ROOT / "scripts/create_v9_study_demo_provider_secrets.py"), "--plan"],
    cwd=ROOT,
    check=True,
    capture_output=True,
    text=True,
  )
  payload = json.loads(completed.stdout)
  assert payload["status"] == "plan"
  assert "tech-cartography-v9-study-demo-openalex-api-key" in payload["secrets"]["openalex_key"]["secret"]


def test_disable_search_plan() -> None:
  completed = subprocess.run(
    ["bash", str(ROOT / "scripts/disable_v9_study_demo_search.sh"), "--plan"],
    cwd=ROOT,
    check=True,
    capture_output=True,
    text=True,
  )
  payload = json.loads(completed.stdout)
  assert payload["status"] == "plan"


def test_acceptance_plan() -> None:
  completed = subprocess.run(
    [sys.executable, str(ROOT / "scripts/run_v9_study_demo_three_source_acceptance.py"), "--plan"],
    cwd=ROOT,
    check=True,
    capture_output=True,
    text=True,
  )
  payload = json.loads(completed.stdout)
  assert payload["status"] == "plan"


def test_fingerprint_changes_when_conditions_change() -> None:
  a = _request(theme="alpha")
  b = _request(theme="beta")
  assert request_fingerprint(a) != request_fingerprint(b)


class _FakeBlob:
  def __init__(self) -> None:
    self.generation = 1
    self._exists = False
    self._text = ""

  def exists(self) -> bool:
    return self._exists

  def upload_from_string(self, text: str, **kwargs: object) -> None:
    if kwargs.get("if_generation_match") == 0 and self._exists:
      raise RuntimeError("exists")
    self._text = text
    self._exists = True

  def reload(self) -> None:
    return None

  def download_as_bytes(self) -> bytes:
    return self._text.encode()

  def delete(self, **kwargs: object) -> None:
    self._exists = False


class _FakeBucket:
  def __init__(self) -> None:
    self.blob_obj = _FakeBlob()

  def blob(self, _name: str) -> _FakeBlob:
    return self.blob_obj


class _FakeClient:
  def __init__(self) -> None:
    self._bucket = _FakeBucket()

  def bucket(self, _name: str) -> _FakeBucket:
    return self._bucket


def test_search_lock_acquire_and_release() -> None:
  client = _FakeClient()
  with patch.dict("os.environ", {**SEARCH_ENV, "V9_STUDY_DEMO_BUCKET": "demo-bucket"}, clear=False):
    lock = acquire_search_lock("run-a", storage_client=client, owner_id="owner-a")
    assert lock["acquired"] is True
    release = release_search_lock(lock, storage_client=client)
    assert release["released"] is True


def test_ui_module_requires_auth_flag() -> None:
  source = Path(ROOT / "ui_v9/study_demo_search_ui.py").read_text(encoding="utf-8")
  assert "authenticated" in source
  assert 'if not authenticated' in source


def test_tabs_integrates_search_section() -> None:
  source = Path(ROOT / "ui_v9/tabs.py").read_text(encoding="utf-8")
  assert "render_study_demo_keyword_search_section" in source
