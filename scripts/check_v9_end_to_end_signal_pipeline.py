"""Readiness checks for the v9 end-to-end multi-source signal pipeline."""

from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from services_v9.digest_export import build_weekly_digest_markdown
from services_v9.review_state import apply_reviews_to_signals
from services_v9.search_plan import build_unified_search_plan
from services_v9.signal_integration import build_source_top_signals, integrate_multi_source_signals
from services_v9.signal_models import Signal, WatchProfile
from services_v9.signal_scoring import select_diverse_top_signals, select_top_reads


def _watch_profile() -> dict[str, object]:
  return {
    "theme_name": "Battery materials",
    "theme_description": "Monitor next-gen battery materials and manufacturing signals.",
    "keywords": {
      "core_en": ["solid state battery", "cathode"],
      "core_ja": ["全固体電池", "正極材"],
      "application_en": ["energy density", "cycle life"],
      "application_ja": ["高エネルギー密度"],
      "material_process_en": ["electrolyte", "sintering"],
      "material_process_ja": ["電解質", "焼結"],
      "exclude_en": ["review"],
      "exclude_ja": [],
    },
    "target_companies": ["Toyota", "Panasonic", "Samsung"],
    "source_types": ["patent", "paper", "web", "company"],
  }


def _base_signals() -> list[dict[str, object]]:
  return [
    {
      "id": "demo_001",
      "title": "Battery demo baseline",
      "type": "web",
      "source_url": "https://demo.example.com/baseline",
      "source_name": "Demo",
      "published_date": "2026-06-01",
      "summary": "baseline signal",
      "score": 0.70,
      "previous_score": 0.62,
      "status": "Rising",
      "action": "Read Now",
      "why_read": "demo baseline",
      "what_to_check": "baseline",
      "next_action": "baseline",
      "tags": ["battery"],
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
      "record_stage": "staged",
      "retrieval_mode": "real",
      "data_source": "bigquery_patent",
    },
    {
      "candidate_id": "p2",
      "publication_number": "US2024000001A1",
      "family_id": "FAM1",
      "title": "Solid state battery patent duplicate publication",
      "abstract": "electrolyte duplicate",
      "assignee": "Toyota",
      "publication_date": "2026-05-11",
      "country": "US",
      "cpc_codes": "H01M",
      "source_url": "https://patents.example.com/p1b",
      "query_id": "patent_q01",
      "retrieval_run_id": "patent_retrieval_patent_q01_20260704_120000",
      "bigquery_job_id": "job1",
      "provider_status": "success",
      "record_stage": "staged",
      "retrieval_mode": "real",
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
      "record_stage": "staged",
      "retrieval_mode": "real",
    },
    {
      "work_id": "https://openalex.org/W1b",
      "doi": "10.1000/test1",
      "title": "Solid state battery paper duplicate DOI",
      "abstract": "same doi duplicate",
      "authors": ["Bob"],
      "institutions": ["Example University"],
      "publication_date": "2025-12-02",
      "source_journal": "Battery Journal",
      "cited_by_count": 8,
      "topics": ["Solid electrolytes"],
      "open_access": True,
      "original_language": "en",
      "source_url": "https://example.org/paper1b",
      "query_id": "paper_q01",
      "retrieval_run_id": "paper_retrieval_paper_q01_20260704_120000",
      "provider_status": "success",
      "record_stage": "staged",
      "retrieval_mode": "real",
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
      "source_url": "https://company.example.com/pr/factory?utm_campaign=x",
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
    {
      "candidate_id": "c2",
      "query_id": "gw_q004",
      "country_region": "KR",
      "web_intent": "product_commercialization",
      "result_bucket": "company",
      "original_title": "Samsung battery launch",
      "original_snippet": "new battery launch",
      "original_language": "en",
      "source_url": "https://samsung.example.com/pr/launch",
      "canonical_url": "https://samsung.example.com/pr/launch",
      "event_type": "product_commercialization",
      "organization": "Samsung",
      "source_quality": "high",
      "content_access": "full",
      "content_hash": "hash4",
      "same_story_group": "story_C",
      "summary_ja": "製品投入候補",
      "retrieval_run_id": "web_company_retrieval_20260704_120000",
      "provider_status": "success",
      "record_stage": "staged",
      "retrieval_mode": "real",
    },
  ]


def main() -> int:
  errors: list[str] = []
  profile = _watch_profile()
  plan = build_unified_search_plan(profile)
  if "plans" not in plan or "global_web_plan" not in plan:
    errors.append("検索計画を生成できません")

  patent_rows = _patent_rows()
  paper_rows = _paper_rows()
  web_company_rows = _web_company_rows()
  original_patent = deepcopy(patent_rows)
  original_paper = deepcopy(paper_rows)
  original_web_company = deepcopy(web_company_rows)

  integrated = integrate_multi_source_signals(
    base_signals=_base_signals(),
    watch_profile=profile,
    patent_rows=patent_rows,
    paper_rows=paper_rows,
    web_company_rows=web_company_rows,
  )
  if integrated["raw_count"] != 9:
    errors.append("4情報源の候補を統合できていません")
  if integrated["deduped_count"] >= integrated["raw_count"]:
    errors.append("重複除去が動いていません")

  signals = integrated["signals"]
  if {signal["type"] for signal in signals} < {"patent", "paper", "web", "company"}:
    errors.append("4情報源が共通Signalへ揃っていません")
  if not all(signal["source_url"] for signal in signals):
    errors.append("source_url を保持できていません")
  if not all(signal["data_origin"] for signal in signals):
    errors.append("data_origin を保持できていません")
  if not all(signal["record_stage"] == "staged" or signal["data_origin"] == "base_signal" for signal in signals):
    errors.append("staged / real の区別を保持できていません")
  ranks = [int(signal["current_rank"]) for signal in signals]
  if ranks != list(range(1, len(ranks) + 1)):
    errors.append("rank が連番になっていません")

  patent_external_ids = [signal["external_id"] for signal in signals if signal["type"] == "patent"]
  if patent_external_ids.count("US2024000001A1") != 1:
    errors.append("publication number 重複を除去できていません")
  paper_external_ids = [signal["external_id"] for signal in signals if signal["type"] == "paper"]
  if paper_external_ids.count("10.1000/test1") != 1:
    errors.append("DOI 重複を除去できていません")
  web_duplicate_groups = [signal["duplicate_group"] for signal in signals if signal["type"] == "web"]
  if len(web_duplicate_groups) != len(set(web_duplicate_groups)):
    errors.append("same story group / normalized URL 重複を除去できていません")

  top10 = select_diverse_top_signals([Signal.from_dict(signal) for signal in signals], top_n=10)
  if len(top10) > 10:
    errors.append("UI Top10 相当を制御できていません")
  top_by_source = build_source_top_signals(signals, top_n=5)
  if any(len(top_by_source[source]) > 5 for source in ("patent", "paper", "web", "company")):
    errors.append("情報源別Top5 相当を制御できていません")
  digest_top3 = select_top_reads([Signal.from_dict(signal) for signal in signals], limit=3)
  if len(digest_top3) > 3:
    errors.append("Digest Top3 相当を制御できていません")

  reviewed_signals = apply_reviews_to_signals(
    signals,
    {
      str(signals[0]["id"]): {"review_decision": "採用", "review_priority": 1, "review_comment": "keep", "reviewed": True},
      str(signals[1]["id"]): {"review_decision": "保留", "review_priority": 2, "review_comment": "watch", "reviewed": True},
    },
  )
  digest = build_weekly_digest_markdown(
    [Signal.from_dict(signal) for signal in signals],
    WatchProfile.from_dict(profile),
    data_source="integrated",
    loaded_count=len(signals),
    reviewed_signals=reviewed_signals,
  )
  if "Tech Cartography v9 週次ダイジェスト" not in digest or "人間レビュー状況" not in digest:
    errors.append("Digest を生成できていません")

  if patent_rows != original_patent or paper_rows != original_paper or web_company_rows != original_web_company:
    errors.append("元candidateを変更しています")

  if errors:
    for message in errors:
      print(f"[v9 end-to-end signal pipeline] ERROR: {message}")
    return 1
  print("[v9 end-to-end signal pipeline] OK: multi-source signal pipeline is ready.")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
