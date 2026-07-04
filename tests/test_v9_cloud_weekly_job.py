"""Tests for the thin v9 cloud weekly job adapter."""

from __future__ import annotations

import json
from pathlib import Path

import services_v9.cloud_weekly_job as cloud_weekly_job_module
from services_v9.cloud_weekly_settings import resolve_weekly_delivery_settings_path
from services_v9.persistence import save_watch_profile


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
  assert config["paper"]["approved_query_ids"] == ["paper_q08"]
  assert config["web_company"]["approved_query_ids"] == ["gw_q001"]
  assert config["limits"]["paper_max_results"] == 5
  assert config["limits"]["web_max_results"] == 2
  assert config["web_company"]["verification_limit"] == 1
  assert config["paper"]["time_range"] == "all"
  summary = cloud_weekly_job_module.summarize_cloud_weekly_job_config(config, environ=env)
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
