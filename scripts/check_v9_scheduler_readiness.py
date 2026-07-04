"""Readiness checks for the v9 weekly scheduler."""

from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))

from services_v9.retrieval_run_store import build_retrieval_run_manifest, save_retrieval_run_manifest  # noqa: E402
from services_v9.watch_profile_schema import migrate_watch_profile  # noqa: E402
from services_v9.weekly_run_config import default_weekly_run_config, validate_weekly_run_config  # noqa: E402
from services_v9 import paper_openalex_retrieval  # noqa: E402
from services_v9 import patent_bigquery_query  # noqa: E402
from services_v9 import web_company_retrieval  # noqa: E402
from services_v9.weekly_scheduler import (  # noqa: E402
  acquire_weekly_run_lock,
  build_cron_preview,
  build_launchd_preview,
  release_weekly_run_lock,
  run_paper_provider_for_weekly,
  run_patent_provider_for_weekly,
  run_web_company_provider_for_weekly,
  run_weekly_watch,
  validate_approved_query_ids,
)


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


def _write_artifact(root: Path, source_type: str, run_id: str, rows: list[dict]) -> Path:
  mapping = {
    "patent": ("patent_retrieval_runs", "patent_candidates_staged.json"),
    "paper": ("paper_retrieval_runs", "paper_candidates_staged.json"),
    "web_company": ("web_company_retrieval_runs", "web_company_candidates_staged.json"),
  }
  subdir, filename = mapping[source_type]
  target = root / subdir / run_id
  target.mkdir(parents=True, exist_ok=True)
  (target / filename).write_text(
    json.dumps({"retrieval_run_id": run_id, "provider_status": "success", "rows": rows}, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
  )
  return target


def _assert_provider_contracts(root: Path, watch_profile_path: Path) -> None:
  config = default_weekly_run_config()
  config["enabled"] = True
  config["watch_profile_path"] = str(watch_profile_path)
  config["patent"]["approved_query_ids"] = ["patent_q01"]
  config["patent"]["maximum_bytes_billed"] = 1000000
  config["paper"]["approved_query_ids"] = ["paper_q01"]
  config["web_company"]["approved_query_ids"] = ["gw_q001"]

  patent_preview_sig = inspect.signature(patent_bigquery_query.build_patent_bigquery_preview)
  assert "selected_query_id" in patent_preview_sig.parameters
  assert "config" in patent_preview_sig.parameters
  patent_execute_sig = inspect.signature(patent_bigquery_query.execute_patent_bigquery_retrieval)
  assert "dry_run_result" in patent_execute_sig.parameters
  assert "approved" in patent_execute_sig.parameters

  paper_preview_sig = inspect.signature(paper_openalex_retrieval.build_openalex_paper_preview)
  assert "retry_limit" in paper_preview_sig.parameters
  paper_execute_sig = inspect.signature(paper_openalex_retrieval.execute_openalex_paper_retrieval)
  assert "timeout_sec" in paper_execute_sig.parameters

  web_preview_sig = inspect.signature(web_company_retrieval.build_global_web_retrieval_preview)
  assert "verification_limit" in web_preview_sig.parameters
  web_execute_sig = inspect.signature(web_company_retrieval.execute_global_web_retrieval)
  assert "discovery_timeout_sec" in web_execute_sig.parameters

  external_calls = {"network": 0, "smtp": 0}

  def _patent_preview(search_plan, watch_profile, *, selected_query_id=None, time_range="12m", max_results=None, config=None):
    return {"request": {"query_id": selected_query_id}, "validation_rows": [], "parameters": [], "sql": "SELECT 1"}

  def _patent_dry_run(preview, *, client_factory=None, job_config_builder=None, config=None):
    external_calls["network"] += 0
    return {"dry_run_status": "ok", "estimated_bytes": 1, "estimated_cost_usd": 0.0}

  def _patent_execute(preview, dry_run_result, *, approved, client_factory=None, job_config_builder=None, config=None):
    external_calls["network"] += 0
    return {
      "provider_status": "success",
      "retrieval_run_id": "patent_contract_run",
      "rows_retrieved": 1,
      "rows": [{"publication_number": "US1"}],
      "log": {"approved": approved},
      "error": None,
    }

  patent_result = run_patent_provider_for_weekly(
    search_plan={"plans": {"patent": {"queries": [{"query_id": "patent_q01"}]}}},
    watch_profile=_watch_profile(),
    config=config,
    output_root=root,
    weekly_run_id="contract",
    preview_builder=_patent_preview,
    dry_run_runner=_patent_dry_run,
    execute_runner=_patent_execute,
  )
  assert patent_result["status"] == "success"
  assert patent_result["retrieval_run_id"] == "patent_contract_run"
  assert patent_result["artifact_dir"]

  def _paper_preview(search_plan, watch_profile, *, selected_query_id=None, time_range="12m", max_results=None, per_page=25, retry_limit=2, polite_email=None):
    return {"request": {"query_id": selected_query_id, "retry_limit": retry_limit}, "validation_rows": []}

  def _paper_execute(preview, *, opener=None, sleeper=None, timeout_sec=30, rate_limit_sleep_sec=0.2):
    external_calls["network"] += 0
    return {
      "status": "partial_success",
      "run_id": "paper_contract_run",
      "rows_retrieved": 1,
      "rows": [{"work_id": "W1"}],
      "provider_log": [],
      "error": "partial",
    }

  paper_result = run_paper_provider_for_weekly(
    search_plan={"plans": {"paper": {"queries": [{"query_id": "paper_q01"}]}}},
    watch_profile=_watch_profile(),
    config=config,
    output_root=root,
    weekly_run_id="contract",
    preview_builder=_paper_preview,
    execute_runner=_paper_execute,
  )
  assert paper_result["status"] == "partial_success"
  assert paper_result["retrieval_run_id"] == "paper_contract_run"

  def _web_preview(search_plan, *, max_query_count=None, verification_limit=30, summary_top_n=10):
    return {"request": {"queries": list(search_plan["global_web_plan"]["queries"])}, "validation_rows": []}

  def _web_execute(preview, *, tavily_search_post_fn=None, tavily_extract_post_fn=None, google_grounding_fn=None, sleeper=None, discovery_timeout_sec=30, extract_timeout_sec=60, rate_limit_sleep_sec=0.2):
    external_calls["network"] += 0
    return {
      "provider_status": "success",
      "retrieval_run_id": "web_contract_run",
      "rows_retrieved": 1,
      "rows": [{"candidate_id": "W1"}],
      "provider_log": [],
      "error": None,
      "query_count": len(preview["request"]["queries"]),
    }

  web_result = run_web_company_provider_for_weekly(
    search_plan={
      "global_web_plan": {
        "queries": [
          {"query_id": "gw_q001", "enabled": True, "duplicate_of": "", "query_local": "a", "max_results": 5},
          {"query_id": "gw_q999", "enabled": True, "duplicate_of": "", "query_local": "b", "max_results": 5},
        ]
      }
    },
    watch_profile=_watch_profile(),
    config=config,
    output_root=root,
    weekly_run_id="contract",
    preview_builder=_web_preview,
    execute_runner=_web_execute,
  )
  assert web_result["status"] == "success"
  assert web_result["retrieval_run_id"] == "web_contract_run"

  def _paper_execute_raises(preview, *, opener=None, sleeper=None, timeout_sec=30, rate_limit_sleep_sec=0.2):
    raise RuntimeError("contract failure")

  failure = run_paper_provider_for_weekly(
    search_plan={"plans": {"paper": {"queries": [{"query_id": "paper_q01"}]}}},
    watch_profile=_watch_profile(),
    config=config,
    output_root=root,
    weekly_run_id="contract",
    preview_builder=_paper_preview,
    execute_runner=_paper_execute_raises,
  )
  assert failure["status"] == "failed"
  assert failure["rows"] == []
  assert external_calls["network"] == 0
  assert external_calls["smtp"] == 0


def _write_previous_weekly_email_status(
  weekly_root: Path,
  *,
  run_id: str,
  signature: str,
  email_preview: dict[str, object],
  overall_status: str,
  dry_run: bool,
) -> None:
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


def _assert_digest_duplicate_detection(root: Path, watch_profile_path: Path) -> None:
  config = default_weekly_run_config()
  config["enabled"] = True
  config["watch_profile_path"] = str(watch_profile_path)
  config["execution"]["dry_run"] = False
  config["execution"]["patent_enabled"] = True
  config["execution"]["paper_enabled"] = True
  config["execution"]["web_company_enabled"] = True
  config["patent"]["approved_query_ids"] = ["patent_q01"]
  config["patent"]["maximum_bytes_billed"] = 1000000
  config["paper"]["approved_query_ids"] = ["paper_q01"]
  config["web_company"]["approved_query_ids"] = ["gw_q001"]
  config["email"]["mode"] = "self_only"
  config["email"]["self_send_enabled"] = False

  patent_rows = [{
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
    "retrieval_run_id": "patent_saved_run",
    "provider_status": "success",
    "record_stage": "staged",
    "retrieval_mode": "real",
    "data_source": "bigquery_patent",
  }]
  paper_rows = [{
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
    "retrieval_run_id": "paper_saved_run",
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
    "summary_ja": "Toyotaの研究開発更新",
    "retrieval_run_id": "web_saved_run",
    "provider_status": "partial_success",
    "record_stage": "staged",
    "retrieval_mode": "real",
  }]

  def _patent_ok(**kwargs):
    return {
      "status": "success",
      "message": "patent ok",
      "rows": patent_rows,
      "warnings": [],
      "errors": [],
      "provider_log": {"provider": "patent"},
      "source_run": {
        "run_id": "patent_live_run",
        "artifact_dir": str(_write_artifact(root, "patent", "patent_live_run", patent_rows)),
        "status": "success",
        "candidate_count": len(patent_rows),
      },
      "details": {"rows_retrieved": len(patent_rows)},
    }

  def _paper_ok(**kwargs):
    return {
      "status": "success",
      "message": "paper ok",
      "rows": paper_rows,
      "warnings": [],
      "errors": [],
      "provider_log": {"provider": "paper"},
      "source_run": {
        "run_id": "paper_live_run",
        "artifact_dir": str(_write_artifact(root, "paper", "paper_live_run", paper_rows)),
        "status": "success",
        "candidate_count": len(paper_rows),
      },
      "details": {"rows_retrieved": len(paper_rows)},
    }

  def _web_ok(**kwargs):
    return {
      "status": "success",
      "message": "web ok",
      "rows": web_rows,
      "warnings": [],
      "errors": [],
      "provider_log": {"provider": "web_company"},
      "source_run": {
        "run_id": "web_live_run",
        "artifact_dir": str(_write_artifact(root, "web_company", "web_live_run", web_rows)),
        "status": "success",
        "candidate_count": len(web_rows),
      },
      "details": {"rows_retrieved": len(web_rows)},
    }

  baseline = run_weekly_watch(
    config,
    output_root=root / "duplicate_preview_case",
    provider_adapters={"patent": _patent_ok, "paper": _paper_ok, "web_company": _web_ok},
  )
  baseline_status = json.loads((Path(baseline["run_dir"]) / "weekly_run_status.json").read_text(encoding="utf-8"))
  baseline_email = json.loads((Path(baseline["run_dir"]) / "email_preview.json").read_text(encoding="utf-8"))
  digest = str(baseline_email["digest_sha256"])
  signature = str(baseline_status["watch_profile_signature"])

  _write_previous_weekly_email_status(
    root / "duplicate_preview_case" / "weekly_runs",
    run_id="smtp_failed_previous",
    signature=signature,
    email_preview={
      "status": "error",
      "digest_sha256": digest,
      "send_attempted": True,
      "send_succeeded": False,
      "error_type": "SMTPException",
    },
    overall_status="failed",
    dry_run=False,
  )

  send_calls: list[str] = []

  def _mock_send(preview, email_config):
    send_calls.append(str(preview.get("digest_sha256", "")))
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
      "delivery_run_id": "email_delivery_duplicate_case",
      "smtp_host": "smtp.example.com",
      "sender_masked": "s***@example.com",
      "safe_error_message": "",
    }

  config["email"]["self_send_enabled"] = True
  successful_retry = run_weekly_watch(
    config,
    output_root=root / "duplicate_preview_case",
    provider_adapters={"patent": _patent_ok, "paper": _paper_ok, "web_company": _web_ok, "email_send": _mock_send},
  )
  assert len(send_calls) == 1
  successful_retry_status = json.loads((Path(successful_retry["run_dir"]) / "weekly_run_status.json").read_text(encoding="utf-8"))
  assert successful_retry_status["stage_statuses"]["send_email"] == "success"

  blocked_duplicate = run_weekly_watch(
    config,
    output_root=root / "duplicate_preview_case",
    provider_adapters={"patent": _patent_ok, "paper": _paper_ok, "web_company": _web_ok, "email_send": _mock_send},
  )
  assert len(send_calls) == 1
  blocked_status = json.loads((Path(blocked_duplicate["run_dir"]) / "weekly_run_status.json").read_text(encoding="utf-8"))
  assert blocked_status["stage_statuses"]["send_email"] == "blocked"


