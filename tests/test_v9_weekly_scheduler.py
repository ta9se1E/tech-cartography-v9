from __future__ import annotations

from copy import deepcopy
import inspect
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from services_v9.retrieval_run_store import build_retrieval_run_manifest, save_retrieval_run_manifest, stable_payload_signature
from services_v9.watch_profile_schema import migrate_watch_profile
from services_v9.weekly_run_config import (
  WEEKLY_RUN_CONFIG_SCHEMA_VERSION,
  default_weekly_run_config,
  load_weekly_run_config,
  validate_weekly_run_config,
)
from services_v9.weekly_scheduler import (
  acquire_weekly_run_lock,
  build_cron_preview,
  build_launchd_preview,
  find_previous_successful_weekly_run,
  release_weekly_run_lock,
  run_paper_provider_for_weekly,
  run_patent_provider_for_weekly,
  run_web_company_provider_for_weekly,
  run_weekly_watch,
  validate_approved_query_ids,
)
from services_v9 import paper_openalex_retrieval
from services_v9 import patent_bigquery_query
from services_v9 import web_company_retrieval

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _watch_profile() -> dict[str, object]:
  return {
    "schema_version": "v9.2",
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
    "countries": ["JP", "US"],
  }


def _write_watch_profile(tmp_path: Path) -> Path:
  path = tmp_path / "watch_profile.json"
  path.write_text(json.dumps(_watch_profile(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  return path


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
    }
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
    }
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
      "source_url": "https://example.co.jp/news/a",
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
    }
  ]


def _base_config(watch_profile_path: Path) -> dict[str, object]:
  config = default_weekly_run_config()
  config["enabled"] = True
  config["watch_profile_path"] = str(watch_profile_path)
  config["patent"]["approved_query_ids"] = ["patent_q01"]
  config["patent"]["maximum_bytes_billed"] = 1000000
  config["paper"]["approved_query_ids"] = ["paper_q01"]
  config["web_company"]["approved_query_ids"] = ["gw_q001"]
  return config


def _write_staged_artifact(root: Path, source_type: str, run_id: str, provider_status: str, rows: list[dict[str, object]]) -> Path:
  mapping = {
    "patent": ("patent_retrieval_runs", "patent_candidates_staged.json"),
    "paper": ("paper_retrieval_runs", "paper_candidates_staged.json"),
    "web_company": ("web_company_retrieval_runs", "web_company_candidates_staged.json"),
  }
  subdir, filename = mapping[source_type]
  run_dir = root / subdir / run_id
  run_dir.mkdir(parents=True, exist_ok=True)
  (run_dir / filename).write_text(
    json.dumps(
      {
        "retrieval_run_id": run_id,
        "provider_status": provider_status,
        "rows": rows,
      },
      ensure_ascii=False,
      indent=2,
    )
    + "\n",
    encoding="utf-8",
  )
  return run_dir


def _create_saved_manifest(root: Path, *, profile: dict[str, object]) -> dict[str, object]:
  patent_dir = _write_staged_artifact(root, "patent", "patent_saved_run", "success", _patent_rows())
  paper_dir = _write_staged_artifact(root, "paper", "paper_saved_run", "success", _paper_rows())
  web_dir = _write_staged_artifact(root, "web_company", "web_saved_run", "partial_success", _web_company_rows())
  manifest = build_retrieval_run_manifest(
    migrate_watch_profile(profile),
    {
      "patent": {"run_id": "patent_saved_run", "artifact_dir": str(patent_dir), "status": "success", "candidate_count": 1},
      "paper": {"run_id": "paper_saved_run", "artifact_dir": str(paper_dir), "status": "success", "candidate_count": 1},
      "web_company": {"run_id": "web_saved_run", "artifact_dir": str(web_dir), "status": "partial_success", "candidate_count": 1},
    },
  )
  save_retrieval_run_manifest(manifest, base_dir=root)
  return manifest


def _stage_adapter(source_type: str, rows: list[dict[str, object]], tmp_path: Path, *, status: str = "success", message: str = "ok"):
  run_id = f"{source_type}_weekly_run"

  def _adapter(**kwargs):
    artifact_dir = _write_staged_artifact(tmp_path, source_type, run_id, "success" if status == "success" else "partial_success", rows)
    return {
      "status": status,
      "message": message,
      "rows": rows,
      "warnings": [],
      "errors": [] if status == "success" else [message],
      "provider_log": {"provider": source_type, "rows": len(rows)},
      "source_run": {
        "run_id": run_id,
        "artifact_dir": str(artifact_dir),
        "status": "success" if status == "success" else "partial_success",
        "candidate_count": len(rows),
      },
      "details": {"rows_retrieved": len(rows)},
    }

  return _adapter


def test_load_and_validate_weekly_run_config_defaults() -> None:
  config = default_weekly_run_config()
  validated = validate_weekly_run_config(config)
  assert config["schema_version"] == WEEKLY_RUN_CONFIG_SCHEMA_VERSION
  assert config["enabled"] is False
  assert config["execution"]["dry_run"] is True
  assert config["execution"]["patent_enabled"] is False
  assert config["execution"]["paper_enabled"] is False
  assert config["execution"]["web_company_enabled"] is False
  assert config["email"]["mode"] == "preview"
  assert config["email"]["self_send_enabled"] is False
  assert validated["status"] == "ok"


def test_validate_approved_query_ids_ready_for_patent_paper_web() -> None:
  patent = validate_approved_query_ids(["patent_q01"], {"patent_q01", "patent_q02"}, "patent")
  paper = validate_approved_query_ids(["paper_q01"], {"paper_q01", "paper_q02"}, "paper")
  web = validate_approved_query_ids(["gw_q001"], {"gw_q001", "gw_q002"}, "web_company")
  assert patent["status"] == "ready"
  assert paper["status"] == "ready"
  assert web["status"] == "ready"
  assert patent["valid_query_ids"] == ["patent_q01"]
  assert paper["valid_query_ids"] == ["paper_q01"]
  assert web["valid_query_ids"] == ["gw_q001"]


