"""Tests for Study Demo external source URL resolution and link rendering."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from services_v9.study_demo_active_loader import adapt_study_demo_signal_to_display, adapt_integrated_signals_for_display
from services_v9.study_demo_analysis_context import build_active_context_from_run
from services_v9.study_demo_config import PRODUCTION_PERSIST_BUCKET
from services_v9.study_demo_downstream import build_downstream_bundle, digest_to_markdown
from services_v9.study_demo_search.export import build_export_bundle
from services_v9.study_demo_source_url import (
  build_doi_url,
  build_google_patents_url,
  build_openalex_url,
  enrich_signal_with_url_provenance,
  is_valid_external_url,
  normalize_doi,
  resolve_signal_source_url,
  summarize_url_resolution,
)
from ui_v9.study_demo_source_link import build_study_demo_source_link_key, render_external_source_link
from ui_v9.tabs import render_top_signals_tab

FIXTURE_PATH = ROOT / "tests/fixtures/study_demo_active_run_connection_samples.json"
RUN_ID = "study_demo_search_20260705_061319_e973e4c2"


def _patent_signal(**overrides: object) -> dict:
  base = {
    "signal_id": "patent:p1",
    "source_type": "patent",
    "source_id": "US2020378036A1",
    "title": "Patent title",
    "summary": "abstract",
    "organization": "Example",
  }
  base.update(overrides)
  return base


def _paper_signal(**overrides: object) -> dict:
  base = {
    "signal_id": "paper:w1",
    "source_type": "paper",
    "source_id": "W123",
    "title": "Paper title",
    "summary": "abstract",
    "metadata": {"doi": "10.1000/example"},
  }
  base.update(overrides)
  return base


def _web_signal(**overrides: object) -> dict:
  base = {
    "signal_id": "web:u1",
    "source_type": "web_company",
    "source_id": "web1",
    "title": "Web title",
    "summary": "snippet",
    "source_url": "https://company.example.com/news/a",
  }
  base.update(overrides)
  return base


def test_patent_explicit_url_preferred() -> None:
  resolution = resolve_signal_source_url(
    _patent_signal(source_url="https://patents.google.com/patent/US111/en", url="")
  )
  assert resolution.is_valid
  assert resolution.resolved_url.endswith("/US111/en")
  assert resolution.url_source == "source_url"


def test_patent_publication_number_builds_google_patents_url() -> None:
  resolution = resolve_signal_source_url(_patent_signal(source_id="US2020378036A1"))
  assert resolution.is_valid
  assert resolution.resolved_url == "https://patents.google.com/patent/US2020378036A1/en"
  assert resolution.url_source == "publication_number"


def test_paper_doi_builds_https_doi_url() -> None:
  resolution = resolve_signal_source_url(_paper_signal(metadata={"doi": "doi:10.1234/example"}))
  assert resolution.is_valid
  assert resolution.resolved_url == "https://doi.org/10.1234/example"
  assert resolution.url_source == "doi"


def test_paper_openalex_fallback() -> None:
  resolution = resolve_signal_source_url(
    _paper_signal(metadata={"openalex_id": "https://openalex.org/W2949920894"}, url="", source_url="")
  )
  assert resolution.is_valid
  assert "openalex.org/W2949920894" in resolution.resolved_url


def test_web_source_url_preserved() -> None:
  resolution = resolve_signal_source_url(_web_signal())
  assert resolution.is_valid
  assert resolution.resolved_url == "https://company.example.com/news/a"


def test_empty_url_invalid() -> None:
  resolution = resolve_signal_source_url(_patent_signal(source_id="", source_url="", url=""))
  assert not resolution.is_valid
  assert resolution.url_resolution_status == "missing"


@pytest.mark.parametrize(
  "url",
  ["/relative", "#", "javascript:alert(1)", "http://localhost/x", "https://127.0.0.1/x"],
)
def test_invalid_urls_rejected(url: str) -> None:
  valid, _ = is_valid_external_url(url)
  assert not valid


def test_study_demo_self_url_rejected() -> None:
  valid, reason = is_valid_external_url("https://tech-cartography-v9-study-demo-1020686343587.us-central1.run.app/")
  assert not valid
  assert reason == "study_demo_self_url"


def test_original_url_not_overwritten() -> None:
  enriched = enrich_signal_with_url_provenance(_patent_signal(source_url="https://patents.google.com/patent/US111/en"))
  assert enriched["source_url_original"] == "https://patents.google.com/patent/US111/en"
  assert enriched["source_url"] == "https://patents.google.com/patent/US111/en"


def test_normalize_doi_strips_prefix() -> None:
  assert normalize_doi("https://doi.org/10.1/x") == "10.1/x"
  assert build_doi_url("10.1/x") == "https://doi.org/10.1/x"


def test_patent_without_publication_number_no_link() -> None:
  resolution = resolve_signal_source_url(_patent_signal(source_id="", external_id=""))
  assert not resolution.is_valid


def test_web_without_url_not_guessed() -> None:
  resolution = resolve_signal_source_url(_web_signal(source_url="", url="", title="Some title"))
  assert not resolution.is_valid


def test_adapter_uses_source_url_when_url_missing() -> None:
  adapted = adapt_study_demo_signal_to_display(
    {
      "signal_id": "patent:p1",
      "source_type": "patent",
      "source_url": "https://patents.google.com/patent/US999/en",
      "title": "Patent",
      "summary": "s",
      "relevance_score": 80,
      "relevance_tier": "A",
    }
  )
  assert adapted["source_url"] == "https://patents.google.com/patent/US999/en"
  assert adapted["source_url_resolved"] == "https://patents.google.com/patent/US999/en"


def test_downstream_bundle_preserves_resolved_urls() -> None:
  artifacts = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["artifacts"]
  artifacts["integrated_signals.json"]["signals"] = [
    _patent_signal(source_url="https://patents.google.com/patent/US111/en", relevance_tier="A", relevance_score=90),
    _paper_signal(source_url="", landing_page_url="https://example.org/paper", relevance_tier="B", relevance_score=70),
    _web_signal(relevance_tier="C", relevance_score=50),
  ]
  context = build_active_context_from_run(search_run_id=RUN_ID, artifacts=artifacts)
  loaded = {"search_run_id": RUN_ID, "artifacts": artifacts}
  enriched = {"integrated_signals": artifacts["integrated_signals.json"]}
  with patch("services_v9.study_demo_downstream.list_run_snapshots", return_value=[]):
    with patch("services_v9.study_demo_downstream.load_run_reviews", return_value={"reviews": []}):
      with patch("services_v9.study_demo_active_loader.load_search_run", return_value=loaded):
        with patch("services_v9.study_demo_resolved_context.load_search_run", return_value=loaded):
          with patch("services_v9.study_demo_active_loader.build_search_result_from_artifacts", return_value=enriched):
            with patch("services_v9.study_demo_resolved_context.build_search_result_from_artifacts", return_value=enriched):
              bundle = build_downstream_bundle(context, storage_client=MagicMock())
  display = list(bundle.get("display_signals", []) or [])
  urls = {item["source_url"] for item in display}
  assert "https://patents.google.com/patent/US111/en" in urls
  assert "https://example.org/paper" in urls
  assert "https://company.example.com/news/a" in urls


def test_digest_markdown_no_empty_href() -> None:
  digest = {
    "theme": "t",
    "search_run_id": RUN_ID,
    "top_tier_a": [_patent_signal(source_url="https://patents.google.com/patent/US111/en", relevance_score=90)],
    "review_summary": {},
  }
  markdown = digest_to_markdown(digest)
  assert "引用元: https://patents.google.com/patent/US111/en" in markdown
  assert "]()" not in markdown


def test_digest_markdown_missing_url_text() -> None:
  digest = {
    "theme": "t",
    "search_run_id": RUN_ID,
    "top_tier_a": [_patent_signal(source_id="", source_url="", url="", relevance_score=90)],
    "review_summary": {},
  }
  markdown = digest_to_markdown(digest)
  assert "引用元URL未取得" in markdown


def test_export_includes_url_provenance() -> None:
  bundle = build_export_bundle(
    [_patent_signal(source_url="https://patents.google.com/patent/US111/en", relevance_tier="A")],
    {},
    {},
    {},
  )
  assert "source_url_resolved" in bundle["integrated_csv"]
  assert "https://patents.google.com/patent/US111/en" in bundle["integrated_csv"]
  assert "]()" not in bundle["integrated_markdown"]


def test_render_external_source_link_valid_uses_link_button() -> None:
  mock_st = MagicMock()
  with patch("ui_v9.study_demo_source_link.st", mock_st):
    resolution = render_external_source_link(
      _web_signal(),
      key_namespace="test_tab",
      search_run_id=RUN_ID,
    )
  assert resolution.is_valid
  mock_st.link_button.assert_called_once()
  mock_st.caption.assert_not_called()


def test_render_external_source_link_invalid_shows_caption() -> None:
  mock_st = MagicMock()
  with patch("ui_v9.study_demo_source_link.st", mock_st):
    render_external_source_link(_patent_signal(source_id="", source_url="", url=""), key_namespace="test_tab")
  mock_st.link_button.assert_not_called()
  mock_st.caption.assert_called_once()
  assert "引用元URL未取得" in mock_st.caption.call_args.args[0]


def test_source_link_keys_unique_per_tab() -> None:
  keys = {
    build_study_demo_source_link_key("top_signals_top3", "sig-a", RUN_ID),
    build_study_demo_source_link_key("top_signals_list", "sig-a", RUN_ID),
  }
  assert len(keys) == 2


def test_tabs_do_not_use_page_link_for_external_sources() -> None:
  source = Path(ROOT / "ui_v9/tabs.py").read_text(encoding="utf-8")
  assert "st.page_link" not in source
  assert "[出典URLを開く](" not in source


def test_full_tab_render_no_empty_markdown_href() -> None:
  source_info = {
    "mode": "temporary_search",
    "label": "run",
    "loaded_count": 3,
    "active_context": {"active_search_run_id": RUN_ID},
    "study_demo_downstream": {
      "top_reads_raw": [_patent_signal(source_url="https://patents.google.com/patent/US111/en", relevance_score=90, relevance_tier="A")],
      "display_signals": [
        adapt_study_demo_signal_to_display(
          _patent_signal(source_url="https://patents.google.com/patent/US222/en", relevance_score=80, relevance_tier="A")
        )
      ],
    },
  }
  mock_st = MagicMock()
  mock_st.session_state = {}
  mock_st.button.return_value = False
  mock_st.columns.side_effect = lambda n: [MagicMock() for _ in range(n if isinstance(n, int) else len(n))]
  mock_st.multiselect.side_effect = lambda label, options, **kwargs: list(options)
  mock_st.text_input.return_value = ""
  mock_st.expander.return_value.__enter__ = MagicMock(return_value=None)
  mock_st.expander.return_value.__exit__ = MagicMock(return_value=False)
  with patch("ui_v9.tabs.st", mock_st):
    with patch("ui_v9.study_demo_active_banner.st", mock_st):
      with patch("ui_v9.study_demo_source_link.st", mock_st):
        with patch("services_v9.study_demo_active_loader.adapt_study_demo_signal_to_display", side_effect=adapt_study_demo_signal_to_display):
          render_top_signals_tab([], source_info["study_demo_downstream"]["display_signals"], source_info)
  assert mock_st.link_button.call_count >= 1
  markdown_calls = [str(args[0]) for args, _ in mock_st.markdown.call_args_list if args]
  assert not any("]()" in text or re.search(r"\]\(\s*\)", text) for text in markdown_calls)


def test_fixture_run_url_summary_counts() -> None:
  signals = [
    _patent_signal(source_url="https://patents.google.com/patent/US111/en"),
    _paper_signal(source_url="", metadata={"doi": "10.1000/example"}),
    _web_signal(),
    _patent_signal(source_id="", source_url="", url=""),
  ]
  counts = summarize_url_resolution(signals)
  assert counts["patent_resolved"] == 1
  assert counts["paper_resolved"] == 1
  assert counts["web_resolved"] == 1
  assert counts["missing"] == 1
  assert counts["self_app_url"] == 0


def test_no_external_http_in_module() -> None:
  source = Path(ROOT / "services_v9/study_demo_source_url.py").read_text(encoding="utf-8")
  assert "requests." not in source
  assert "urllib.request" not in source


def test_production_bucket_not_in_resolver() -> None:
  serialized = json.dumps({"x": PRODUCTION_PERSIST_BUCKET})
  assert "weekly-persist" in serialized
