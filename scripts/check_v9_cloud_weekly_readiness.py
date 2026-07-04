"""Readiness checks for v9 cloud weekly delivery control."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))

from services_v9.cloud_runtime import DEFAULT_WEEKLY_CONFIG_OBJECT, get_persist_root, get_runtime_mode
from services_v9.cloud_scheduler_admin import get_scheduler_job_status
from services_v9.cloud_weekly_job import build_cloud_weekly_run_config, run_cloud_weekly_job
from services_v9.cloud_weekly_settings import (
  build_cron_expression,
  load_weekly_delivery_settings,
  save_weekly_delivery_settings,
  validate_weekly_delivery_settings,
)
from services_v9.persistence import save_watch_profile

class _FakeBlob:
  def __init__(self, bucket: "_FakeBucket", name: str) -> None:
    self.bucket = bucket
    self.name = name
    self.generation = None

  def exists(self) -> bool:
    return self.name in self.bucket.objects

  def upload_from_string(self, payload: str, content_type: str | None = None, if_generation_match=None) -> None:
    existing = self.bucket.objects.get(self.name)
    if if_generation_match == 0 and existing is not None:
      raise RuntimeError("exists")
    generation = (existing["generation"] if existing else 0) + 1
    self.bucket.objects[self.name] = {"payload": payload, "generation": generation}
    self.generation = generation

  def download_as_text(self, encoding: str = "utf-8") -> str:
    return str(self.bucket.objects[self.name]["payload"])

  def reload(self) -> None:
    if self.exists():
      self.generation = self.bucket.objects[self.name]["generation"]

  def delete(self, if_generation_match=None) -> None:
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


def _email_env() -> dict[str, str]:
  return {
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
    "theme_name": "Cloud Weekly Readiness",
    "theme_description": "Cloud readiness",
    "keywords": {
      "core_en": ["signal"],
      "core_ja": ["信号"],
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


def main() -> None:
  assert get_runtime_mode({}) == "local"
  assert str(get_persist_root({"V9_PERSIST_ROOT": "data/v9_runs"})).endswith("data/v9_runs")
  assert build_cron_expression("MON", 9, 0) == "0 9 * * 1"
  assert DEFAULT_WEEKLY_CONFIG_OBJECT == "v9_config/weekly_delivery_config.json"

  validation = validate_weekly_delivery_settings(
    {
      "enabled": True,
      "recipient_email": "owner@example.com",
      "weekday": "MON",
      "hour": 9,
      "minute": 0,
      "timezone": "Asia/Tokyo",
    },
    environ=_email_env(),
  )
  assert validation["status"] == "ok"
  blocked = get_scheduler_job_status(environ={"V9_ENABLE_CLOUD_SCHEDULER_ADMIN": "false"})
  assert blocked["status"] == "blocked"

  with tempfile.TemporaryDirectory() as tmp_dir:
    root = Path(tmp_dir) / "v9_runs"
    save_watch_profile(_profile(), base_dir=root)
    saved = save_weekly_delivery_settings(
      {
        "enabled": False,
        "recipient_email": "owner@example.com",
        "weekday": "WED",
        "hour": 7,
        "minute": 30,
        "timezone": "UTC",
      },
      base_dir=root,
      environ=_email_env(),
    )
    loaded = load_weekly_delivery_settings(base_dir=root, environ=_email_env())
    assert loaded["revision"] == 1
    assert loaded["cron_expression"] == "30 7 * * 3"
    config = build_cloud_weekly_run_config(saved["settings"], persist_root=root, environ=_email_env())
    assert config["watch_profile_path"].endswith("watch_profile_current.json")
    skip_result = run_cloud_weekly_job(environ=_email_env(), output_root=root)
    assert skip_result["status"] == "skipped"

  fake_storage = _FakeStorageClient()
  cloud_env = {
    **_email_env(),
    "V9_RUNTIME_MODE": "cloud",
    "V9_PERSIST_BUCKET": "bucket-a",
    "V9_WEEKLY_CONFIG_OBJECT": DEFAULT_WEEKLY_CONFIG_OBJECT,
  }
  cloud_saved = save_weekly_delivery_settings(
    {
      "enabled": True,
      "recipient_email": "owner@example.com",
      "weekday": "FRI",
      "hour": 8,
      "minute": 45,
      "timezone": "Asia/Tokyo",
    },
    environ=cloud_env,
    storage_client=fake_storage,
  )
  assert cloud_saved["storage_mode"] == "cloud"
  stored_payload = fake_storage.bucket("bucket-a").objects[DEFAULT_WEEKLY_CONFIG_OBJECT]["payload"]
  assert "SMTP_PASSWORD" not in str(stored_payload)

  dockerfile = (PROJECT_ROOT / "Dockerfile.v9").read_text(encoding="utf-8")
  cloudbuild = (PROJECT_ROOT / "cloudbuild.v9.yaml").read_text(encoding="utf-8")
  deploy_script = (PROJECT_ROOT / "scripts" / "deploy_v9_cloud_run_weekly.sh").read_text(encoding="utf-8")
  bootstrap_script = (PROJECT_ROOT / "scripts" / "bootstrap_v9_cloud_weekly_settings.py").read_text(encoding="utf-8")
  assert "streamlit" in dockerfile and "app.py" in dockerfile
  assert "Dockerfile.v9" in cloudbuild
  assert "docker" in cloudbuild
  assert "${_IMAGE_URI}" in cloudbuild
  assert "--file Dockerfile.v9" not in deploy_script
  assert "--config cloudbuild.v9.yaml" in deploy_script
  assert "scripts/run_v9_cloud_weekly_job.py" in deploy_script
  assert "scripts/bootstrap_v9_cloud_weekly_settings.py" in deploy_script
  assert "--region \"${REGION}\"" in deploy_script
  assert "--iap" in deploy_script
  assert "iap.googleapis.com" in deploy_script
  assert "V9_ENABLE_CLOUD_SCHEDULER_ADMIN=false" in deploy_script
  assert "cloudscheduler.googleapis.com" in deploy_script
  assert "--tasks=1" in deploy_script
  assert "--parallelism=1" in deploy_script
  assert "--max-retries=0" in deploy_script
  assert "--task-timeout=30m" in deploy_script
  assert "--max-retry-attempts=0" in deploy_script
  assert 'MODE="${1:---plan}"' in deploy_script
  assert 'if [[ "${V9_CLOUD_CHANGE_APPROVED:-false}" != "true" ]]' in deploy_script
  assert "load_nonsecret_smtp_env_from_dotenv()" in deploy_script
  assert "Path(\".env\")" in deploy_script
  assert "cat .env" not in deploy_script
  service_section = deploy_script.split("deploy_service() {", 1)[1].split("grant_iap_access() {", 1)[0]
  assert "--set-secrets" not in service_section
  assert "SMTP_PASSWORD" not in service_section
  assert "TAVILY_API_KEY" not in service_section
  job_section = deploy_script.split("deploy_job() {", 1)[1].split("bootstrap_settings() {", 1)[0]
  assert "SMTP_PASSWORD=${SMTP_PASSWORD_SECRET}:latest" in job_section
  assert "TAVILY_API_KEY=${TAVILY_API_KEY_SECRET}:latest" in job_section
  assert "DISABLE_EMAIL_SEND=true" in job_section
  assert "EMAIL_SEND_MODE=preview" in job_section
  assert "V9_ENABLE_EMAIL_SEND=false" in job_section
  assert "roles/storage.objectUser" in deploy_script
  assert "roles/secretmanager.secretAccessor" in deploy_script
  assert "gcloud run jobs add-iam-policy-binding" in deploy_script
  assert "gcloud iap web add-iam-policy-binding" in deploy_script
  assert "roles/iap.httpsResourceAccessor" in deploy_script
  bootstrap_section = deploy_script.split("bootstrap_settings() {", 1)[1].split("manual_skip_test() {", 1)[0]
  assert 'V9_RUNTIME_MODE="cloud"' in bootstrap_section
  assert 'V9_PERSIST_BUCKET="${BUCKET}"' in bootstrap_section
  assert 'V9_WEEKLY_CONFIG_OBJECT="${V9_WEEKLY_CONFIG_OBJECT}"' in bootstrap_section
  assert deploy_script.index("bootstrap_settings") < deploy_script.index("deploy_scheduler")
  assert deploy_script.index("deploy_scheduler") < deploy_script.index("pause_scheduler")
  assert "save_weekly_delivery_settings" in bootstrap_script
  assert "load_weekly_delivery_settings" in bootstrap_script
  assert "printf '%s\\n' '{\"enabled\": false}'" not in deploy_script
  assert '"enabled": False' in bootstrap_script
  for banned in ("tech-cartography-v7-demo", "tech-cartography-v7-live", "tech-cartography-v8-demo"):
    assert banned not in deploy_script

  print(json.dumps({
    "status": "ok",
    "runtime_mode": "validated",
    "settings_schema": "validated",
    "scheduler_admin": "blocked by default",
    "cloud_job": "skip path validated",
    "dockerfile": "ready",
    "cloudbuild": "ready",
    "deploy_script": "ready",
  }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
  main()