def test_validate_approved_query_ids_blocks_unknown_ids_without_replacement() -> None:
  patent = validate_approved_query_ids(["patent_q01", "unknown_patent"], {"patent_q01"}, "patent")
  paper = validate_approved_query_ids(["unknown_paper"], {"paper_q01"}, "paper")
  web = validate_approved_query_ids(["gw_q001", "unknown_web"], {"gw_q001"}, "web_company")
  assert patent["status"] == "blocked"
  assert paper["status"] == "blocked"
  assert web["status"] == "blocked"
  assert patent["unknown_query_ids"] == ["unknown_patent"]
  assert paper["unknown_query_ids"] == ["unknown_paper"]
  assert web["unknown_query_ids"] == ["unknown_web"]
  assert patent["valid_query_ids"] == ["patent_q01"]
  assert web["valid_query_ids"] == ["gw_q001"]


def test_provider_function_signatures_match_scheduler_expectations() -> None:
  patent_preview_sig = inspect.signature(patent_bigquery_query.build_patent_bigquery_preview)
  assert "search_plan" in patent_preview_sig.parameters
  assert "watch_profile" in patent_preview_sig.parameters
  assert "selected_query_id" in patent_preview_sig.parameters
  assert "max_results" in patent_preview_sig.parameters
  assert "config" in patent_preview_sig.parameters

  patent_execute_sig = inspect.signature(patent_bigquery_query.execute_patent_bigquery_retrieval)
  assert "preview" in patent_execute_sig.parameters
  assert "dry_run_result" in patent_execute_sig.parameters
  assert "approved" in patent_execute_sig.parameters
  assert "config" in patent_execute_sig.parameters

  paper_preview_sig = inspect.signature(paper_openalex_retrieval.build_openalex_paper_preview)
  assert "search_plan" in paper_preview_sig.parameters
  assert "watch_profile" in paper_preview_sig.parameters
  assert "selected_query_id" in paper_preview_sig.parameters
  assert "max_results" in paper_preview_sig.parameters
  assert "retry_limit" in paper_preview_sig.parameters

  paper_execute_sig = inspect.signature(paper_openalex_retrieval.execute_openalex_paper_retrieval)
  assert "preview" in paper_execute_sig.parameters
  assert "timeout_sec" in paper_execute_sig.parameters

  web_preview_sig = inspect.signature(web_company_retrieval.build_global_web_retrieval_preview)
  assert "search_plan" in web_preview_sig.parameters
  assert "max_query_count" in web_preview_sig.parameters
  assert "verification_limit" in web_preview_sig.parameters

  web_execute_sig = inspect.signature(web_company_retrieval.execute_global_web_retrieval)
  assert "preview" in web_execute_sig.parameters
  assert "discovery_timeout_sec" in web_execute_sig.parameters


def test_patent_provider_contract_adapter_normalizes_success_and_partial(tmp_path: Path) -> None:
  config = _base_config(_write_watch_profile(tmp_path))
  original_config = deepcopy(config)
  original_plan = deepcopy({"plans": {"patent": {"queries": [{"query_id": "patent_q01"}]}}})

  preview_calls: list[dict[str, object]] = []
  dry_run_calls: list[dict[str, object]] = []
  execute_calls: list[dict[str, object]] = []

  def _fake_preview(search_plan, watch_profile, *, selected_query_id=None, time_range="12m", max_results=None, config=None):
    preview_calls.append(
      {
        "selected_query_id": selected_query_id,
        "max_results": max_results,
        "maximum_bytes_billed": getattr(config, "bigquery_max_bytes_billed", None),
      }
    )
    return {"request": {"query_id": selected_query_id}, "validation_rows": [], "parameters": [], "sql": "SELECT 1"}

  def _fake_dry_run(preview, *, client_factory=None, job_config_builder=None, config=None):
    dry_run_calls.append({"query_id": dict(preview.get("request", {}) or {}).get("query_id", ""), "client_factory": client_factory})
    return {"dry_run_status": "ok", "estimated_bytes": 10, "estimated_cost_usd": 0.1}

  raw_result = {
    "provider_status": "partial_success",
    "retrieval_run_id": "patent_real_run_001",
    "rows_retrieved": 1,
    "rows": _patent_rows(),
    "log": {"provider_status": "partial_success"},
    "error": "partial",
  }
  raw_result_before = deepcopy(raw_result)

  def _fake_execute(preview, dry_run_result, *, approved, client_factory=None, job_config_builder=None, config=None):
    execute_calls.append({"approved": approved, "query_id": dict(preview.get("request", {}) or {}).get("query_id", "")})
    return raw_result

  result = run_patent_provider_for_weekly(
    search_plan=original_plan,
    watch_profile=_watch_profile(),
    config=config,
    output_root=tmp_path,
    weekly_run_id="weekly_test",
    preview_builder=_fake_preview,
    dry_run_runner=_fake_dry_run,
    execute_runner=_fake_execute,
  )
  assert result["provider"] == "patent"
  assert result["status"] == "partial_success"
  assert result["provider_status"] == "partial_success"
  assert result["retrieval_run_id"] == "patent_real_run_001"
  assert result["candidate_count"] == 1
  assert result["artifact_dir"]
  assert preview_calls[0]["selected_query_id"] == "patent_q01"
  assert preview_calls[0]["maximum_bytes_billed"] == 1000000
  assert execute_calls[0]["approved"] is True
  assert raw_result == raw_result_before
  assert config == original_config
  assert original_plan == {"plans": {"patent": {"queries": [{"query_id": "patent_q01"}]}}}

  def _fake_execute_success(preview, dry_run_result, *, approved, client_factory=None, job_config_builder=None, config=None):
    return {
      "provider_status": "success",
      "retrieval_run_id": "patent_real_run_002",
      "rows_retrieved": 1,
      "rows": _patent_rows(),
      "log": {"provider_status": "success"},
      "error": None,
    }

  success_result = run_patent_provider_for_weekly(
    search_plan=original_plan,
    watch_profile=_watch_profile(),
    config=config,
    output_root=tmp_path,
    weekly_run_id="weekly_test",
    preview_builder=_fake_preview,
    dry_run_runner=_fake_dry_run,
    execute_runner=_fake_execute_success,
  )
  assert success_result["status"] == "success"
  assert success_result["retrieval_run_id"] == "patent_real_run_002"


