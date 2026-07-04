"""Readiness checks for persistent retrieval run reload."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from services_v9.paper_openalex_retrieval import save_openalex_paper_retrieval_artifacts
from services_v9.patent_bigquery_query import save_patent_retrieval_artifacts
from services_v9.retrieval_run_store import (
  build_retrieval_run_manifest,
  find_latest_compatible_manifest,
  load_candidates_from_manifest,
  load_paper_retrieval_artifact,
  load_patent_retrieval_artifact,
  load_retrieval_run_manifest,
  load_web_company_retrieval_artifact,
  save_retrieval_run_manifest,
  stable_payload_signature,
)
from services_v9.signal_integration import integrate_multi_source_signals
from services_v9.web_company_retrieval import save_global_web_retrieval_artifacts


def _watch_profile() -> dict[str, object]:
  return {
    "theme_name": "全固体電池ウォッチ",
    "theme_description": "Battery materials and manufacturing signals.",
    "keywords": {
      "core_en": ["solid state battery"],
      "core_ja": ["全固体電池"],
      "application_en": ["energy density"],
      "application_ja": ["高エネルギー密度"],
      "material_process_en": ["electrolyte"],
      "material_process_ja": ["電解質"],
      "exclude_en": [],
      "exclude_ja": [],
    },
    "target_companies": ["Toyota"],
    "source_types": ["patent", "paper", "web", "company"],
  }


def main() -> None:
  with tempfile.TemporaryDirectory(prefix="v9_retrieval_reload_") as temp_dir:
    base_dir = Path(temp_dir)
    patent_rows = [{
      "publication_number": "US2024000001A1",
      "family_id": "FAM1",
      "title": "Solid state battery patent",
      "abstract": "electrolyte",
      "assignee": "Toyota",
      "inventor": "Alice",
      "publication_date": "2026-05-12",
      "priority_date": "2025-06-01",
      "country": "US",
      "cpc_codes": "H01M",
      "source_url": "https://patents.example.com/p1",
      "query_id": "patent_q01",
      "retrieval_run_id": "patent_retrieval_patent_q01_20260704_120000",
      "provider_status": "success",
      "record_stage": "staged",
      "retrieval_mode": "real",
      "data_source": "bigquery_patent",
    }]
    paper_rows = [{
      "work_id": "https://openalex.org/W1",
      "doi": "10.1000/test1",
      "title": "Solid state battery paper",
      "abstract": "electrolyte",
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
    }]
    web_rows = [{
      "candidate_id": "w1",
      "query_id": "gw_q001",
      "country_region": "JP",
      "web_intent": "research_development",
      "result_bucket": "web",
      "original_title": "Toyota 全固体電池 研究開発",
      "original_snippet": "研究開発の更新",
      "original_language": "ja",
      "source_url": "https://example.co.jp/news/a",
      "canonical_url": "https://example.co.jp/news/a",
      "event_type": "research_development",
      "organization": "Toyota",
      "source_quality": "medium_high",
      "content_access": "full",
      "content_hash": "hash1",
      "same_story_group": "story_A",
      "summary_ja": "更新",
      "retrieval_run_id": "web_company_retrieval_20260704_120000",
      "provider_status": "partial_success",
      "record_stage": "staged",
      "retrieval_mode": "real",
    }]

    patent_paths = save_patent_retrieval_artifacts(
      {"sql": "SELECT 1", "request": {"query_id": "patent_q01"}, "parameters": [], "validation_rows": []},
      {"dry_run_status": "ok"},
      {"retrieval_run_id": patent_rows[0]["retrieval_run_id"], "provider_status": "success", "rows": patent_rows, "query_id": "patent_q01", "rows_retrieved": 1, "log": {}},
      base_dir=base_dir,
    )
    paper_paths = save_openalex_paper_retrieval_artifacts(
      {"request": {"query_id": "paper_q01"}, "url_preview": "https://api.openalex.org/works", "validation_rows": []},
      {"provider": "openalex", "query_id": "paper_q01", "retrieval_run_id": paper_rows[0]["retrieval_run_id"], "provider_status": "success", "rows": paper_rows, "pages_fetched": 1, "retry_limit": 2, "provider_log": []},
      base_dir=base_dir,
    )
    web_paths = save_global_web_retrieval_artifacts(
      {"request": {"query_id": "gw_q001"}, "validation_rows": []},
      {"retrieval_run_id": web_rows[0]["retrieval_run_id"], "provider_status": "partial_success", "rows": web_rows, "discovery_rows": [], "verification_rows": [], "provider_log": []},
      base_dir=base_dir,
    )

    patent = load_patent_retrieval_artifact(patent_paths["run_dir"])
    paper = load_paper_retrieval_artifact(paper_paths["run_dir"])
    web_company = load_web_company_retrieval_artifact(web_paths["run_dir"])
    assert patent["candidate_count"] == 1
    assert paper["candidate_count"] == 1
    assert web_company["status"] == "partial_success"

    profile = _watch_profile()
    manifest = build_retrieval_run_manifest(
      profile,
      {
        "patent": {"run_id": patent["run_id"], "artifact_dir": patent["artifact_dir"], "status": patent["status"], "candidate_count": patent["candidate_count"]},
        "paper": {"run_id": paper["run_id"], "artifact_dir": paper["artifact_dir"], "status": paper["status"], "candidate_count": paper["candidate_count"]},
        "web_company": {"run_id": web_company["run_id"], "artifact_dir": web_company["artifact_dir"], "status": web_company["status"], "candidate_count": web_company["candidate_count"]},
      },
    )
    manifest_path = save_retrieval_run_manifest(manifest, base_dir=base_dir)
    reloaded_manifest = load_retrieval_run_manifest(manifest_path, base_dir=base_dir)
    assert reloaded_manifest["watch_profile_signature"] == stable_payload_signature(profile)

    latest = find_latest_compatible_manifest(base_dir, stable_payload_signature(profile))
    assert latest is not None
    loaded_bundle = load_candidates_from_manifest(latest)
    assert loaded_bundle["status"] == "partial_success"
    assert len(loaded_bundle["candidates_by_source"]["patent"]) == 1
    assert len(loaded_bundle["candidates_by_source"]["paper"]) == 1
    assert len(loaded_bundle["candidates_by_source"]["web_company"]) == 1

    integrated = integrate_multi_source_signals(
      base_signals=[],
      watch_profile=profile,
      patent_rows=loaded_bundle["candidates_by_source"]["patent"],
      paper_rows=loaded_bundle["candidates_by_source"]["paper"],
      web_company_rows=loaded_bundle["candidates_by_source"]["web_company"],
      max_items=1000,
      ranking_limit=100,
    )
    assert integrated["ranked_count"] >= 2
    assert all(signal.get("data_origin") != "base_signal" for signal in integrated["signals"])

    labels_text = (PROJECT_ROOT / "ui_v9" / "labels.py").read_text(encoding="utf-8")
    tabs_text = (PROJECT_ROOT / "ui_v9" / "tabs.py").read_text(encoding="utf-8")
    assert '"retrieval_saved": "取得済みデータ"' in labels_text
    assert "現在の取得runを保存" in tabs_text
    assert "最新の保存済み取得結果を読み込む" in tabs_text

  print("[v9 retrieval run reload readiness] OK: persistent retrieval run reload is ready.")


if __name__ == "__main__":
  main()
