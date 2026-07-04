"""Tests for v9 OpenAlex paper retrieval."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
from pathlib import Path

from streamlit.testing.v1 import AppTest

from services_v9.paper_openalex_retrieval import (
  build_openalex_paper_preview,
  build_openalex_search_url,
  execute_openalex_paper_retrieval,
  save_openalex_paper_retrieval_artifacts,
)
from services_v9.search_plan import build_unified_search_plan

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE = (PROJECT_ROOT / "services_v9" / "paper_openalex_retrieval.py").read_text(encoding="utf-8")
TABS_SOURCE = (PROJECT_ROOT / "ui_v9" / "tabs.py").read_text(encoding="utf-8")


def _profile() -> dict[str, object]:
  return {
    "theme_name": "Battery materials",
    "theme_description": "Monitor next-gen cathode and electrolyte signals.",
    "keywords": {
      "core_en": ["solid state battery", "cathode"],
      "core_ja": ["全固体電池"],
      "application_en": ["energy density", "cycle life"],
      "application_ja": ["寿命"],
      "material_process_en": ["electrolyte", "sintering"],
      "material_process_ja": ["電解質"],
      "exclude_en": ["review"],
      "exclude_ja": [],
    },
    "seed_publications": ["US20240123456A1"],
    "candidate_publications": [],
    "target_companies": ["Toyota"],
  }


def _sample_work(work_id: str, doi: str) -> dict[str, object]:
  return {
    "id": work_id,
    "display_name": f"Paper {work_id.split('/')[-1]}",
    "doi": f"https://doi.org/{doi}",
    "publication_date": "2025-01-20",
    "publication_year": 2025,
    "abstract_inverted_index": {"solid": [0], "state": [1], "battery": [2]},
    "authorships": [
      {
        "author": {"display_name": "Alice"},
        "institutions": [{"display_name": "Example University"}],
      },
    ],
    "primary_location": {
      "landing_page_url": f"https://example.org/{work_id.split('/')[-1]}",
      "source": {"display_name": "Journal of Batteries", "type": "journal"},
    },
    "cited_by_count": 9,
    "open_access": {"is_oa": True},
    "concepts": [{"display_name": "Materials science"}],
    "topics": [{"display_name": "Solid electrolytes"}],
    "language": "en",
  }


class _FakeResponse:
  def __init__(self, payload: dict[str, object]) -> None:
    self._payload = json.dumps(payload).encode("utf-8")

  def __enter__(self):
    return self

  def __exit__(self, *args):  # noqa: ANN002
    return False

  def read(self) -> bytes:
    return self._payload


def _preview(max_results: int = 40) -> dict[str, object]:
  plan = build_unified_search_plan(_profile())
  return build_openalex_paper_preview(plan, _profile(), max_results=max_results)


def test_preview_builds_openalex_request() -> None:
  preview = _preview()
  request = dict(preview["request"])
  assert request["provider"] == "openalex"
  assert request["fallback_interface"]["provider"] == "semantic_scholar"
  assert request["fallback_interface"]["implemented"] is False
  assert str(request["query_id"]).startswith("paper_q")
  assert str(request["query_text"]).strip()
  assert "Battery materials" in str(request["query_text"])


def test_search_url_includes_cursor_and_filter() -> None:
  preview = _preview()
  url = build_openalex_search_url(dict(preview["request"]), cursor="abc123")
  parsed = urllib.parse.urlparse(url)
  params = urllib.parse.parse_qs(parsed.query)
  assert params["cursor"] == ["abc123"]
  assert "filter" in params
  assert "from_publication_date:" in params["filter"][0]


def test_execute_openalex_pages_and_normalizes_rows() -> None:
  preview = _preview(max_results=3)
  payloads = {
    "*": {
      "results": [_sample_work("https://openalex.org/W1", "10.1000/test1")],
      "meta": {"next_cursor": "next-1"},
    },
    "next-1": {
      "results": [_sample_work("https://openalex.org/W2", "10.1000/test2")],
      "meta": {"next_cursor": ""},
    },
  }

  def _fake_opener(request, _timeout):
    cursor = urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query).get("cursor", ["*"])[0]
    return _FakeResponse(payloads[cursor])

  result = execute_openalex_paper_retrieval(dict(preview), opener=_fake_opener, sleeper=lambda _s: None)
  assert result["provider_status"] == "success"
  assert result["pages_fetched"] == 2
  assert result["rows_retrieved"] == 2
  first = result["rows"][0]
  assert first["record_stage"] == "staged"
  assert first["retrieval_mode"] == "real"
  assert first["source_journal"] == "Journal of Batteries"
  assert first["topics"] == ["Solid electrolytes"]
  assert first["institutions"] == ["Example University"]


def test_execute_retries_after_transient_error() -> None:
  preview = _preview(max_results=2)
  attempts = {"count": 0}

  def _fake_opener(request, _timeout):
    attempts["count"] += 1
    if attempts["count"] == 1:
      raise urllib.error.URLError("temporary outage")
    return _FakeResponse({
      "results": [_sample_work("https://openalex.org/W3", "10.1000/test3")],
      "meta": {"next_cursor": ""},
    })

  result = execute_openalex_paper_retrieval(dict(preview), opener=_fake_opener, sleeper=lambda _s: None)
  assert attempts["count"] == 2
  assert result["provider_status"] == "success"
  assert result["rows_retrieved"] == 1
  assert any(int(row.get("attempt", 0) or 0) == 2 for row in result["provider_log"])


def test_execute_keeps_partial_success_rows() -> None:
  preview = _preview(max_results=3)
  payload = {
    "results": [_sample_work("https://openalex.org/W4", "10.1000/test4")],
    "meta": {"next_cursor": "next-2"},
  }

  def _fake_opener(request, _timeout):
    cursor = urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query).get("cursor", ["*"])[0]
    if cursor == "*":
      return _FakeResponse(payload)
    raise urllib.error.URLError("page 2 failed")

  result = execute_openalex_paper_retrieval(dict(preview), opener=_fake_opener, sleeper=lambda _s: None)
  assert result["provider_status"] == "partial_success"
  assert result["rows_retrieved"] == 1
  assert result["error"] is not None


def test_artifacts_are_saved_for_openalex_retrieval(tmp_path: Path) -> None:
  preview = _preview(max_results=1)
  retrieval_result = {
    "provider": "openalex",
    "query_id": "paper_q01",
    "retrieval_run_id": "paper_retrieval_paper_q01_20260704_120000",
    "provider_status": "success",
    "rows": [
      {
        "work_id": "https://openalex.org/W9",
        "doi": "10.1000/test9",
        "title": "Paper W9",
        "abstract": "solid state battery",
        "authors": ["Alice"],
        "institutions": ["Example University"],
        "publication_date": "2025-01-20",
        "source_journal": "Journal of Batteries",
        "cited_by_count": 9,
        "topics": ["Solid electrolytes"],
        "open_access": True,
        "original_language": "en",
        "source_url": "https://example.org/W9",
        "query_id": "paper_q01",
        "retrieval_run_id": "paper_retrieval_paper_q01_20260704_120000",
        "provider_status": "success",
        "record_stage": "staged",
        "retrieval_mode": "real",
      },
    ],
    "provider_log": [{"page_index": 1, "status": "ok"}],
    "pages_fetched": 1,
    "retry_limit": 2,
    "error": None,
  }
  paths = save_openalex_paper_retrieval_artifacts(dict(preview), retrieval_result, base_dir=tmp_path / "v9_runs")
  assert paths["plan_json"].exists()
  assert paths["staged_json"].exists()
  assert paths["staged_csv"].exists()
  assert paths["provider_log_json"].exists()


def test_source_code_has_no_google_scholar_scrape() -> None:
  assert "google scholar" not in SOURCE.lower()
  assert "serpapi" not in SOURCE.lower()


def test_ui_source_contains_openalex_controls() -> None:
  required = [
    "OpenAlex Paper Retrieval",
    "OpenAlex論文取得を実行",
    "論文query_id",
    "provider status",
    "Semantic Scholar future only",
  ]
  assert all(label in TABS_SOURCE for label in required)


def test_streamlit_testing_finds_paper_retrieval_controls() -> None:
  at = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
  at.run()
  button_labels = [button.label for button in at.button]
  assert "OpenAlex論文取得を実行" in button_labels
  assert any(select.label == "論文query_id" for select in at.selectbox)