def test_paper_provider_contract_adapter_passes_query_limit_retry_and_normalizes(tmp_path: Path) -> None:
  config = _base_config(_write_watch_profile(tmp_path))
  config["paper"]["retry_limit"] = 4
  preview_calls: list[dict[str, object]] = []

  def _fake_preview(search_plan, watch_profile, *, selected_query_id=None, time_range="12m", max_results=None, per_page=25, retry_limit=2, polite_email=None):
    preview_calls.append(
      {
        "selected_query_id": selected_query_id,
        "max_results": max_results,
        "retry_limit": retry_limit,
      }
    )
    return {"request": {"query_id": selected_query_id, "retry_limit": retry_limit}, "validation_rows": [], "url_preview": "u"}

  def _fake_execute(preview, *, opener=None, sleeper=None, timeout_sec=30, rate_limit_sleep_sec=0.2):
    return {
      "status": "success",
      "run_id": "paper_real_run_001",
      "rows_retrieved": 1,
      "rows": _paper_rows(),
      "provider_log": [{"page": 1}],
      "error": None,
    }

  result = run_paper_provider_for_weekly(
    search_plan={"plans": {"paper": {"queries": [{"query_id": "paper_q01"}]}}},
    watch_profile=_watch_profile(),
    config=config,
    output_root=tmp_path,
    weekly_run_id="weekly_test",
    preview_builder=_fake_preview,
    execute_runner=_fake_execute,
  )
  assert result["provider"] == "paper"
  assert result["status"] == "success"
  assert result["retrieval_run_id"] == "paper_real_run_001"
  assert result["candidate_count"] == 1
  assert preview_calls[0]["selected_query_id"] == "paper_q01"
  assert preview_calls[0]["retry_limit"] == 4
  assert preview_calls[0]["max_results"] >= 1

  def _fake_execute_partial(preview, *, opener=None, sleeper=None, timeout_sec=30, rate_limit_sleep_sec=0.2):
    return {
      "provider_status": "partial_success",
      "retrieval_run_id": "paper_real_run_002",
      "rows_retrieved": 1,
      "rows": _paper_rows(),
      "provider_log": [{"page": 1}],
      "error": "partial",
    }

  partial_result = run_paper_provider_for_weekly(
    search_plan={"plans": {"paper": {"queries": [{"query_id": "paper_q01"}]}}},
    watch_profile=_watch_profile(),
    config=config,
    output_root=tmp_path,
    weekly_run_id="weekly_test",
    preview_builder=_fake_preview,
    execute_runner=_fake_execute_partial,
  )
  assert partial_result["status"] == "partial_success"
  assert partial_result["retrieval_run_id"] == "paper_real_run_002"


def test_web_provider_contract_adapter_filters_plan_and_normalizes(tmp_path: Path) -> None:
  config = _base_config(_write_watch_profile(tmp_path))
  original_plan = {
    "global_web_plan": {
      "queries": [
        {"query_id": "gw_q001", "enabled": True, "duplicate_of": "", "query_local": "a", "max_results": 5},
        {"query_id": "gw_q999", "enabled": True, "duplicate_of": "", "query_local": "b", "max_results": 5},
      ]
    }
  }
  preview_calls: list[dict[str, object]] = []

  def _fake_preview(search_plan, *, max_query_count=None, verification_limit=30, summary_top_n=10):
    preview_calls.append(
      {
        "query_ids": [item["query_id"] for item in search_plan["global_web_plan"]["queries"]],
        "max_query_count": max_query_count,
        "verification_limit": verification_limit,
      }
    )
    return {"request": {"queries": list(search_plan["global_web_plan"]["queries"])}, "validation_rows": []}

  def _fake_execute(preview, *, tavily_search_post_fn=None, tavily_extract_post_fn=None, google_grounding_fn=None, sleeper=None, discovery_timeout_sec=30, extract_timeout_sec=60, rate_limit_sleep_sec=0.2):
    return {
      "provider_status": "partial_success",
      "retrieval_run_id": "web_real_run_001",
      "rows_retrieved": 1,
      "rows": _web_company_rows(),
      "provider_log": [{"step": "discovery"}],
      "error": "partial",
      "query_count": len(preview["request"]["queries"]),
    }

  result = run_web_company_provider_for_weekly(
    search_plan=deepcopy(original_plan),
    watch_profile=_watch_profile(),
    config=config,
    output_root=tmp_path,
    weekly_run_id="weekly_test",
    preview_builder=_fake_preview,
    execute_runner=_fake_execute,
  )
  assert result["provider"] == "web_company"
  assert result["status"] == "partial_success"
  assert result["retrieval_run_id"] == "web_real_run_001"
  assert result["candidate_count"] == 1
  assert preview_calls[0]["query_ids"] == ["gw_q001"]
  assert preview_calls[0]["verification_limit"] == 30
  assert original_plan["global_web_plan"]["queries"][1]["query_id"] == "gw_q999"

  def _fake_execute_success(preview, *, tavily_search_post_fn=None, tavily_extract_post_fn=None, google_grounding_fn=None, sleeper=None, discovery_timeout_sec=30, extract_timeout_sec=60, rate_limit_sleep_sec=0.2):
    return {
      "status": "success",
      "run_id": "web_real_run_002",
      "rows_retrieved": 1,
      "rows": _web_company_rows(),
      "provider_log": [{"step": "discovery"}],
      "error": None,
      "query_count": len(preview["request"]["queries"]),
    }

  success_result = run_web_company_provider_for_weekly(
    search_plan=deepcopy(original_plan),
    watch_profile=_watch_profile(),
    config=config,
    output_root=tmp_path,
    weekly_run_id="weekly_test",
    preview_builder=_fake_preview,
    execute_runner=_fake_execute_success,
  )
  assert success_result["status"] == "success"
  assert success_result["retrieval_run_id"] == "web_real_run_002"


