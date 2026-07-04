"""Tests for persistent retrieval run reload in v9."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from streamlit.testing.v1 import AppTest

from services_v9.digest_export import build_weekly_digest_markdown
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
from services_v9.review_state import apply_reviews_to_signals
from services_v9.signal_integration import integrate_multi_source_signals
from services_v9.signal_models import Signal, WatchProfile
from ui_v9 import signal_watch_app

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _watch_profile() -> dict[str, object]:
  return {
    "theme_name": "全固体電池ウォッチ",
    "theme_description": "Battery materials and manufacturing signals.",
    "keywords": {
      "core_en": ["solid state battery", "cathode"],
      "core_ja": ["全固体電池", "正極材"],
      "application_en": ["energy density"],
      "application_ja": ["高エネルギー密度"],
      "material_process_en": ["electrolyte"],
      "material_process_ja": ["電解質"],
      "exclude_en": [],
      "exclude_ja": [],
    },
    "target_companies": ["Toyota", "Samsung"],
    "source_types": ["patent", "paper", "web", "company"],
  }


def _patent_rows() -> list[dict[str, object]]:
  return [
    {
      "publication_number": "US2024000001A1",
      "family_id": "FAM1",
      "title": "Solid state battery patent",
      "abstract": "electrolyte cathode process",
      "assignee": "Toyota",
      "inventor": "Alice",
      "publication_date": "2026-05-12",
      "priority_date": "2025-06-01",
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
      "provider_status": "partial_success",
      "record_stage": "staged",
      "retrieval_mode": "real",
    },
  ]


def _build_artifacts(tmp_path: Path) -> dict[str, dict[str, object]]:
  patent_rows = _patent_rows()
  paper_rows = _paper_rows()
  web_company_rows = _web_company_rows()
  patent_paths = save_patent_retrieval_artifacts(
    {
      "sql": "SELECT 1",
      "request": {"query_id": "patent_q01"},
      "parameters": [],
      "validation_rows": [],
    },
    {"dry_run_status": "ok"},
    {
      "retrieval_run_id": patent_rows[0]["retrieval_run_id"],
      "provider_status": "success",
      "rows": patent_rows,
      "query_id": "patent_q01",
      "rows_retrieved": len(patent_rows),
      "log": {"provider": "bigquery"},
    },
    base_dir=tmp_path,
  )
  paper_paths = save_openalex_paper_retrieval_artifacts(
    {
      "request": {"query_id": "paper_q01"},
      "url_preview": "https://api.openalex.org/works?...",
      "validation_rows": [],
    },
    {
      "provider": "openalex",
      "query_id": "paper_q01",
      "retrieval_run_id": paper_rows[0]["retrieval_run_id"],
      "provider_status": "success",
      "rows": paper_rows,
      "pages_fetched": 1,
      "retry_limit": 2,
      "provider_log": [],
    },
    base_dir=tmp_path,
  )
  from services_v9.web_company_retrieval import save_global_web_retrieval_artifacts

  web_paths = save_global_web_retrieval_artifacts(
    {
      "request": {"query_id": "gw_q001"},
      "validation_rows": [],
    },
    {
      "retrieval_run_id": web_company_rows[0]["retrieval_run_id"],
      "provider_status": "partial_success",
      "rows": web_company_rows,
      "discovery_rows": [],
      "verification_rows": [],
      "provider_log": [],
    },
    base_dir=tmp_path,
  )
  return {
    "patent": {
      "rows": patent_rows,
      "run_dir": patent_paths["run_dir"],
      "status": "success",
      "run_id": patent_rows[0]["retrieval_run_id"],
    },
    "paper": {
      "rows": paper_rows,
      "run_dir": paper_paths["run_dir"],
      "status": "success",
      "run_id": paper_rows[0]["retrieval_run_id"],
    },
    "web_company": {
      "rows": web_company_rows,
      "run_dir": web_paths["run_dir"],
      "status": "partial_success",
      "run_id": web_company_rows[0]["retrieval_run_id"],
    },
  }


def test_load_artifacts_and_manifest_roundtrip(tmp_path: Path) -> None:
  artifacts = _build_artifacts(tmp_path)
  patent = load_patent_retrieval_artifact(artifacts["patent"]["run_dir"])
  paper = load_paper_retrieval_artifact(artifacts["paper"]["run_dir"])
  web_company = load_web_company_retrieval_artifact(artifacts["web_company"]["run_dir"])

  assert patent["run_id"] == artifacts["patent"]["run_id"]
  assert paper["run_id"] == artifacts["paper"]["run_id"]
  assert web_company["status"] == "partial_success"
  assert patent["candidate_count"] == 1
  assert paper["candidate_count"] == 1
  assert web_company["candidate_count"] == 1

  profile = _watch_profile()
  profile_signature = stable_payload_signature(profile)
  manifest = build_retrieval_run_manifest(
    profile,
    {
      "patent": {
        "run_id": patent["run_id"],
        "artifact_dir": patent["artifact_dir"],
        "status": patent["status"],
        "candidate_count": patent["candidate_count"],
      },
      "paper": {
        "run_id": paper["run_id"],
        "artifact_dir": paper["artifact_dir"],
        "status": paper["status"],
        "candidate_count": paper["candidate_count"],
      },
      "web_company": {
        "run_id": web_company["run_id"],
        "artifact_dir": web_company["artifact_dir"],
        "status": web_company["status"],
        "candidate_count": web_company["candidate_count"],
      },
    },
  )
  assert manifest["theme_name"] == "全固体電池ウォッチ"
  assert manifest["watch_profile_signature"] == profile_signature
  assert manifest["status"] == "partial_success"
  assert manifest["total_candidate_count"] == 3

  manifest_path = save_retrieval_run_manifest(manifest, base_dir=tmp_path)
  reloaded_manifest = load_retrieval_run_manifest(manifest_path, base_dir=tmp_path)
  assert reloaded_manifest["manifest_id"] == manifest["manifest_id"]
  assert reloaded_manifest["theme_name"] == "全固体電池ウォッチ"

  latest = find_latest_compatible_manifest(tmp_path, profile_signature)
  assert latest is not None
  assert latest["manifest_id"] == manifest["manifest_id"]


def test_manifest_selection_skips_signature_mismatch_and_failed_runs(tmp_path: Path) -> None:
  artifacts = _build_artifacts(tmp_path)
  patent = load_patent_retrieval_artifact(artifacts["patent"]["run_dir"])

  profile_a = _watch_profile()
  profile_b = {
    **profile_a,
    "theme_name": "別テーマ",
  }
  manifest_a = build_retrieval_run_manifest(
    profile_a,
    {
      "patent": {
        "run_id": patent["run_id"],
        "artifact_dir": patent["artifact_dir"],
        "status": patent["status"],
        "candidate_count": patent["candidate_count"],
      },
      "paper": {
        "run_id": "failed_run",
        "artifact_dir": patent["artifact_dir"],
        "status": "failed",
        "candidate_count": 1,
      },
    },
  )
  manifest_b = build_retrieval_run_manifest(
    profile_b,
    {
      "patent": {
        "run_id": patent["run_id"],
        "artifact_dir": patent["artifact_dir"],
        "status": patent["status"],
        "candidate_count": patent["candidate_count"],
      },
    },
  )
  save_retrieval_run_manifest(manifest_a, base_dir=tmp_path)
  save_retrieval_run_manifest(manifest_b, base_dir=tmp_path)

  latest = find_latest_compatible_manifest(tmp_path, stable_payload_signature(profile_a))
  assert latest is not None
  assert latest["theme_name"] == profile_a["theme_name"]
  assert set(latest["source_runs"]) == {"patent"}
  assert find_latest_compatible_manifest(tmp_path, "no-match") is None


def test_load_candidates_handles_partial_success_and_missing_artifacts(tmp_path: Path) -> None:
  artifacts = _build_artifacts(tmp_path)
  patent = load_patent_retrieval_artifact(artifacts["patent"]["run_dir"])
  paper = load_paper_retrieval_artifact(artifacts["paper"]["run_dir"])
  web_company = load_web_company_retrieval_artifact(artifacts["web_company"]["run_dir"])
  missing_staged = Path(artifacts["web_company"]["run_dir"]) / "web_company_candidates_staged.json"
  missing_staged.unlink()

  manifest = build_retrieval_run_manifest(
    _watch_profile(),
    {
      "patent": {
        "run_id": patent["run_id"],
        "artifact_dir": patent["artifact_dir"],
        "status": patent["status"],
        "candidate_count": patent["candidate_count"],
      },
      "paper": {
        "run_id": paper["run_id"],
        "artifact_dir": paper["artifact_dir"],
        "status": paper["status"],
        "candidate_count": paper["candidate_count"],
      },
      "web_company": {
        "run_id": web_company["run_id"],
        "artifact_dir": web_company["artifact_dir"],
        "status": web_company["status"],
        "candidate_count": web_company["candidate_count"],
      },
    },
  )

  loaded = load_candidates_from_manifest(manifest)
  assert loaded["status"] == "partial_success"
  assert len(loaded["candidates_by_source"]["patent"]) == 1
  assert len(loaded["candidates_by_source"]["paper"]) == 1
  assert loaded["candidates_by_source"]["web_company"] == []
  assert loaded["warnings"]


def test_loaders_reject_path_traversal(tmp_path: Path) -> None:
  _build_artifacts(tmp_path)
  traversal = "../../outside"
  try:
    load_patent_retrieval_artifact(traversal)
  except ValueError as exc:
    assert "許可範囲外" in str(exc)
  else:
    raise AssertionError("path traversal should be rejected")

  manifest_path = tmp_path / "retrieval_manifests" / "x" / "retrieval_run_manifest.json"
  manifest_path.parent.mkdir(parents=True, exist_ok=True)
  manifest_path.write_text("{}", encoding="utf-8")
  try:
    load_retrieval_run_manifest("../../bad.json", base_dir=tmp_path)
  except ValueError as exc:
    assert "許可範囲外" in str(exc)
  else:
    raise AssertionError("manifest path traversal should be rejected")


def test_loaded_candidates_integrate_without_mutating_inputs_and_support_review_digest(tmp_path: Path) -> None:
  artifacts = _build_artifacts(tmp_path)
  profile = _watch_profile()
  patent = load_patent_retrieval_artifact(artifacts["patent"]["run_dir"])
  paper = load_paper_retrieval_artifact(artifacts["paper"]["run_dir"])
  web_company = load_web_company_retrieval_artifact(artifacts["web_company"]["run_dir"])
  manifest = build_retrieval_run_manifest(
    profile,
    {
      "patent": {
        "run_id": patent["run_id"],
        "artifact_dir": patent["artifact_dir"],
        "status": patent["status"],
        "candidate_count": patent["candidate_count"],
      },
      "paper": {
        "run_id": paper["run_id"],
        "artifact_dir": paper["artifact_dir"],
        "status": paper["status"],
        "candidate_count": paper["candidate_count"],
      },
      "web_company": {
        "run_id": web_company["run_id"],
        "artifact_dir": web_company["artifact_dir"],
        "status": web_company["status"],
        "candidate_count": web_company["candidate_count"],
      },
    },
  )
  loaded = load_candidates_from_manifest(manifest)
  original_patent = deepcopy(loaded["candidates_by_source"]["patent"])
  original_paper = deepcopy(loaded["candidates_by_source"]["paper"])
  original_web_company = deepcopy(loaded["candidates_by_source"]["web_company"])

  integrated = integrate_multi_source_signals(
    base_signals=[],
    watch_profile=profile,
    patent_rows=loaded["candidates_by_source"]["patent"],
    paper_rows=loaded["candidates_by_source"]["paper"],
    web_company_rows=loaded["candidates_by_source"]["web_company"],
    max_items=1000,
    ranking_limit=100,
  )
  assert integrated["signals"]
  assert all(signal.get("data_origin") != "base_signal" for signal in integrated["signals"])
  assert all(signal.get("record_stage") == "staged" for signal in integrated["signals"])
  assert all(signal.get("retrieval_mode") == "real" for signal in integrated["signals"])
  assert loaded["candidates_by_source"]["patent"] == original_patent
  assert loaded["candidates_by_source"]["paper"] == original_paper
  assert loaded["candidates_by_source"]["web_company"] == original_web_company

  reviewed = apply_reviews_to_signals(
    list(integrated["signals"]),
    {"signal_001": {"decision": "採用", "priority": 1, "comment": "採用"}},
  )
  digest = build_weekly_digest_markdown(
    [Signal.from_dict(item) for item in reviewed],
    WatchProfile.from_dict(profile),
    data_source="取得済みデータ",
    loaded_count=len(reviewed),
  )
  assert "ダイジェスト" in digest


def test_ui_keeps_japanese_tabs_and_explicit_reload_buttons() -> None:
  at = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
  at.run()

  assert signal_watch_app.V9_TAB_LABELS == [
    "テーマ設定",
    "情報源",
    "注目シグナル",
    "週次更新",
    "監視プロファイル",
    "ダイジェスト / エクスポート",
  ]
  button_labels = [button.label for button in at.button]
  assert "現在の取得runを保存" in button_labels
  assert "最新の保存済み取得結果を読み込む" in button_labels
  source_text = (PROJECT_ROOT / "ui_v9" / "signal_watch_app.py").read_text(encoding="utf-8")
  assert 'if source_events.get("load_saved_retrieval_manifest"):' in source_text
  assert source_text.count("find_latest_compatible_manifest(") == 1
