"""Tests for v9 multi-source signal integration."""

from __future__ import annotations

from pathlib import Path

from services_v9.signal_integration import (
  apply_signal_change_tracking,
  build_source_top_signals,
  deduplicate_signal_candidates,
  integrate_multi_source_signals,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = (PROJECT_ROOT / "ui_v9" / "signal_watch_app.py").read_text(encoding="utf-8")
TABS_SOURCE = (PROJECT_ROOT / "ui_v9" / "tabs.py").read_text(encoding="utf-8")


def _watch_profile() -> dict[str, object]:
  return {
    "theme_name": "Battery materials",
    "theme_description": "Monitor next-gen battery materials.",
    "keywords": {
      "core_en": ["solid state battery", "cathode"],
      "core_ja": ["全固体電池", "正極材"],
      "application_en": ["energy density"],
      "application_ja": ["高エネルギー密度"],
      "material_process_en": ["electrolyte", "sintering"],
      "material_process_ja": ["電解質"],
      "exclude_en": ["review"],
      "exclude_ja": [],
    },
    "target_companies": ["Toyota"],
    "source_types": ["patent", "paper", "web", "company"],
  }


def _base_signals() -> list[dict[str, object]]:
  return [
    {
      "id": "demo_001",
      "title": "Demo cathode update",
      "type": "web",
      "source_url": "https://demo.example.com/a",
      "source_name": "Demo",
      "published_date": "2026-06-01",
      "summary": "cathode news",
      "score": 0.72,
      "previous_score": 0.60,
      "status": "Rising",
      "action": "Read Now",
      "why_read": "demo",
      "what_to_check": "demo",
      "next_action": "demo",
      "tags": ["cathode"],
      "companies": ["Toyota"],
      "language": "en",
      "memo": "",
    },
  ]


def _patent_rows() -> list[dict[str, object]]:
  return [
    {
      "candidate_id": "p1",
      "publication_number": "US2024000001A1",
      "family_id": "FAM1",
      "title": "Solid state battery patent",
      "abstract": "electrolyte cathode process",
      "assignee": "Toyota",
      "publication_date": "2026-05-12",
      "country": "US",
      "cpc_codes": "H01M",
      "source_url": "https://patents.example.com/p1",
      "query_id": "patent_q01",
      "retrieval_run_id": "patent_retrieval_patent_q01_20260704_120000",
      "bigquery_job_id": "job1",
      "provider_status": "success",
      "data_source": "bigquery_patent",
    },
    {
      "candidate_id": "p2",
      "publication_number": "US2024000002A1",
      "family_id": "FAM1",
      "title": "Solid state battery patent duplicate family",
      "abstract": "electrolyte variant",
      "assignee": "Toyota",
      "publication_date": "2026-05-10",
      "country": "US",
      "cpc_codes": "H01M",
      "source_url": "https://patents.example.com/p2",
      "query_id": "patent_q01",
      "retrieval_run_id": "patent_retrieval_patent_q01_20260704_120000",
      "bigquery_job_id": "job1",
      "provider_status": "success",
      "data_source": "bigquery_patent",
      "family_duplicate_candidate": True,
    },
  ]


def _paper_rows() -> list[dict[str, object]]:
  return [
    {
      "work_id": "https://openalex.org/W1",
      "doi": "10.1000/test1",
      "title": "Solid state battery paper",
      "abstract": "electrolyte cathode",
      "authors": ["Alice"],
      "institutions": ["Example University"],
      "publication_date": "2025-12-01",
      "source_journal": "Battery Journal",
      "cited_by_count": 12,
      "topics": ["Solid electrolytes"],
      "open_access": True,
      "original_language": "en",
      "source_url": "https://example.org/paper1",
      "query_id": "paper_q01",
      "retrieval_run_id": "paper_retrieval_paper_q01_20260704_120000",
      "provider_status": "success",
    },
  ]


def _web_company_rows() -> list[dict[str, object]]:
  return [
    {
      "candidate_id": "w1",
      "query_id": "gw_q001",
      "country_region": "JP",
      "web_intent": "research_development",
      "result_bucket": "web",
      "original_title": "Toyota 全固体電池 研究開発",
      "original_snippet": "研究開発の更新",
      "original_language": "ja",
      "source_url": "https://example.co.jp/news/a?utm_source=test",
      "canonical_url": "https://example.co.jp/news/a",
      "event_type": "research_development",
      "organization": "Toyota",
      "source_quality": "medium_high",
      "content_access": "full",
      "content_hash": "hash1",
      "same_story_group": "story_A",
      "summary_ja": "Toyotaの研究開発更新",
      "retrieval_run_id": "web_company_retrieval_20260704_120000",
      "provider_status": "success",
      "record_stage": "staged",
      "retrieval_mode": "real",
    },
    {
      "candidate_id": "w2",
      "query_id": "gw_q002",
      "country_region": "JP",
      "web_intent": "research_development",
      "result_bucket": "web",
      "original_title": "Toyota 全固体電池 研究開発 続報",
      "original_snippet": "同じニュース群",
      "original_language": "ja",
      "source_url": "https://another.example.co.jp/news/a",
      "canonical_url": "https://another.example.co.jp/news/a",
      "event_type": "research_development",
      "organization": "Toyota",
      "source_quality": "medium",
      "content_access": "partial",
      "content_hash": "hash2",
      "same_story_group": "story_A",
      "summary_ja": "同一ニュース群",
      "retrieval_run_id": "web_company_retrieval_20260704_120000",
      "provider_status": "success",
      "record_stage": "staged",
      "retrieval_mode": "real",
    },
    {
      "candidate_id": "c1",
      "query_id": "gw_q003",
      "country_region": "US",
      "web_intent": "investment_production",
      "result_bucket": "company",
      "original_title": "Toyota battery factory investment",
      "original_snippet": "factory investment",
      "original_language": "en",
      "source_url": "https://company.example.com/pr/factory",
      "canonical_url": "https://company.example.com/pr/factory",
      "event_type": "investment_production",
      "organization": "Toyota",
      "source_quality": "high",
      "content_access": "full",
      "content_hash": "hash3",
      "same_story_group": "story_B",
      "summary_ja": "工場投資候補",
      "retrieval_run_id": "web_company_retrieval_20260704_120000",
      "provider_status": "success",
      "record_stage": "staged",
      "retrieval_mode": "real",
    },
  ]


def test_deduplicate_groups_merge_patent_family_and_story_group() -> None:
  integrated = integrate_multi_source_signals(
    base_signals=_base_signals(),
    watch_profile=_watch_profile(),
    patent_rows=_patent_rows(),
    paper_rows=_paper_rows(),
    web_company_rows=_web_company_rows(),
  )
  assert integrated["raw_count"] == 7
  assert integrated["deduped_count"] < integrated["raw_count"]
  assert integrated["ranked_count"] <= 100


def test_integrated_signals_keep_existing_fields_and_add_trace() -> None:
  integrated = integrate_multi_source_signals(
    base_signals=_base_signals(),
    watch_profile=_watch_profile(),
    patent_rows=_patent_rows(),
    paper_rows=_paper_rows(),
    web_company_rows=_web_company_rows(),
  )
  signal = integrated["signals"][0]
  for field in ("id", "title", "type", "source_url", "summary", "status", "action"):
    assert field in signal
  for field in ("signal_id", "run_id", "source_subtype", "external_id", "source_trace", "duplicate_group", "data_origin"):
    assert field in signal
  assert isinstance(signal["source_trace"], list)
  assert signal["score"] == signal["final_score"]


def test_build_source_top_signals_returns_top5_per_type() -> None:
  integrated = integrate_multi_source_signals(
    base_signals=_base_signals(),
    watch_profile=_watch_profile(),
    patent_rows=_patent_rows(),
    paper_rows=_paper_rows(),
    web_company_rows=_web_company_rows(),
  )
  by_source = build_source_top_signals(integrated["signals"], top_n=5)
  assert set(by_source.keys()) >= {"patent", "paper", "web", "company"}
  assert len(by_source["patent"]) <= 5


def test_apply_signal_change_tracking_sets_previous_rank_and_updated() -> None:
  integrated = integrate_multi_source_signals(
    base_signals=_base_signals(),
    watch_profile=_watch_profile(),
    patent_rows=_patent_rows(),
    paper_rows=_paper_rows(),
    web_company_rows=_web_company_rows(),
  )
  current = integrated["signals"]
  previous = []
  for signal in current:
    copied = dict(signal)
    copied["current_rank"] = int(signal["current_rank"]) + 1
    copied["summary"] = str(signal.get("summary", "")) + " old"
    previous.append(copied)
  updated = apply_signal_change_tracking(current, previous)
  assert all(item.get("previous_rank") is not None for item in updated)
  assert any(item.get("change_status") in {"Rising", "Updated", "Dropped", "Stable"} for item in updated)


def test_app_source_wires_integrated_signal_flow() -> None:
  assert "integrate_multi_source_signals(" in APP_SOURCE
  assert "apply_signal_change_tracking(" in APP_SOURCE
  assert "情報源別Top5" in TABS_SOURCE