def test_provider_contract_adapters_handle_exceptions_and_missing_rows_safely(tmp_path: Path) -> None:
  config = _base_config(_write_watch_profile(tmp_path))

  def _paper_preview(search_plan, watch_profile, *, selected_query_id=None, time_range="12m", max_results=None, per_page=25, retry_limit=2, polite_email=None):
    return {"request": {"query_id": selected_query_id}, "validation_rows": []}

  def _paper_execute_raises(preview, *, opener=None, sleeper=None, timeout_sec=30, rate_limit_sleep_sec=0.2):
    raise RuntimeError("paper boom")

  failed = run_paper_provider_for_weekly(
    search_plan={"plans": {"paper": {"queries": [{"query_id": "paper_q01"}]}}},
    watch_profile=_watch_profile(),
    config=config,
    output_root=tmp_path,
    weekly_run_id="weekly_test",
    preview_builder=_paper_preview,
    execute_runner=_paper_execute_raises,
  )
  assert failed["status"] == "failed"
  assert failed["rows"] == []

  def _web_preview(search_plan, *, max_query_count=None, verification_limit=30, summary_top_n=10):
    return {"request": {"queries": [{"query_id": "gw_q001"}]}, "validation_rows": []}

  def _web_execute_missing_rows(preview, *, tavily_search_post_fn=None, tavily_extract_post_fn=None, google_grounding_fn=None, sleeper=None, discovery_timeout_sec=30, extract_timeout_sec=60, rate_limit_sleep_sec=0.2):
    return {
      "status": "success",
      "run_id": "web_run_missing_rows",
      "provider_log": [],
      "error": None,
    }

  normalized = run_web_company_provider_for_weekly(
    search_plan={"global_web_plan": {"queries": [{"query_id": "gw_q001", "enabled": True, "duplicate_of": "", "query_local": "a", "max_results": 5}]}},
    watch_profile=_watch_profile(),
    config=config,
    output_root=tmp_path,
    weekly_run_id="weekly_test",
    preview_builder=_web_preview,
    execute_runner=_web_execute_missing_rows,
  )
  assert normalized["rows"] == []
  assert normalized["candidate_count"] == 0
  assert normalized["warnings"]


def test_load_weekly_run_config_from_file(tmp_path: Path) -> None:
  config_path = tmp_path / "weekly_config.json"
  config_path.write_text(json.dumps(default_weekly_run_config(), ensure_ascii=False, indent=2), encoding="utf-8")
  loaded = load_weekly_run_config(config_path)
  assert loaded["schema_version"] == WEEKLY_RUN_CONFIG_SCHEMA_VERSION
  assert loaded["_config_path"] == str(config_path.resolve())


