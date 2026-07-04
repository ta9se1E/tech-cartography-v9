"""Tests for v9 Cloud Build context and image safety helpers."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import scripts.check_v9_build_context as build_context_script
from scripts.v9_build_security import (
  build_source_cleanup_target,
  extract_nonempty_sensitive_env_names,
  scan_image_context,
  summarize_archive_presence,
  validate_upload_file_list,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _clean_upload_list() -> list[str]:
  return [
    "Dockerfile.v9",
    "cloudbuild.v9.yaml",
    "app.py",
    "services_v9/weekly_scheduler.py",
    "services_v9/cloud_weekly_job.py",
    "ui_v9/tabs.py",
    "scripts/run_v9_cloud_weekly_job.py",
    "scripts/check_v9_cloud_weekly_readiness.py",
    "tests/test_v9_weekly_scheduler.py",
    "README.md",
  ]


def test_validate_upload_file_list_fails_when_forbidden_path_present() -> None:
  result = validate_upload_file_list(_clean_upload_list() + [".env"], minimum_count=5)
  assert result["status"] == "failed"
  assert ".env" in result["forbidden_matches"]


def test_validate_upload_file_list_succeeds_for_clean_context() -> None:
  result = validate_upload_file_list(_clean_upload_list(), minimum_count=5)
  assert result["status"] == "ok"
  assert result["forbidden_match_count"] == 0


def test_validate_upload_file_list_fails_when_required_targets_are_missing() -> None:
  result = validate_upload_file_list(["Dockerfile.v9", "cloudbuild.v9.yaml"], minimum_count=1)
  assert result["status"] == "failed"
  assert "app.py" in result["missing_required_files"]
  assert "services_v9/" in result["missing_required_prefixes"]


def test_scan_image_context_rejects_dotenv_local_config_and_v9_runs() -> None:
  assert scan_image_context(["app/.env"], [])["status"] == "failed"
  assert scan_image_context(["app/config/v9_weekly_run_config.local.json"], [])["status"] == "failed"
  assert scan_image_context(["app/data/v9_runs/run.json"], [])["status"] == "failed"


def test_scan_image_context_rejects_secret_env_key_without_logging_value() -> None:
  result = scan_image_context([], ["SMTP_PASSWORD=super-secret-value"])
  assert result["status"] == "failed"
  assert result["forbidden_env_keys"] == ["SMTP_PASSWORD"]
  assert "super-secret-value" not in json.dumps(result, ensure_ascii=False)


def test_summarize_archive_presence_flags_forbidden_inputs() -> None:
  summary = summarize_archive_presence([
    ".env",
    "config/v9_weekly_run_config.local.json",
    "data/v9_runs/latest/weekly_run_status.json",
    "credentials/service-account-test.json",
  ])
  assert summary[".env_present"] is True
  assert summary["local_config_present"] is True
  assert summary["data_v9_runs_present"] is True
  assert summary["other_credential_filename_present"] is True


def test_extract_nonempty_sensitive_env_names_returns_names_only(tmp_path: Path) -> None:
  dotenv_path = tmp_path / ".env"
  dotenv_path.write_text(
    "SMTP_PASSWORD=secret-one\n"
    "TAVILY_API_KEY=secret-two\n"
    "NORMAL_VALUE=visible\n",
    encoding="utf-8",
  )
  names = extract_nonempty_sensitive_env_names(dotenv_path)
  assert names == ["SMTP_PASSWORD", "TAVILY_API_KEY"]
  assert "secret-one" not in json.dumps(names)
  assert "secret-two" not in json.dumps(names)


def test_build_source_cleanup_target_only_allows_exact_v9_source_archive() -> None:
  clean_target = build_source_cleanup_target({
    "id": "build-1",
    "substitutions": {"_IMAGE_URI": "us-central1-docker.pkg.dev/x/cloud-run-source-deploy/tech-cartography-v9-signal-watch:test"},
    "source": {"storageSource": {"bucket": "bucket-a", "object": "source/path-a.tgz", "generation": "123"}},
  })
  assert clean_target["status"] == "ok"
  assert clean_target["bucket"] == "bucket-a"
  assert clean_target["object"] == "source/path-a.tgz"

  log_target = build_source_cleanup_target({
    "id": "build-2",
    "substitutions": {"_IMAGE_URI": "us-central1-docker.pkg.dev/x/cloud-run-source-deploy/tech-cartography-v9-signal-watch:test"},
    "source": {"storageSource": {"bucket": "102.log-bucket.cloudbuild-logs.googleusercontent.com", "object": "source/path-b.tgz", "generation": "456"}},
  })
  assert log_target["status"] == "blocked"
  assert log_target["reason"] == "log_bucket"

  unrelated_target = build_source_cleanup_target({
    "id": "build-3",
    "substitutions": {"_IMAGE_URI": "us-central1-docker.pkg.dev/x/cloud-run-source-deploy/tech-cartography-v9-signal-watch:test"},
    "source": {"storageSource": {"bucket": "bucket-a", "object": "logs/path-c.txt", "generation": "789"}},
  })
  assert unrelated_target["status"] == "blocked"
  assert unrelated_target["reason"] == "not_source_object"

  v8_target = build_source_cleanup_target({
    "id": "build-4",
    "substitutions": {"_IMAGE_URI": "us-central1-docker.pkg.dev/x/cloud-run-source-deploy/tech-cartography-v8-demo:test"},
    "source": {"storageSource": {"bucket": "bucket-a", "object": "source/path-d.tgz", "generation": "000"}},
  })
  assert v8_target["status"] == "blocked"
  assert v8_target["reason"] == "not_v9_build"


def test_check_v9_build_context_main_fails_when_forbidden_paths_found(monkeypatch, capsys) -> None:
  monkeypatch.setattr(build_context_script, "resolve_listing_command", lambda ignore_file: (["gcloud"], "explicit_ignore_file"))
  monkeypatch.setattr(build_context_script, "list_files_for_upload", lambda listing_command: _clean_upload_list() + [".env"])
  exit_code = build_context_script.main(["--ignore-file", ".gcloudignore", "--minimum-count", "5"])
  captured = capsys.readouterr().out
  assert exit_code == 1
  assert "\"forbidden_match_count\": 1" in captured


def test_check_v9_build_context_main_succeeds_for_clean_context(monkeypatch, capsys) -> None:
  monkeypatch.setattr(build_context_script, "resolve_listing_command", lambda ignore_file: (["gcloud"], "implicit_gcloudignore"))
  monkeypatch.setattr(build_context_script, "list_files_for_upload", lambda listing_command: _clean_upload_list())
  exit_code = build_context_script.main(["--ignore-file", ".gcloudignore", "--minimum-count", "5"])
  captured = capsys.readouterr().out
  assert exit_code == 0
  assert "\"status\": \"ok\"" in captured


def test_safe_build_helper_defaults_to_plan_and_requires_approval_env() -> None:
  helper_path = PROJECT_ROOT / "scripts" / "submit_v9_cloud_build_safe.sh"
  plan = subprocess.run(
    ["bash", str(helper_path)],
    cwd=PROJECT_ROOT,
    check=False,
    capture_output=True,
    text=True,
  )
  assert plan.returncode == 0
  assert "Safe v9 Cloud Build plan only" in plan.stdout

  apply = subprocess.run(
    ["bash", str(helper_path), "--apply"],
    cwd=PROJECT_ROOT,
    check=False,
    capture_output=True,
    text=True,
    env={**os.environ, "HOME": str(PROJECT_ROOT)},
  )
  combined = apply.stdout + apply.stderr
  assert apply.returncode != 0
  assert "V9_CLOUD_CHANGE_APPROVED=true" in combined
