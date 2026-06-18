"""Tests for Patent × Paper × Web Signal linker (Phase 23.4)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from tech_cartography.reports.project_export import save_records_csv
from tech_cartography.web_signals.linker import (
  SUMMARY_CAUTION,
  WebSignalLinkCandidate,
  build_web_signal_link_candidates,
  build_web_signal_link_pack,
  deduplicate_link_candidates,
  extract_technology_terms,
  match_terms,
  normalize_text_for_matching,
  render_next_verification_actions_md,
  render_patent_paper_web_signal_summary_md,
  save_web_signal_link_pack,
  score_link_candidate,
)


def _write_fixture(root: Path) -> None:
  pub = "US-12565719-B2"
  ev_dir = root / "outputs" / "evidence_map_synthesis" / pub
  oa_dir = root / "outputs" / "openalex_limited_execution"
  review_dir = root / "outputs" / "web_signals" / "tavily_pan_carbon_fiber" / "review_pack"
  ev_dir.mkdir(parents=True, exist_ok=True)
  oa_dir.mkdir(parents=True, exist_ok=True)
  review_dir.mkdir(parents=True, exist_ok=True)

  (ev_dir / "evidence_map_synthesis.json").write_text(
    json.dumps({"publication_number": pub, "title": "Carbon fiber patent"}),
    encoding="utf-8",
  )
  save_records_csv(
    [
      {
        "claim_element": "CE-1",
        "claim_element_text": "a PAN-based carbon fiber with carbonization stabilization",
      },
    ],
    ev_dir / "evidence_map_items.csv",
  )
  save_records_csv(
    [
      {
        "title": "Carbon fiber composite aerospace application",
        "paper_id": "paper-1",
        "keywords": "CFRP composite",
      },
    ],
    oa_dir / "selected_evidence_papers.csv",
  )
  save_records_csv(
    [
      {
        "claim_element": "CE-1",
        "claim_element_text": "PAN carbon fiber",
        "paper_title": "Carbon fiber composite aerospace application",
      },
    ],
    oa_dir / "claim_paper_candidate_links.csv",
  )
  save_records_csv(
    [
      {
        "signal_id": "wsig-nedo-1",
        "signal_type": "national_project",
        "source_title": "NEDO CFRP high-rate production technology",
        "source_url": "https://www.nedo.go.jp/project/1",
        "source_domain": "nedo.go.jp",
        "source_quality": "high",
        "evidence_sentences": "炭素繊維 CFRP composite project",
        "confidence": "medium",
        "verification_status": "needs_human_review",
      },
      {
        "signal_id": "wsig-ir-1",
        "signal_type": "ir_disclosure",
        "source_title": "Carbon fiber earnings presentation",
        "source_url": "https://example.co.jp/ir/earnings",
        "source_domain": "example.co.jp",
        "source_quality": "medium_high",
        "evidence_sentences": "carbon fiber composite investment",
        "confidence": "low",
        "verification_status": "needs_human_review",
      },
    ],
    review_dir / "high_priority_web_signals.csv",
  )
  save_records_csv(
    [
      {
        "signal_id": "wsig-nedo-1",
        "signal_type": "national_project",
        "source_title": "NEDO CFRP high-rate production technology",
        "source_url": "https://www.nedo.go.jp/project/1",
        "source_domain": "nedo.go.jp",
        "source_quality": "high",
        "evidence_sentences": "炭素繊維 CFRP composite project",
      },
    ],
    review_dir / "money_national_project_candidates.csv",
  )
  save_records_csv([], review_dir / "web_signal_review_items.csv")
  save_records_csv([], review_dir / "ir_disclosure_candidates.csv")
  save_records_csv([], review_dir / "company_local_news_candidates.csv")


def test_extract_technology_terms_english() -> None:
  terms = extract_technology_terms("PAN carbon fiber carbonization composite")
  assert "carbon fiber" in terms
  assert "carbonization" in terms


def test_extract_technology_terms_japanese() -> None:
  terms = extract_technology_terms("PAN系 炭素繊維 炭化 複合材料")
  assert "炭素繊維" in terms
  assert "炭化" in terms


def test_match_terms() -> None:
  matched = match_terms("PAN carbon fiber composite", "carbon fiber CFRP aerospace")
  assert "carbon fiber" in matched


def test_normalize_text_for_matching() -> None:
  assert normalize_text_for_matching("  PAN   Carbon Fiber ") == "pan carbon fiber"


def test_score_high_quality_higher() -> None:
  high = score_link_candidate(
    matched_terms=["carbon fiber", "composite", "cfrp"],
    source_quality="high",
    web_signal_type="national_project",
    web_signal_domain="nedo.go.jp",
    evidence_sentence="Carbon fiber project",
    has_claim_match=True,
    has_paper_match=False,
    source_url="https://example.com",
  )
  low = score_link_candidate(
    matched_terms=["pan"],
    source_quality="low",
    web_signal_type="other",
    web_signal_domain="blog.example",
    evidence_sentence=None,
    has_claim_match=False,
    has_paper_match=False,
    source_url="",
  )
  assert high > low


def test_no_high_confidence() -> None:
  score = score_link_candidate(
    matched_terms=["carbon fiber", "composite", "cfrp"],
    source_quality="high",
    web_signal_type="national_project",
    web_signal_domain="nedo.go.jp",
    evidence_sentence="Carbon fiber",
    has_claim_match=True,
    has_paper_match=True,
    source_url="https://nedo.go.jp",
  )
  from tech_cartography.web_signals.linker import _confidence_from_score

  assert _confidence_from_score(score) in {"medium", "low", "weak"}
  assert _confidence_from_score(score) != "high"


def test_build_links_national_project_context(tmp_path: Path) -> None:
  _write_fixture(tmp_path)
  pack = build_web_signal_link_pack(
    publication_number="US-12565719-B2",
    project_root=tmp_path,
    min_link_score=30,
    top_n=50,
  )
  assert pack.link_candidates
  assert any(item.link_type == "project_context_match" for item in pack.link_candidates)


def test_build_links_ir_disclosure_company_context(tmp_path: Path) -> None:
  _write_fixture(tmp_path)
  review_dir = tmp_path / "outputs/web_signals/tavily_pan_carbon_fiber/review_pack"
  save_records_csv(
    [
      {
        "signal_id": "wsig-ir-1",
        "signal_type": "ir_disclosure",
        "source_title": "Carbon fiber integrated report",
        "source_url": "https://example.co.jp/ir",
        "source_domain": "example.co.jp",
        "source_quality": "medium_high",
        "evidence_sentences": "carbon fiber composite",
      },
    ],
    review_dir / "ir_disclosure_candidates.csv",
  )
  pack = build_web_signal_link_pack(
    publication_number="US-12565719-B2",
    project_root=tmp_path,
    min_link_score=30,
    top_n=50,
  )
  assert any(item.web_signal_type == "ir_disclosure" for item in pack.link_candidates)
  assert any(item.link_type == "company_context_match" for item in pack.link_candidates)


def test_empty_inputs_do_not_crash(tmp_path: Path) -> None:
  pack = build_web_signal_link_pack(
    publication_number="US-12565719-B2",
    project_root=tmp_path,
    min_link_score=40,
    top_n=20,
  )
  assert pack.link_candidates == []


def test_deduplicate_same_web_signal_claim_paper_type() -> None:
  base = dict(
    publication_number="US-1",
    claim_element_id="CE-1",
    claim_element_text="carbon fiber",
    paper_id=None,
    paper_title="Paper",
    web_signal_id="wsig-1",
    web_signal_type="national_project",
    web_signal_title="NEDO",
    web_signal_url="https://nedo.go.jp",
    web_signal_domain="nedo.go.jp",
    source_quality="high",
    link_type="project_context_match",
    matched_terms=["carbon fiber"],
    matched_contexts=["claim_element"],
    evidence_sentence="carbon fiber",
    confidence="medium",
    verification_status="needs_human_review",
    caveat="c",
    next_verification_action="a",
  )
  a = WebSignalLinkCandidate(link_id="a", link_score=70, **base)
  b = WebSignalLinkCandidate(link_id="b", link_score=80, **base)
  deduped = deduplicate_link_candidates([a, b])
  assert len(deduped) == 1
  assert deduped[0].link_score == 80


def test_summary_markdown_contains_caution(tmp_path: Path) -> None:
  _write_fixture(tmp_path)
  pack = build_web_signal_link_pack(
    publication_number="US-12565719-B2",
    project_root=tmp_path,
    min_link_score=30,
    top_n=50,
  )
  summary = render_patent_paper_web_signal_summary_md(pack)
  assert "link candidates, not final conclusions" in summary
  assert "FTO, infringement, or validity analysis" in summary
  assert SUMMARY_CAUTION.splitlines()[0] in summary


def test_next_verification_actions_md() -> None:
  md = render_next_verification_actions_md()
  assert "NEDO" in md
  assert "IR / disclosure" in md


def test_save_outputs(tmp_path: Path) -> None:
  _write_fixture(tmp_path)
  pack = build_web_signal_link_pack(
    publication_number="US-12565719-B2",
    project_root=tmp_path,
    min_link_score=30,
    top_n=50,
  )
  out = tmp_path / "outputs/web_signal_links/US-12565719-B2"
  paths = save_web_signal_link_pack(pack, out)
  for name in (
    "web_signal_link_candidates.json",
    "web_signal_link_candidates.csv",
    "high_priority_web_signal_links.csv",
    "patent_paper_web_signal_summary.md",
    "next_verification_actions.md",
  ):
    assert (out / name).exists(), name
  assert paths["patent_paper_web_signal_summary_md"].exists()


def test_evidence_sentence_missing_lowers_score() -> None:
  with_evidence = score_link_candidate(
    matched_terms=["carbon fiber"],
    source_quality="medium",
    web_signal_type="company",
    web_signal_domain="example.co.jp",
    evidence_sentence="carbon fiber",
    has_claim_match=True,
    has_paper_match=False,
    source_url="https://example.com",
  )
  without_evidence = score_link_candidate(
    matched_terms=["carbon fiber"],
    source_quality="medium",
    web_signal_type="company",
    web_signal_domain="example.co.jp",
    evidence_sentence=None,
    has_claim_match=True,
    has_paper_match=False,
    source_url="https://example.com",
  )
  assert with_evidence > without_evidence