def test_lock_acquire_release_and_stale_handling(tmp_path: Path) -> None:
  signature = stable_payload_signature(_watch_profile())
  lock_root = tmp_path / "weekly_locks"
  first = acquire_weekly_run_lock(signature, "run_a", lock_root, stale_timeout_seconds=3600)
  assert first["acquired"] is True

  second = acquire_weekly_run_lock(signature, "run_b", lock_root, stale_timeout_seconds=3600)
  assert second["acquired"] is False
  assert second["status"] == "blocked"

  lock_path = Path(first["path"])
  stale_payload = json.loads(lock_path.read_text(encoding="utf-8"))
  stale_payload["started_at"] = (datetime.now().astimezone() - timedelta(hours=3)).isoformat(timespec="seconds")
  lock_path.write_text(json.dumps(stale_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

  third = acquire_weekly_run_lock(signature, "run_c", lock_root, stale_timeout_seconds=60)
  assert third["acquired"] is True
  release_weekly_run_lock(third)
  assert not Path(third["path"]).exists()


def test_run_weekly_watch_blocks_invalid_config(tmp_path: Path) -> None:
  config = default_weekly_run_config()
  config["enabled"] = True
  config["watch_profile_path"] = ""
  result = run_weekly_watch(config, output_root=tmp_path, provider_adapters={})
  assert result["status"] == "blocked"
  status_path = Path(result["run_dir"]) / "weekly_run_status.json"
  payload = json.loads(status_path.read_text(encoding="utf-8"))
  assert payload["stage_statuses"]["load_config"] == "blocked"


def test_provider_validation_blocks_unknown_patent_id_but_allows_other_providers(tmp_path: Path) -> None:
  watch_profile_path = _write_watch_profile(tmp_path)
  config = _base_config(watch_profile_path)
  config["execution"]["dry_run"] = False
  config["execution"]["patent_enabled"] = True
  config["execution"]["paper_enabled"] = True
  config["execution"]["web_company_enabled"] = True
  config["patent"]["approved_query_ids"] = ["unknown_patent_q99"]
  original_config = deepcopy(config)

  calls = {"patent": 0, "paper": 0, "web_company": 0}

  def _patent_adapter(**kwargs):
    calls["patent"] += 1
    raise AssertionError("blocked patent adapter must not be called")

  def _paper_adapter(**kwargs):
    calls["paper"] += 1
    return _stage_adapter("paper", _paper_rows(), tmp_path, status="success", message="paper ok")(**kwargs)

  def _web_adapter(**kwargs):
    calls["web_company"] += 1
    return _stage_adapter("web_company", _web_company_rows(), tmp_path, status="success", message="web ok")(**kwargs)

  result = run_weekly_watch(
    config,
    output_root=tmp_path,
    provider_adapters={"patent": _patent_adapter, "paper": _paper_adapter, "web_company": _web_adapter},
  )
  assert result["status"] == "partial_success"
  assert calls["patent"] == 0
  assert calls["paper"] == 1
  assert calls["web_company"] == 1
  assert config == original_config

  run_dir = Path(result["run_dir"])
  status_payload = json.loads((run_dir / "weekly_run_status.json").read_text(encoding="utf-8"))
  assert status_payload["stage_statuses"]["retrieve_patent"] == "blocked"
  assert status_payload["stage_statuses"]["retrieve_paper"] == "success"
  assert status_payload["stage_statuses"]["retrieve_web_company"] == "success"
  provider_log = json.loads((run_dir / "provider_log.json").read_text(encoding="utf-8"))
  validation = provider_log["patent"]["approved_query_validation"]
  assert validation["unknown_query_ids"] == ["unknown_patent_q99"]
  assert validation["valid_query_ids"] == []


def test_provider_validation_blocks_unknown_paper_and_web_ids(tmp_path: Path) -> None:
  watch_profile_path = _write_watch_profile(tmp_path)
  config = _base_config(watch_profile_path)
  config["execution"]["dry_run"] = False
  config["execution"]["patent_enabled"] = False
  config["execution"]["paper_enabled"] = True
  config["execution"]["web_company_enabled"] = True
  config["paper"]["approved_query_ids"] = ["unknown_paper_q99"]
  config["web_company"]["approved_query_ids"] = ["unknown_gw_q999"]

  calls = {"paper": 0, "web_company": 0}

  def _paper_adapter(**kwargs):
    calls["paper"] += 1
    raise AssertionError("blocked paper adapter must not be called")

  def _web_adapter(**kwargs):
    calls["web_company"] += 1
    raise AssertionError("blocked web adapter must not be called")

  result = run_weekly_watch(
    config,
    output_root=tmp_path,
    provider_adapters={"paper": _paper_adapter, "web_company": _web_adapter},
  )
  assert calls["paper"] == 0
  assert calls["web_company"] == 0
  status_payload = json.loads((Path(result["run_dir"]) / "weekly_run_status.json").read_text(encoding="utf-8"))
  assert status_payload["stage_statuses"]["retrieve_paper"] == "blocked"
  assert status_payload["stage_statuses"]["retrieve_web_company"] == "blocked"


def test_empty_approved_query_ids_keep_existing_safety_behavior_and_disabled_skips_validation(tmp_path: Path) -> None:
  watch_profile_path = _write_watch_profile(tmp_path)
  config = _base_config(watch_profile_path)
  config["execution"]["dry_run"] = False
  config["execution"]["patent_enabled"] = True
  config["execution"]["paper_enabled"] = False
  config["execution"]["web_company_enabled"] = False
  config["patent"]["approved_query_ids"] = []
  result = run_weekly_watch(config, output_root=tmp_path, provider_adapters={})
  status_payload = json.loads((Path(result["run_dir"]) / "weekly_run_status.json").read_text(encoding="utf-8"))
  assert status_payload["stage_statuses"]["load_config"] == "blocked"

  disabled_config = _base_config(watch_profile_path)
  disabled_config["execution"]["dry_run"] = False
  disabled_config["execution"]["patent_enabled"] = False
  disabled_config["patent"]["approved_query_ids"] = ["unknown_patent_q99"]
  disabled_result = run_weekly_watch(disabled_config, output_root=tmp_path / "disabled_case", provider_adapters={})
  disabled_status = json.loads((Path(disabled_result["run_dir"]) / "weekly_run_status.json").read_text(encoding="utf-8"))
  assert disabled_status["stage_statuses"]["retrieve_patent"] == "skipped"


def test_dry_run_skips_external_calls_and_can_reuse_saved_manifest(tmp_path: Path) -> None:
  watch_profile_path = _write_watch_profile(tmp_path)
  profile = _watch_profile()
  _create_saved_manifest(tmp_path, profile=profile)

  config = _base_config(watch_profile_path)
  config["execution"]["dry_run"] = True
  config["execution"]["patent_enabled"] = True
  config["execution"]["paper_enabled"] = True
  config["execution"]["web_company_enabled"] = True

  calls: list[str] = []

  def _should_not_run(**kwargs):
    calls.append("called")
    raise AssertionError("provider must not be called in dry-run")

  result = run_weekly_watch(
    config,
    output_root=tmp_path,
    provider_adapters={"patent": _should_not_run, "paper": _should_not_run, "web_company": _should_not_run},
  )
  assert not calls
  assert result["status"] == "partial_success"
  run_dir = Path(result["run_dir"])
  assert (run_dir / "retrieval_run_manifest.json").exists()
  assert (run_dir / "integrated_signals.json").exists()
  assert "Digest は未生成です" not in (run_dir / "weekly_digest.md").read_text(encoding="utf-8")
  email_preview = json.loads((run_dir / "email_preview.json").read_text(encoding="utf-8"))
  assert email_preview["subject"].startswith("[Tech Cartography]")


def test_real_run_success_partial_success_and_previous_success_diff(tmp_path: Path) -> None:
  watch_profile_path = _write_watch_profile(tmp_path)
  config = _base_config(watch_profile_path)
  config["execution"]["dry_run"] = False
  config["execution"]["patent_enabled"] = True
  config["execution"]["paper_enabled"] = True
  config["execution"]["web_company_enabled"] = True

  provider_adapters = {
    "patent": _stage_adapter("patent", _patent_rows(), tmp_path, status="success", message="patent ok"),
    "paper": _stage_adapter("paper", _paper_rows(), tmp_path, status="success", message="paper ok"),
    "web_company": _stage_adapter("web_company", _web_company_rows(), tmp_path, status="success", message="web ok"),
  }
  first = run_weekly_watch(config, output_root=tmp_path, provider_adapters=provider_adapters)
  assert first["status"] == "success"

  failed_dir = Path(tmp_path) / "weekly_runs" / "failed_run"
  failed_dir.mkdir(parents=True, exist_ok=True)
  (failed_dir / "weekly_run_status.json").write_text(
    json.dumps(
      {
        "weekly_run_id": "failed_run",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "overall_status": "failed",
        "watch_profile_signature": stable_payload_signature(_watch_profile()),
      },
      ensure_ascii=False,
      indent=2,
    )
    + "\n",
    encoding="utf-8",
  )

  paper_rows_second = [
    {
      **_paper_rows()[0],
      "title": "Solid state battery paper updated",
      "publication_date": "2026-01-01",
      "cited_by_count": 30,
    }
  ]
  second_adapters = {
    "patent": _stage_adapter("patent", _patent_rows(), tmp_path, status="success", message="patent ok"),
    "paper": _stage_adapter("paper", paper_rows_second, tmp_path, status="partial_success", message="paper partial"),
    "web_company": _stage_adapter("web_company", _web_company_rows(), tmp_path, status="success", message="web ok"),
  }
  second = run_weekly_watch(config, output_root=tmp_path, provider_adapters=second_adapters)
  assert second["status"] == "partial_success"
  second_payload = json.loads((Path(second["run_dir"]) / "weekly_run_status.json").read_text(encoding="utf-8"))
  assert second_payload["stage_statuses"]["load_previous_success"] == "success"
  diff_payload = json.loads((Path(second["run_dir"]) / "weekly_diff.json").read_text(encoding="utf-8"))
  assert diff_payload["previous_weekly_run_id"] == first["weekly_run_id"]
  integrated_payload = json.loads((Path(second["run_dir"]) / "integrated_signals.json").read_text(encoding="utf-8"))
  assert integrated_payload["signals"]
  assert any(signal.get("change_status") in {"Stable", "Updated", "Rising", "New"} for signal in integrated_payload["signals"])


def test_email_send_control_and_duplicate_digest_block(tmp_path: Path) -> None:
  watch_profile_path = _write_watch_profile(tmp_path)
  config = _base_config(watch_profile_path)
  config["execution"]["dry_run"] = False
  config["execution"]["patent_enabled"] = True
  config["execution"]["paper_enabled"] = True
  config["execution"]["web_company_enabled"] = True
  config["email"]["mode"] = "self_only"
  config["email"]["self_send_enabled"] = True

  provider_adapters = {
    "patent": _stage_adapter("patent", _patent_rows(), tmp_path),
    "paper": _stage_adapter("paper", _paper_rows(), tmp_path),
    "web_company": _stage_adapter("web_company", _web_company_rows(), tmp_path),
  }

  sent_calls: list[str] = []

  def _mock_send(preview, email_config):
    sent_calls.append(str(preview.get("digest_sha256", "")))
    return {
      "status": "sent",
      "send_attempted": True,
      "send_succeeded": True,
      "recipient_masked": "m***@example.com",
      "subject": preview.get("subject", ""),
      "digest_sha256": preview.get("digest_sha256", ""),
      "signal_count": preview.get("signal_count", 0),
      "data_source": preview.get("data_source", ""),
      "send_mode": email_config.send_mode,
      "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
      "delivery_run_id": "email_delivery_mock",
      "smtp_host": "smtp.example.com",
      "sender_masked": "s***@example.com",
      "safe_error_message": "",
    }

  first = run_weekly_watch(
    config,
    output_root=tmp_path,
    provider_adapters={**provider_adapters, "email_send": _mock_send},
  )
  assert first["status"] == "success"
  assert len(sent_calls) == 1
  first_status_path = Path(first["run_dir"]) / "weekly_run_status.json"
  first_status_payload = json.loads(first_status_path.read_text(encoding="utf-8"))
  first_status_payload["overall_status"] = "failed"
  first_status_path.write_text(json.dumps(first_status_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

  second = run_weekly_watch(
    config,
    output_root=tmp_path,
    provider_adapters={**provider_adapters, "email_send": _mock_send},
  )
  assert len(sent_calls) == 1
  second_status = json.loads((Path(second["run_dir"]) / "weekly_run_status.json").read_text(encoding="utf-8"))
  assert second_status["stage_statuses"]["send_email"] == "blocked"
  second_email = json.loads((Path(second["run_dir"]) / "email_preview.json").read_text(encoding="utf-8"))
  assert second_email["message"].startswith("同一 Digest")


def _write_previous_weekly_email_status(
  weekly_root: Path,
  *,
  run_id: str,
  signature: str,
  overall_status: str,
  dry_run: bool,
  email_preview: dict[str, object],
) -> Path:
  run_dir = weekly_root / run_id
  run_dir.mkdir(parents=True, exist_ok=True)
  (run_dir / "weekly_run_status.json").write_text(
    json.dumps(
      {
        "weekly_run_id": run_id,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "overall_status": overall_status,
        "watch_profile_signature": signature,
        "dry_run": dry_run,
        "email_preview": email_preview,
      },
      ensure_ascii=False,
      indent=2,
    )
    + "\n",
    encoding="utf-8",
  )
  return run_dir


def test_email_duplicate_detection_allows_retry_for_unsuccessful_history(tmp_path: Path) -> None:
  cases = [
    ("preview_only", {"status": "preview", "send_attempted": False, "send_succeeded": False}, "blocked", False),
    ("dry_run_only", {"status": "dry_run", "send_attempted": False, "send_succeeded": False}, "partial_success", True),
    ("send_attempted_false", {"status": "sent", "send_attempted": False, "send_succeeded": True}, "success", False),
    ("send_failed", {"status": "error", "send_attempted": True, "send_succeeded": False, "safe_error_message": "smtp send failed"}, "failed", False),
    ("smtp_connect_failure", {"status": "error", "send_attempted": True, "send_succeeded": False, "error_type": "SMTPConnectError"}, "failed", False),
    ("smtp_auth_failure", {"status": "error", "send_attempted": True, "send_succeeded": False, "error_type": "SMTPAuthenticationError"}, "failed", False),
    ("allowlist_rejected", {"status": "blocked", "send_attempted": False, "send_succeeded": False, "safe_error_message": "recipient が EMAIL_RECIPIENT_ALLOWLIST に含まれていません。"}, "blocked", False),
    ("self_only_missing", {"status": "blocked", "send_attempted": False, "send_succeeded": False, "safe_error_message": "EMAIL_SEND_MODE=self_only の場合のみ実送信できます。"}, "blocked", False),
    ("blocked_only", {"status": "blocked", "send_attempted": False, "send_succeeded": False}, "blocked", False),
  ]

  for index, (label, email_preview_payload, overall_status, dry_run) in enumerate(cases, start=1):
    case_root = tmp_path / f"case_{index}"
    case_root.mkdir(parents=True, exist_ok=True)
    watch_profile_path = _write_watch_profile(case_root)
    config = _base_config(watch_profile_path)
    config["execution"]["dry_run"] = False
    config["execution"]["patent_enabled"] = True
    config["execution"]["paper_enabled"] = True
    config["execution"]["web_company_enabled"] = True
    config["email"]["mode"] = "self_only"
    config["email"]["self_send_enabled"] = False

    provider_adapters = {
      "patent": _stage_adapter("patent", _patent_rows(), case_root),
      "paper": _stage_adapter("paper", _paper_rows(), case_root),
      "web_company": _stage_adapter("web_company", _web_company_rows(), case_root),
    }
    baseline = run_weekly_watch(config, output_root=case_root, provider_adapters=provider_adapters)
    baseline_status = json.loads((Path(baseline["run_dir"]) / "weekly_run_status.json").read_text(encoding="utf-8"))
    digest = json.loads((Path(baseline["run_dir"]) / "email_preview.json").read_text(encoding="utf-8"))["digest_sha256"]
    _write_previous_weekly_email_status(
      case_root / "weekly_runs",
      run_id=f"previous_{label}",
      signature=str(baseline_status["watch_profile_signature"]),
      overall_status=overall_status,
      dry_run=dry_run,
      email_preview={**email_preview_payload, "digest_sha256": digest},
    )

    sent_calls: list[str] = []

    def _mock_send(preview, email_config):
      sent_calls.append(str(preview.get("digest_sha256", "")))
      return {
        "status": "sent",
        "send_attempted": True,
        "send_succeeded": True,
        "recipient_masked": "m***@example.com",
        "subject": preview.get("subject", ""),
        "digest_sha256": preview.get("digest_sha256", ""),
        "signal_count": preview.get("signal_count", 0),
        "data_source": preview.get("data_source", ""),
        "send_mode": email_config.send_mode,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "delivery_run_id": f"email_delivery_{label}",
        "smtp_host": "smtp.example.com",
        "sender_masked": "s***@example.com",
        "safe_error_message": "",
      }

    config["email"]["self_send_enabled"] = True
    result = run_weekly_watch(
      config,
      output_root=case_root,
      provider_adapters={**provider_adapters, "email_send": _mock_send},
    )
    assert len(sent_calls) == 1, label
    status_payload = json.loads((Path(result["run_dir"]) / "weekly_run_status.json").read_text(encoding="utf-8"))
    assert status_payload["stage_statuses"]["send_email"] == "success", label


def _write_previous_weekly_run(
  weekly_root: Path,
  *,
  run_id: str,
  signature: str,
  created_at: str,
  overall_status: str,
  dry_run: bool,
  signals: list[dict[str, object]] | None,
) -> Path:
  run_dir = weekly_root / run_id
  run_dir.mkdir(parents=True, exist_ok=True)
  (run_dir / "weekly_run_status.json").write_text(
    json.dumps(
      {
        "weekly_run_id": run_id,
        "created_at": created_at,
        "overall_status": overall_status,
        "watch_profile_signature": signature,
        "dry_run": dry_run,
      },
      ensure_ascii=False,
      indent=2,
    )
    + "\n",
    encoding="utf-8",
  )
  if signals is not None:
    (run_dir / "integrated_signals.json").write_text(
      json.dumps({"signals": signals}, ensure_ascii=False, indent=2) + "\n",
      encoding="utf-8",
    )
  return run_dir


def test_find_previous_successful_weekly_run_ignores_failed_runs(tmp_path: Path) -> None:
  signature = stable_payload_signature(_watch_profile())
  weekly_root = tmp_path / "weekly_runs"
  _write_previous_weekly_run(
    weekly_root,
    run_id="good_run",
    signature=signature,
    created_at="2026-07-04T09:00:00+09:00",
    overall_status="success",
    dry_run=False,
    signals=[{"id": "sig-1", "title": "A"}],
  )
  _write_previous_weekly_run(
    weekly_root,
    run_id="bad_run",
    signature=signature,
    created_at="2026-07-04T10:00:00+09:00",
    overall_status="failed",
    dry_run=False,
    signals=[{"id": "sig-2", "title": "B"}],
  )
  latest = find_previous_successful_weekly_run(tmp_path, signature)
  assert latest is not None
  assert latest["weekly_run_id"] == "good_run"


def test_find_previous_successful_weekly_run_prefers_real_run_over_newer_dry_run(tmp_path: Path) -> None:
  signature = stable_payload_signature(_watch_profile())
  weekly_root = tmp_path / "weekly_runs"
  _write_previous_weekly_run(
    weekly_root,
    run_id="real_run",
    signature=signature,
    created_at="2026-07-04T09:00:00+09:00",
    overall_status="success",
    dry_run=False,
    signals=[{"id": "sig-1", "title": "A"}],
  )
  _write_previous_weekly_run(
    weekly_root,
    run_id="dry_run_newer",
    signature=signature,
    created_at="2026-07-04T10:00:00+09:00",
    overall_status="partial_success",
    dry_run=True,
    signals=[{"id": "sig-2", "title": "B"}],
  )
  latest = find_previous_successful_weekly_run(tmp_path, signature)
  assert latest is not None
  assert latest["weekly_run_id"] == "real_run"


def test_find_previous_successful_weekly_run_returns_none_when_only_dry_runs_exist(tmp_path: Path) -> None:
  signature = stable_payload_signature(_watch_profile())
  weekly_root = tmp_path / "weekly_runs"
  _write_previous_weekly_run(
    weekly_root,
    run_id="dry_only",
    signature=signature,
    created_at="2026-07-04T10:00:00+09:00",
    overall_status="success",
    dry_run=True,
    signals=[{"id": "sig-1", "title": "A"}],
  )
  assert find_previous_successful_weekly_run(tmp_path, signature) is None


def test_find_previous_successful_weekly_run_excludes_empty_or_missing_integrated_signals(tmp_path: Path) -> None:
  signature = stable_payload_signature(_watch_profile())
  weekly_root = tmp_path / "weekly_runs"
  _write_previous_weekly_run(
    weekly_root,
    run_id="missing_signals",
    signature=signature,
    created_at="2026-07-04T09:00:00+09:00",
    overall_status="success",
    dry_run=False,
    signals=None,
  )
  _write_previous_weekly_run(
    weekly_root,
    run_id="empty_signals",
    signature=signature,
    created_at="2026-07-04T10:00:00+09:00",
    overall_status="partial_success",
    dry_run=False,
    signals=[],
  )
  assert find_previous_successful_weekly_run(tmp_path, signature) is None


def test_find_previous_successful_weekly_run_accepts_partial_success_real_run_with_signals(tmp_path: Path) -> None:
  signature = stable_payload_signature(_watch_profile())
  weekly_root = tmp_path / "weekly_runs"
  _write_previous_weekly_run(
    weekly_root,
    run_id="partial_real_run",
    signature=signature,
    created_at="2026-07-04T10:00:00+09:00",
    overall_status="partial_success",
    dry_run=False,
    signals=[{"id": "sig-1", "title": "A"}],
  )
  latest = find_previous_successful_weekly_run(tmp_path, signature)
  assert latest is not None
  assert latest["weekly_run_id"] == "partial_real_run"


def test_find_previous_successful_weekly_run_excludes_blocked_and_failed_runs(tmp_path: Path) -> None:
  signature = stable_payload_signature(_watch_profile())
  weekly_root = tmp_path / "weekly_runs"
  _write_previous_weekly_run(
    weekly_root,
    run_id="blocked_run",
    signature=signature,
    created_at="2026-07-04T09:00:00+09:00",
    overall_status="blocked",
    dry_run=False,
    signals=[{"id": "sig-1", "title": "A"}],
  )
  _write_previous_weekly_run(
    weekly_root,
    run_id="failed_run",
    signature=signature,
    created_at="2026-07-04T10:00:00+09:00",
    overall_status="failed",
    dry_run=False,
    signals=[{"id": "sig-2", "title": "B"}],
  )
  assert find_previous_successful_weekly_run(tmp_path, signature) is None


def test_cron_and_launchd_preview_are_generated_without_installing() -> None:
  config = default_weekly_run_config()
  config["_config_path"] = "config/v9_weekly_run_config.json"
  cron_preview = build_cron_preview(config, PROJECT_ROOT, sys.executable)
  launchd_preview = build_launchd_preview(config, PROJECT_ROOT, sys.executable)
  assert "scripts/run_v9_weekly_watch.py --config" in cron_preview
  assert "<plist version=\"1.0\">" in launchd_preview
  assert "crontab" not in cron_preview
  assert "launchctl load" not in launchd_preview


def test_cli_exit_codes_and_plain_imports(tmp_path: Path) -> None:
  config_path = tmp_path / "weekly_config.json"
  config_path.write_text(json.dumps(default_weekly_run_config(), ensure_ascii=False, indent=2), encoding="utf-8")
  env = dict(os.environ)
  env.pop("PYTHONPATH", None)
  cli = subprocess.run(
    [
      sys.executable,
      str(PROJECT_ROOT / "scripts" / "run_v9_weekly_watch.py"),
      "--config",
      str(config_path),
      "--dry-run",
      "--no-email",
      "--output-root",
      str(tmp_path / "runs"),
    ],
    cwd=str(PROJECT_ROOT),
    env=env,
    capture_output=True,
    text=True,
    check=False,
  )
  assert cli.returncode == 2
  payload = json.loads(cli.stdout)
  assert payload["status"] == "blocked"

  plain_import = subprocess.run(
    [sys.executable, "-c", "import services_v9.weekly_scheduler; import app; print('ok')"],
    cwd=str(PROJECT_ROOT),
    env=env,
    capture_output=True,
    text=True,
    check=True,
  )
  assert "ok" in plain_import.stdout


def test_scheduler_module_is_streamlit_free_and_has_no_session_state_dependency() -> None:
  source = (PROJECT_ROOT / "services_v9" / "weekly_scheduler.py").read_text(encoding="utf-8")
  assert "import streamlit" not in source
  assert "session_state" not in source
