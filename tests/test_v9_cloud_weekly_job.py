"""Tests for the thin v9 cloud weekly job adapter."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import scripts.run_v9_cloud_weekly_job as cloud_job_entrypoint
import services_v9.cloud_weekly_job as cloud_weekly_job_module
from services_v9.cloud_weekly_settings import resolve_weekly_delivery_settings_path
from services_v9.persistence import save_watch_profile
from services_v9.search_plan import build_unified_search_plan


class _FakeBlob:
  def __init__(self, bucket: "_FakeBucket", name: str) -> None:
    self.bucket = bucket
    self.name = name
    self.generation = None

  def exists(self) -> bool:
    return self.name in self.bucket.objects

  def upload_from_string(self, payload: str, content_type: str | None = None, if_generation_match=None) -> None:
    del content_type
    existing = self.bucket.objects.get(self.name)
    if if_generation_match == 0 and existing is not None:
      raise RuntimeError("exists")
    generation = int(existing["generation"] if existing else 0) + 1
    self.bucket.objects[self.name] = {"payload": payload, "generation": generation}
    self.generation = generation

  def download_as_text(self, encoding: str = "utf-8") -> str:
    del encoding
    return str(self.bucket.objects[self.name]["payload"])

  def reload(self) -> None:
    if self.exists():
      self.generation = int(self.bucket.objects[self.name]["generation"])

  def delete(self, if_generation_match=None) -> None:
    existing = self.bucket.objects.get(self.name)
    if existing is None:
      return
    if if_generation_match is not None and int(existing["generation"]) != int(if_generation_match):
      raise RuntimeError("generation mismatch")
    self.bucket.objects.pop(self.name, None)


class _FakeBucket:
  def __init__(self) -> None:
    self.objects: dict[str, dict[str, object]] = {}

  def blob(self, name: str) -> _FakeBlob:
    return _FakeBlob(self, name)


class _FakeStorageClient:
  def __init__(self) -> None:
    self.buckets: dict[str, _FakeBucket] = {}

  def bucket(self, name: str) -> _FakeBucket:
    self.buckets.setdefault(name, _FakeBucket())
    return self.buckets[name]


def _env() -> dict[str, str]:
  return {
    "V9_RUNTIME_MODE": "local",
    "DISABLE_EMAIL_SEND": "false",
    "EMAIL_SEND_MODE": "self_only",
    "SMTP_HOST": "smtp.example.com",
    "SMTP_PORT": "587",
    "SMTP_USER": "tester",
    "SMTP_PASSWORD": "secret",
    "SMTP_FROM_EMAIL": "owner@example.com",
  }


def _profile() -> dict[str, object]:
  return {
    "schema_version": "v9.2",
    "theme_name": "Cloud Weekly Test",
    "theme_description": "Cloud migration dry-run test",
    "keywords": {
      "core_en": ["signal watch"],
      "core_ja": ["シグナル監視"],
      "application_en": [],
      "application_ja": [],
      "material_process_en": [],
      "material_process_ja": [],
      "exclude_en": [],
      "exclude_ja": [],
    },
    "seed_publications": [],
    "candidate_publications": [],
    "target_companies": ["OpenAI"],
    "countries": ["JP"],
    "source_types": ["paper", "web"],
    "cadence": "weekly",
    "priority_rules": [],
    "notes": "",
  }


def _enabled_settings() -> dict[str, object]:
  return {
    "enabled": True,
    "recipient_email": "owner@example.com",
    "weekday": "MON",
    "hour": 9,
    "minute": 0,
    "timezone": "Asia/Tokyo",
  }


def _paper_rows(query_id: str) -> list[dict[str, object]]:
  return [
    {
      "work_id": "https://openalex.org/W1",
      "doi": "10.1000/test1",
      "title": "Signal watch paper",
      "abstract": "abstract",
      "authors": ["Alice"],
      "institutions": ["Example University"],
      "publication_date": "2025-12-01",
      "source_journal": "Battery Journal",
      "cited_by_count": 12,
      "topics": ["Topic"],
      "open_access": True,
      "original_language": "en",
      "source_url": "https://example.org/paper1",
      "query_id": query_id,
      "retrieval_run_id": "paper_retrieval_test",
      "provider_status": "success",
      "record_stage": "staged",
      "retrieval_mode": "real",
    }
  ]


def _web_company_rows(query_id: str) -> list[dict[str, object]]:
  return [
    {
      "candidate_id": "w1",
      "query_id": query_id,
      "country_region": "JP",
      "web_intent": "research_development",
      "result_bucket": "web",
      "original_title": "OpenAI research development",
      "original_snippet": "research development update",
      "original_language": "en",
      "source_url": "https://example.co.jp/news/a",
      "canonical_url": "https://example.co.jp/news/a",
      "event_type": "research_development",
      "organization": "OpenAI",
      "source_quality": "medium_high",
      "content_access": "full",
      "content_hash": "hash1",
      "same_story_group": "story_A",
      "summary_ja": "OpenAI の研究開発更新",
      "retrieval_run_id": "web_company_retrieval_test",
      "provider_status": "success",
      "record_stage": "staged",
      "retrieval_mode": "real",
    }
  ]


def _stage_adapter(source_type: str, rows: list[dict[str, object]], root: Path):
  def _adapter(**kwargs):
    del kwargs
    artifact_dir = root / f"{source_type}_adapter_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return {
      "status": "success",
      "message": f"{source_type} ok",
      "rows": deepcopy(rows),
      "warnings": [],
      "errors": [],
      "provider_log": {"provider": source_type, "rows": len(rows)},
      "source_run": {
        "run_id": f"{source_type}_test_run",
        "artifact_dir": str(artifact_dir),
        "status": "success",
        "candidate_count": len(rows),
      },
      "details": {"rows_retrieved": len(rows)},
    }

  return _adapter


def test_cloud_weekly_job_skips_when_settings_disabled(tmp_path: Path) -> None:
  save_watch_profile(_profile(), base_dir=tmp_path / "v9_runs")
  result = cloud_weekly_job_module.run_cloud_weekly_job(
    environ=_env(),
    output_root=tmp_path / "v9_runs",
  )
  assert result["status"] == "skipped"
  assert result["external_api_called"] is False
  assert result["smtp_called"] is False


def test_cloud_weekly_job_blocks_when_watch_profile_is_missing(tmp_path: Path) -> None:
  from services_v9.cloud_weekly_settings import save_weekly_delivery_settings

  env = {
    **_env(),
    "V9_ALLOWED_RECIPIENTS": "owner@example.com",
  }
  save_weekly_delivery_settings(
    {
      "enabled": True,
      "recipient_email": "owner@example.com",
      "weekday": "MON",
      "hour": 9,
      "minute": 0,
      "timezone": "Asia/Tokyo",
    },
    base_dir=tmp_path / "v9_runs",
    environ=env,
  )
  result = cloud_weekly_job_module.run_cloud_weekly_job(environ=env, output_root=tmp_path / "v9_runs")
  assert result["status"] == "blocked"
  assert "watch_profile_current.json" in result["message"]


def test_cloud_weekly_job_blocks_when_recipient_is_outside_allowlist(tmp_path: Path) -> None:
  env = {
    **_env(),
    "V9_ALLOWED_RECIPIENTS": "owner@example.com",
  }
  save_watch_profile(_profile(), base_dir=tmp_path / "v9_runs")
  settings_path = resolve_weekly_delivery_settings_path(base_dir=tmp_path / "v9_runs", environ=env)
  settings_path.parent.mkdir(parents=True, exist_ok=True)
  settings_path.write_text(json.dumps({
    "schema_version": "v9.6c",
    "enabled": True,
    "recipient_email": "other@example.com",
    "weekday": "MON",
    "hour": 9,
    "minute": 0,
    "timezone": "Asia/Tokyo",
    "cron_expression": "0 9 * * 1",
    "email_mode": "self_only",
    "updated_at": "",
    "updated_by": "streamlit",
    "revision": 1,
    "scheduler_applied_revision": 0,
    "last_scheduler_apply_status": "",
    "last_scheduler_apply_at": "",
    "last_scheduler_known_state": "",
  }, ensure_ascii=False, indent=2), encoding="utf-8")
  result = cloud_weekly_job_module.run_cloud_weekly_job(environ=env, output_root=tmp_path / "v9_runs")
  assert result["status"] == "blocked"
  assert "allowlist" in result["message"]


def test_cloud_weekly_job_reuses_existing_weekly_runner(tmp_path: Path, monkeypatch) -> None:
  env = {
    **_env(),
    "V9_ALLOWED_RECIPIENTS": "owner@example.com",
    "V9_CLOUD_JOB_DRY_RUN": "true",
  }
  save_watch_profile(_profile(), base_dir=tmp_path / "v9_runs")
  from services_v9.cloud_weekly_settings import save_weekly_delivery_settings

  save_weekly_delivery_settings(
    {
      "enabled": True,
      "recipient_email": "owner@example.com",
      "weekday": "MON",
      "hour": 9,
      "minute": 0,
      "timezone": "Asia/Tokyo",
    },
    base_dir=tmp_path / "v9_runs",
    environ=env,
  )
  captured: dict[str, object] = {}

  def fake_run_weekly_watch(config, output_root, provider_adapters):
    captured["config"] = dict(config)
    captured["output_root"] = output_root
    return {"status": "success", "weekly_run_id": "weekly_watch_fake"}

  monkeypatch.setattr(cloud_weekly_job_module, "run_weekly_watch", fake_run_weekly_watch)
  result = cloud_weekly_job_module.run_cloud_weekly_job(environ=env, output_root=tmp_path / "v9_runs")
  assert result["status"] == "success"
  assert captured["output_root"] == tmp_path / "v9_runs"
  assert captured["config"]["watch_profile_path"].endswith("watch_profile_current.json")
  assert captured["config"]["execution"]["paper_enabled"] is True
  assert captured["config"]["execution"]["web_company_enabled"] is True
  assert captured["config"]["_no_email"] is True
  assert result["cloud_job_summary"]["google_grounding"] is False
  assert result["cloud_job_summary"]["email_send_enabled"] is False


def test_build_cloud_weekly_run_config_applies_safe_query_controls(tmp_path: Path) -> None:
  env = {
    **_env(),
    "V9_CLOUD_JOB_DRY_RUN": "false",
    "V9_CLOUD_ENABLE_PATENT": "false",
    "V9_CLOUD_PATENT_APPROVED_QUERY_IDS": "patent_q01,patent_q01",
    "V9_CLOUD_PATENT_MAX_RESULTS": "300",
    "V9_CLOUD_BIGQUERY_PROJECT": "devops-ai-agent-hackathon-2026",
    "V9_CLOUD_BIGQUERY_LOCATION": "US",
    "V9_CLOUD_BIGQUERY_MAX_BYTES_BILLED": "536870912000",
    "V9_CLOUD_BIGQUERY_DRY_RUN_FIRST": "true",
    "V9_CLOUD_BIGQUERY_TOTAL_BYTES_CAP": "1099511627776",
    "V9_CLOUD_BIGQUERY_MAX_QUERY_EXECUTIONS": "1",
    "V9_CLOUD_ENABLE_PAPER": "true",
    "V9_CLOUD_ENABLE_WEB_COMPANY": "true",
    "V9_CLOUD_PAPER_APPROVED_QUERY_IDS": "paper_q08,paper_q08",
    "V9_CLOUD_WEB_APPROVED_QUERY_IDS": "gw_q001,,gw_q001",
    "V9_CLOUD_PAPER_MAX_RESULTS": "5",
    "V9_CLOUD_WEB_MAX_RESULTS": "2",
    "V9_CLOUD_WEB_VERIFICATION_LIMIT": "1",
    "V9_CLOUD_PAPER_TIME_RANGE": "all",
    "V9_CLOUD_WEB_ENGLISH_FALLBACK": "false",
    "V9_CLOUD_GOOGLE_GROUNDING": "false",
  }
  settings = _enabled_settings()
  original_settings = dict(settings)
  original_env = dict(env)
  root = tmp_path / "v9_runs"
  save_watch_profile(_profile(), base_dir=root)
  config = cloud_weekly_job_module.build_cloud_weekly_run_config(settings, persist_root=root, environ=env)
  assert config["execution"]["dry_run"] is False
  assert config["execution"]["patent_enabled"] is False
  assert config["execution"]["paper_enabled"] is True
  assert config["execution"]["web_company_enabled"] is True
  assert config["patent"]["approved_query_ids"] == ["patent_q01"]
  assert config["limits"]["patent_max_results"] == 300
  assert config["patent"]["project_id"] == "devops-ai-agent-hackathon-2026"
  assert config["patent"]["location"] == "US"
  assert config["patent"]["maximum_bytes_billed"] == 536870912000
  assert config["patent"]["dry_run_first"] is True
  assert config["patent"]["total_bytes_cap"] == 1099511627776
  assert config["patent"]["max_query_executions"] == 1
  assert config["paper"]["approved_query_ids"] == ["paper_q08"]
  assert config["web_company"]["approved_query_ids"] == ["gw_q001"]
  assert config["limits"]["paper_max_results"] == 5
  assert config["limits"]["web_max_results"] == 2
  assert config["web_company"]["verification_limit"] == 1
  assert config["paper"]["time_range"] == "all"
  summary = cloud_weekly_job_module.summarize_cloud_weekly_job_config(config, environ=env)
  assert summary["patent_approved_query_ids"] == ["patent_q01"]
  assert summary["patent_max_results"] == 300
  assert summary["bigquery_project_id"] == "devops-ai-agent-hackathon-2026"
  assert summary["bigquery_location"] == "US"
  assert summary["bigquery_maximum_bytes_billed"] == 536870912000
  assert summary["bigquery_dry_run_first"] is True
  assert summary["bigquery_total_bytes_cap"] == 1099511627776
  assert summary["bigquery_max_query_executions"] == 1
  assert summary["web_english_fallback"] is False
  assert summary["google_grounding"] is False
  assert summary["email_send_enabled"] is False
  assert settings == original_settings
  assert env == original_env


def test_resolve_cloud_job_controls_rejects_invalid_query_ids(tmp_path: Path) -> None:
  save_watch_profile(_profile(), base_dir=tmp_path / "v9_runs")
  env = {
    **_env(),
    "V9_CLOUD_PAPER_APPROVED_QUERY_IDS": "paper_q08,https://example.com",
  }
  try:
    cloud_weekly_job_module.resolve_cloud_job_controls(env)
  except RuntimeError as exc:
    assert "invalid query id" in str(exc)
  else:
    raise AssertionError("expected invalid query id to be rejected")


def test_resolve_cloud_job_controls_rejects_invalid_limits_and_bool() -> None:
  cases = [
    {"V9_CLOUD_PAPER_MAX_RESULTS": "6"},
    {"V9_CLOUD_WEB_MAX_RESULTS": "3"},
    {"V9_CLOUD_WEB_VERIFICATION_LIMIT": "2"},
    {"V9_CLOUD_JOB_DRY_RUN": "maybe"},
    {"V9_CLOUD_BIGQUERY_LOCATION": "asia-northeast1"},
    {"V9_CLOUD_BIGQUERY_PROJECT": "INVALID_PROJECT"},
    {"V9_CLOUD_BIGQUERY_MAX_QUERY_EXECUTIONS": "13"},
    {"V9_CLOUD_BIGQUERY_DRY_RUN_FIRST": "false", "V9_CLOUD_ENABLE_PATENT": "true"},
  ]
  for case in cases:
    env = {**_env(), **case}
    try:
      cloud_weekly_job_module.resolve_cloud_job_controls(env)
    except RuntimeError:
      continue
    raise AssertionError(f"expected validation failure for {case}")


def test_cloud_job_defaults_preserve_safe_behavior_when_env_unset(tmp_path: Path) -> None:
  root = tmp_path / "v9_runs"
  save_watch_profile(_profile(), base_dir=root)
  config = cloud_weekly_job_module.build_cloud_weekly_run_config(_enabled_settings(), persist_root=root, environ=_env())
  assert config["execution"]["dry_run"] is True
  assert config["execution"]["patent_enabled"] is False
  assert config["execution"]["paper_enabled"] is True
  assert config["execution"]["web_company_enabled"] is True
  summary = cloud_weekly_job_module.summarize_cloud_weekly_job_config(config, environ=_env())
  assert summary["web_english_fallback"] is False
  assert summary["google_grounding"] is False


def test_cloud_job_print_summary_and_runner_do_not_require_external_calls(tmp_path: Path, monkeypatch) -> None:
  env = {
    **_env(),
    "V9_ALLOWED_RECIPIENTS": "owner@example.com",
    "V9_CLOUD_ENABLE_PAPER": "true",
    "V9_CLOUD_ENABLE_WEB_COMPANY": "true",
  }
  root = tmp_path / "v9_runs"
  save_watch_profile(_profile(), base_dir=root)
  from services_v9.cloud_weekly_settings import save_weekly_delivery_settings

  save_weekly_delivery_settings(_enabled_settings(), base_dir=root, environ=env)
  called: list[str] = []

  def fake_run_weekly_watch(config, output_root, provider_adapters):
    del config, output_root, provider_adapters
    called.append("run")
    return {"status": "success", "weekly_run_id": "weekly_watch_fake"}

  monkeypatch.setattr(cloud_weekly_job_module, "run_weekly_watch", fake_run_weekly_watch)
  result = cloud_weekly_job_module.run_cloud_weekly_job(environ=env, output_root=root)
  assert result["status"] == "success"
  assert called == ["run"]


def test_cloud_job_uses_separate_outer_lock_namespace(tmp_path: Path, monkeypatch) -> None:
  from services_v9.cloud_weekly_settings import save_weekly_delivery_settings

  env = {
    **_env(),
    "V9_ALLOWED_RECIPIENTS": "owner@example.com",
  }
  root = tmp_path / "v9_runs"
  save_watch_profile(_profile(), base_dir=root)
  save_weekly_delivery_settings(_enabled_settings(), base_dir=root, environ=env)
  captured: dict[str, object] = {}

  def fake_acquire(signature, run_id, *, bucket_name="", object_prefix="", storage_client=None, stale_timeout_seconds=21600):
    del signature, run_id, bucket_name, storage_client, stale_timeout_seconds
    captured["object_prefix"] = object_prefix
    return {"acquired": True, "bucket": "bucket", "lock_name": f"{object_prefix}/x.lock", "payload": {"weekly_run_id": "cloud"}}

  def fake_release(lock_info, *, storage_client=None):
    del lock_info, storage_client
    captured["released"] = True
    return {"released": True}

  def fake_run_weekly_watch(config, output_root, provider_adapters):
    del config, output_root, provider_adapters
    return {"status": "success", "weekly_run_id": "weekly_watch_fake"}

  monkeypatch.setattr(cloud_weekly_job_module, "is_cloud_runtime", lambda env: True)
  monkeypatch.setattr(cloud_weekly_job_module, "get_persist_bucket_name", lambda env: "bucket")
  monkeypatch.setattr(cloud_weekly_job_module, "acquire_cloud_weekly_lock", fake_acquire)
  monkeypatch.setattr(cloud_weekly_job_module, "release_cloud_weekly_lock", fake_release)
  monkeypatch.setattr(cloud_weekly_job_module, "run_weekly_watch", fake_run_weekly_watch)
  result = cloud_weekly_job_module.run_cloud_weekly_job(environ=env, output_root=root)
  assert result["status"] == "success"
  assert captured["object_prefix"] == cloud_weekly_job_module.CLOUD_JOB_LOCK_NAMESPACE
  assert captured["released"] is True


def test_cloud_job_real_run_can_pass_build_search_plan_with_separate_locks(tmp_path: Path, monkeypatch) -> None:
  from services_v9.cloud_weekly_settings import save_weekly_delivery_settings

  root = tmp_path / "v9_runs"
  save_watch_profile(_profile(), base_dir=root)
  save_weekly_delivery_settings(
    _enabled_settings(),
    base_dir=root,
    environ={**_env(), "V9_ALLOWED_RECIPIENTS": "owner@example.com"},
  )
  search_plan = build_unified_search_plan(_profile())
  paper_query_id = str(search_plan["plans"]["paper"]["queries"][0]["query_id"])
  web_query = next(
    query
    for query in list(search_plan["global_web_plan"]["queries"])
    if query.get("enabled") and not str(query.get("duplicate_of", "") or "").strip()
  )
  web_query_id = str(web_query["query_id"])
  env = {
    **_env(),
    "V9_ALLOWED_RECIPIENTS": "owner@example.com",
    "V9_CLOUD_JOB_DRY_RUN": "false",
    "V9_CLOUD_ENABLE_PATENT": "false",
    "V9_CLOUD_ENABLE_PAPER": "true",
    "V9_CLOUD_ENABLE_WEB_COMPANY": "true",
    "V9_CLOUD_PAPER_APPROVED_QUERY_IDS": paper_query_id,
    "V9_CLOUD_WEB_APPROVED_QUERY_IDS": web_query_id,
    "V9_CLOUD_PAPER_MAX_RESULTS": "5",
    "V9_CLOUD_WEB_MAX_RESULTS": "2",
    "V9_CLOUD_WEB_VERIFICATION_LIMIT": "1",
    "V9_CLOUD_PAPER_TIME_RANGE": "all",
    "V9_CLOUD_WEB_ENGLISH_FALLBACK": "false",
    "V9_CLOUD_GOOGLE_GROUNDING": "false",
  }
  storage_client = _FakeStorageClient()
  monkeypatch.setattr(cloud_weekly_job_module, "is_cloud_runtime", lambda env: True)
  monkeypatch.setattr(cloud_weekly_job_module, "get_persist_bucket_name", lambda env: "bucket")
  result = cloud_weekly_job_module.run_cloud_weekly_job(
    environ=env,
    output_root=root,
    storage_client=storage_client,
    provider_adapters={
      "paper": _stage_adapter("paper", _paper_rows(paper_query_id), tmp_path),
      "web_company": _stage_adapter("web_company", _web_company_rows(web_query_id), tmp_path),
    },
  )
  assert result["status"] == "success"
  run_dir = Path(result["run_dir"])
  status_payload = json.loads((run_dir / "weekly_run_status.json").read_text(encoding="utf-8"))
  assert status_payload["stage_statuses"]["build_search_plan"] == "success"
  assert status_payload["stage_statuses"]["retrieve_paper"] == "success"
  assert status_payload["stage_statuses"]["retrieve_web_company"] == "success"
  assert not list((root / "weekly_locks").glob("*.lock"))
  assert not storage_client.bucket("bucket").objects


def test_cloud_job_entrypoint_returns_zero_for_controlled_block(monkeypatch) -> None:
  monkeypatch.setattr(
    cloud_job_entrypoint,
    "run_cloud_weekly_job",
    lambda output_root=None: {
      "status": "blocked",
      "block_reason": "blocked_cost_guard",
      "controlled_outcome": True,
      "weekly_run_id": "weekly_blocked",
    },
  )
  assert cloud_job_entrypoint.main([]) == 0


def test_cloud_job_entrypoint_keeps_nonzero_for_uncontrolled_block_and_failure(monkeypatch) -> None:
  monkeypatch.setattr(
    cloud_job_entrypoint,
    "run_cloud_weekly_job",
    lambda output_root=None: {
      "status": "blocked",
      "block_reason": "",
      "controlled_outcome": False,
    },
  )
  assert cloud_job_entrypoint.main([]) == 2

  monkeypatch.setattr(
    cloud_job_entrypoint,
    "run_cloud_weekly_job",
    lambda output_root=None: {
      "status": "failed",
    },
  )
  assert cloud_job_entrypoint.main([]) == 1