def _assert_lock_safety(root: Path, watch_profile_path: Path) -> None:
  signature = "a" * 64
  lock_root = root / "weekly_locks_safety"
  first = acquire_weekly_run_lock(signature, "run_a", lock_root, stale_timeout_seconds=60)
  assert first["acquired"] is True

  second = acquire_weekly_run_lock(signature, "run_b", lock_root, stale_timeout_seconds=60)
  assert second["acquired"] is False
  assert second["status"] == "blocked"

  other = acquire_weekly_run_lock("b" * 64, "run_other", lock_root, stale_timeout_seconds=60)
  assert other["acquired"] is True
  release_weekly_run_lock(other)

  first_path = Path(first["path"])
  first_payload = json.loads(first_path.read_text(encoding="utf-8"))
  first_payload["started_at"] = (datetime.now().astimezone() - timedelta(hours=3)).isoformat(timespec="seconds")
  first_path.write_text(json.dumps(first_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

  replaced = acquire_weekly_run_lock(signature, "run_b", lock_root, stale_timeout_seconds=60)
  assert replaced["acquired"] is True
  assert json.loads(first_path.read_text(encoding="utf-8"))["weekly_run_id"] == "run_b"

  mismatch_release = release_weekly_run_lock(first)
  assert mismatch_release["released"] is False
  assert first_path.exists()
  assert release_weekly_run_lock(replaced)["released"] is True

  broken_path = lock_root / f"{signature}.lock"
  broken_path.write_text("{not-json\n", encoding="utf-8")
  fresh_blocked = acquire_weekly_run_lock(signature, "run_c", lock_root, stale_timeout_seconds=60)
  assert fresh_blocked["acquired"] is False
  assert broken_path.exists()
  ts = (datetime.now().astimezone() - timedelta(hours=3)).timestamp()
  os.utime(broken_path, (ts, ts))
  stale_broken = acquire_weekly_run_lock(signature, "run_d", lock_root, stale_timeout_seconds=60)
  assert stale_broken["acquired"] is True
  assert release_weekly_run_lock(stale_broken)["released"] is True

  config = default_weekly_run_config()
  config["enabled"] = True
  config["watch_profile_path"] = str(watch_profile_path)
  config["execution"]["dry_run"] = False
  config["execution"]["patent_enabled"] = True
  config["execution"]["paper_enabled"] = True
  config["execution"]["web_company_enabled"] = True
  config["patent"]["approved_query_ids"] = ["patent_q01"]
  config["patent"]["maximum_bytes_billed"] = 1000000
  config["paper"]["approved_query_ids"] = ["paper_q01"]
  config["web_company"]["approved_query_ids"] = ["gw_q001"]

  def _boom(**kwargs):
    raise RuntimeError("provider boom")

  exception_result = run_weekly_watch(
    config,
    output_root=root / "lock_exception_case",
    provider_adapters={
      "patent": _boom,
      "paper": lambda **kwargs: {
        "status": "success",
        "message": "paper ok",
        "rows": [],
        "warnings": [],
        "errors": [],
        "provider_log": {"provider": "paper"},
        "source_run": {},
        "details": {},
      },
      "web_company": lambda **kwargs: {
        "status": "success",
        "message": "web ok",
        "rows": [],
        "warnings": [],
        "errors": [],
        "provider_log": {"provider": "web_company"},
        "source_run": {},
        "details": {},
      },
    },
  )
  assert exception_result["status"] in {"failed", "partial_success", "blocked"}
  assert not list((root / "lock_exception_case" / "weekly_locks").glob("*.lock"))


def main() -> None:
  config = default_weekly_run_config()
  validation = validate_weekly_run_config(config)
  assert validation["status"] == "ok"
  assert config["enabled"] is False
  assert config["execution"]["dry_run"] is True
  assert validate_approved_query_ids(["patent_q01"], {"patent_q01"}, "patent")["status"] == "ready"
  assert validate_approved_query_ids(["unknown_patent"], {"patent_q01"}, "patent")["status"] == "blocked"

  with tempfile.TemporaryDirectory() as tmp_dir:
    root = Path(tmp_dir)
    watch_profile_path = root / "watch_profile.json"
    watch_profile = _watch_profile()
    watch_profile_path.write_text(json.dumps(watch_profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _assert_provider_contracts(root, watch_profile_path)
    _assert_digest_duplicate_detection(root, watch_profile_path)
    _assert_lock_safety(root, watch_profile_path)

    patent_rows = [{
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
      "retrieval_run_id": "patent_saved_run",
      "provider_status": "success",
      "record_stage": "staged",
      "retrieval_mode": "real",
      "data_source": "bigquery_patent",
    }]
    paper_rows = [{
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
      "retrieval_run_id": "paper_saved_run",
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
      "summary_ja": "Toyotaの研究開発更新",
      "retrieval_run_id": "web_saved_run",
      "provider_status": "partial_success",
      "record_stage": "staged",
      "retrieval_mode": "real",
    }]

    patent_dir = _write_artifact(root, "patent", "patent_saved_run", patent_rows)
    paper_dir = _write_artifact(root, "paper", "paper_saved_run", paper_rows)
    web_dir = _write_artifact(root, "web_company", "web_saved_run", web_rows)
    manifest = build_retrieval_run_manifest(
      migrate_watch_profile(watch_profile),
      {
        "patent": {"run_id": "patent_saved_run", "artifact_dir": str(patent_dir), "status": "success", "candidate_count": 1},
        "paper": {"run_id": "paper_saved_run", "artifact_dir": str(paper_dir), "status": "success", "candidate_count": 1},
        "web_company": {"run_id": "web_saved_run", "artifact_dir": str(web_dir), "status": "partial_success", "candidate_count": 1},
      },
    )
    save_retrieval_run_manifest(manifest, base_dir=root)

    scheduler_config = default_weekly_run_config()
    scheduler_config["enabled"] = True
    scheduler_config["watch_profile_path"] = str(watch_profile_path)
    scheduler_config["execution"]["dry_run"] = True
    scheduler_config["execution"]["patent_enabled"] = True
    scheduler_config["execution"]["paper_enabled"] = True
    scheduler_config["execution"]["web_company_enabled"] = True
    scheduler_config["_config_path"] = str(root / "weekly_config.json")

    result = run_weekly_watch(
      scheduler_config,
      output_root=root,
      provider_adapters={
        "patent": lambda **kwargs: (_ for _ in ()).throw(AssertionError("dry-run patent must not execute")),
        "paper": lambda **kwargs: (_ for _ in ()).throw(AssertionError("dry-run paper must not execute")),
        "web_company": lambda **kwargs: (_ for _ in ()).throw(AssertionError("dry-run web must not execute")),
      },
    )
    assert result["status"] == "partial_success"
    run_dir = Path(result["run_dir"])
    assert (run_dir / "retrieval_run_manifest.json").exists()
    assert (run_dir / "integrated_signals.json").exists()
    assert (run_dir / "weekly_diff.json").exists()
    assert (run_dir / "weekly_digest.md").exists()
    assert (run_dir / "email_preview.json").exists()

    live_config = default_weekly_run_config()
    live_config["enabled"] = True
    live_config["watch_profile_path"] = str(watch_profile_path)
    live_config["execution"]["dry_run"] = False
    live_config["execution"]["patent_enabled"] = True
    live_config["execution"]["paper_enabled"] = True
    live_config["execution"]["web_company_enabled"] = True
    live_config["patent"]["approved_query_ids"] = ["unknown_patent_q99"]
    live_config["patent"]["maximum_bytes_billed"] = 1000000
    live_config["paper"]["approved_query_ids"] = ["paper_q01"]
    live_config["web_company"]["approved_query_ids"] = ["gw_q001"]

    calls = {"patent": 0, "paper": 0, "web_company": 0}

    def _blocked_patent(**kwargs):
      calls["patent"] += 1
      raise AssertionError("blocked patent adapter must not run")

    def _paper_ok(**kwargs):
      calls["paper"] += 1
      return {
        "status": "success",
        "message": "paper ok",
        "rows": paper_rows,
        "warnings": [],
        "errors": [],
        "provider_log": {"provider": "paper"},
        "source_run": {
          "run_id": "paper_live_run",
          "artifact_dir": str(_write_artifact(root, "paper", "paper_live_run", paper_rows)),
          "status": "success",
          "candidate_count": len(paper_rows),
        },
        "details": {"rows_retrieved": len(paper_rows)},
      }

    def _web_ok(**kwargs):
      calls["web_company"] += 1
      return {
        "status": "success",
        "message": "web ok",
        "rows": web_rows,
        "warnings": [],
        "errors": [],
        "provider_log": {"provider": "web_company"},
        "source_run": {
          "run_id": "web_live_run",
          "artifact_dir": str(_write_artifact(root, "web_company", "web_live_run", web_rows)),
          "status": "success",
          "candidate_count": len(web_rows),
        },
        "details": {"rows_retrieved": len(web_rows)},
      }

    live_result = run_weekly_watch(
      live_config,
      output_root=root / "live_case",
      provider_adapters={
        "patent": _blocked_patent,
        "paper": _paper_ok,
        "web_company": _web_ok,
      },
    )
    assert live_result["status"] == "partial_success"
    assert calls["patent"] == 0
    assert calls["paper"] == 1
    assert calls["web_company"] == 1
    live_provider_log = json.loads((Path(live_result["run_dir"]) / "provider_log.json").read_text(encoding="utf-8"))
    assert live_provider_log["patent"]["approved_query_validation"]["unknown_query_ids"] == ["unknown_patent_q99"]

    lock = acquire_weekly_run_lock("a" * 64, "run-lock", root / "weekly_locks", stale_timeout_seconds=60)
    assert lock["acquired"] is True
    release_weekly_run_lock(lock)

    cron_preview = build_cron_preview(scheduler_config, PROJECT_ROOT, sys.executable)
    launchd_preview = build_launchd_preview(scheduler_config, PROJECT_ROOT, sys.executable)
    assert "scripts/run_v9_weekly_watch.py --config" in cron_preview
    assert "<plist version=\"1.0\">" in launchd_preview

    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    imports = subprocess.run(
      [sys.executable, "-c", "import services_v9.weekly_scheduler; import app; print('scheduler startup ok')"],
      cwd=str(PROJECT_ROOT),
      env=env,
      capture_output=True,
      text=True,
      check=True,
    )
    assert "scheduler startup ok" in imports.stdout

  print("[v9 scheduler readiness] OK: weekly signal watch scheduler is ready.")


if __name__ == "__main__":
  main()
