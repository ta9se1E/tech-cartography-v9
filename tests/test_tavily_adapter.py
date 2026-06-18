"""Tests for Tavily Web Signal adapter (Phase 23.1)."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest

from tech_cartography.web_signals.tavily_adapter import (
  build_tavily_extract_payload,
  build_tavily_search_payload,
  get_tavily_api_key,
  run_tavily_extract,
  run_tavily_search,
  tavily_search_results_to_web_signals,
)


def test_get_tavily_api_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv("TAVILY_API_KEY", raising=False)
  assert get_tavily_api_key() is None


def test_get_tavily_api_key_present(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("TAVILY_API_KEY", "test-key")
  assert get_tavily_api_key() == "test-key"


def test_build_tavily_search_payload_shape() -> None:
  payload = build_tavily_search_payload(
    "PAN carbon fiber NEDO",
    max_results=5,
    include_domains=["nedo.go.jp"],
    exclude_domains=["linkedin.com"],
  )
  assert payload["query"] == "PAN carbon fiber NEDO"
  assert payload["max_results"] == 5
  assert payload["include_domains"] == ["nedo.go.jp"]
  assert payload["exclude_domains"] == ["linkedin.com"]


def test_build_tavily_extract_payload_shape() -> None:
  payload = build_tavily_extract_payload(["https://example.com/a", "https://example.com/b"])
  assert payload["urls"] == ["https://example.com/a", "https://example.com/b"]


def test_run_tavily_search_missing_api_key() -> None:
  result = run_tavily_search("test", api_key="")
  assert result["error"] == "missing_api_key"


def test_run_tavily_extract_missing_api_key() -> None:
  result = run_tavily_extract(["https://example.com"], api_key="")
  assert result["error"] == "missing_api_key"


MOCK_SEARCH_RESPONSE = {
  "results": [
    {
      "title": "Carbon fiber earnings presentation expansion investment",
      "url": "https://example.co.jp/ir/earnings",
      "content": "Investor relations earnings presentation for carbon fiber business.",
    },
    {
      "title": "NEDO carbon fiber project grant",
      "url": "https://www.nedo.go.jp/project/carbon-fiber",
      "content": "National project grant notice for carbon fiber R&D.",
    },
  ],
}


def test_tavily_search_results_to_web_signals() -> None:
  signals = tavily_search_results_to_web_signals(
    MOCK_SEARCH_RESPONSE,
    query="carbon fiber",
    default_signal_type="company",
    query_category="ir_disclosure",
  )
  assert len(signals) == 2
  ir_signals = [signal for signal in signals if signal.signal_type == "ir_disclosure"]
  assert ir_signals
  assert ir_signals[0].source_kind == "tavily_search"
  assert ir_signals[0].verification_status == "needs_human_review"
  assert ir_signals[0].confidence in {"low", "medium"}
  assert ir_signals[0].source_quality
  assert ir_signals[0].source_category


def test_ir_disclosure_classification_from_title() -> None:
  signals = tavily_search_results_to_web_signals(
    {
      "results": [
        {
          "title": "炭素繊維 決算説明資料 研究開発",
          "url": "https://corp.example.co.jp/ir/library/earnings.pdf",
          "content": "決算説明資料",
        },
      ],
    },
    query="炭素繊維 IR",
    default_signal_type="other",
    query_category="ir_disclosure",
  )
  assert signals[0].signal_type == "ir_disclosure"
  assert signals[0].disclosure_type in {"earnings_presentation", "financial_results", "unknown"}


def test_edinet_disclosure_platform_quality() -> None:
  signals = tavily_search_results_to_web_signals(
    {
      "results": [
        {
          "title": "有価証券報告書",
          "url": "https://disclosure2.edinet-fsa.go.jp/document/123",
          "content": "securities report filing",
        },
      ],
    },
    query="carbon fiber securities report",
    default_signal_type="other",
    query_category="ir_disclosure",
  )
  assert signals[0].signal_type in {"ir_disclosure", "disclosure"}
  assert signals[0].source_quality == "high"
  assert signals[0].source_category == "disclosure_platform"
  assert signals[0].confidence == "medium"
  assert signals[0].verification_status != "verified_source"


def test_empty_source_url_caps_confidence() -> None:
  signals = tavily_search_results_to_web_signals(
    {"results": [{"title": "x", "url": "", "content": "y"}]},
    query="q",
    default_signal_type="other",
  )
  assert signals[0].confidence != "high"


@patch("tech_cartography.web_signals.tavily_adapter._post_tavily")
def test_run_tavily_search_delegates(mock_post) -> None:
  mock_post.return_value = {"results": []}
  result = run_tavily_search("q", api_key="secret", max_results=3)
  assert "results" in result
  mock_post.assert_called_once()
