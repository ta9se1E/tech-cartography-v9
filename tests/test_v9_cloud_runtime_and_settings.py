"""Tests for v9 cloud runtime and weekly settings helpers."""

from __future__ import annotations

import json
from pathlib import Path

from services_v9.cloud_runtime import get_persist_root, get_runtime_mode, is_cloud_scheduler_admin_enabled
from services_v9.cloud_weekly_settings import (
  build_cron_expression,
  load_weekly_delivery_settings,
  mask_email_address,
  resolve_allowed_recipients,
  resolve_weekly_delivery_settings_path,
  save_weekly_delivery_settings,
  validate_weekly_delivery_settings,
)


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
      raise RuntimeError("already exists")
    if if_generation_match not in (None, 0) and existing is not None and existing["generation"] != if_generation_match:
      raise RuntimeError("generation mismatch")
    generation = (existing["generation"] if existing else 0) + 1
    self.bucket.objects[self.name] = {
      "payload": payload,
      "generation": generation,
      "content_type": content_type,
    }
    self.generation = generation

  def download_as_text(self, encoding: str = "utf-8") -> str:
    return str(self.bucket.objects[self.name]["payload"])

  def reload(self) -> None:
    if self.exists():
      self.generation = self.bucket.objects[self.name]["generation"]


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


def test_runtime_defaults_to_local() -> None:
  assert get_runtime_mode({}) == "local"


def test_runtime_uses_env_persist_root(tmp_path: Path) -> None:
  root = get_persist_root({"V9_PERSIST_ROOT": str(tmp_path / "persist")})
  assert root == (tmp_path / "persist").resolve()


def test_scheduler_admin_default_is_disabled() -> None:
  assert is_cloud_scheduler_admin_enabled({}) is False


def test_build_cron_expression_uses_cloud_scheduler_weekday_mapping() -> None:
  assert build_cron_expression("MON", 9, 30) == "30 9 * * 1"
  assert build_cron_expression("SUN", 0, 0) == "0 0 * * 0"


def test_mask_email_address_keeps_domain() -> None:
  assert mask_email_address("owner@example.com").endswith("@example.com")


def test_resolve_allowed_recipients_prefers_v9_allowed_recipients() -> None:
  env = {
    **_email_env(),
    "V9_ALLOWED_RECIPIENTS": "alpha@example.com;beta@example.com",
  }
  assert resolve_allowed_recipients(env) == ("alpha@example.com", "beta@example.com")


def test_validate_weekly_delivery_settings_checks_allowlist() -> None:
  validation = validate_weekly_delivery_settings(
    {
      "enabled": True,
      "recipient_email": "other@example.com",
      "weekday": "MON",
      "hour": 9,
      "minute": 0,
      "timezone": "Asia/Tokyo",
    },
    environ=_email_env(),
  )
  assert validation["status"] == "blocked"
  assert any("allowlist" in item for item in validation["errors"])


def test_save_and_load_weekly_delivery_settings_locally(tmp_path: Path) -> None:
  env = _email_env()
  result = save_weekly_delivery_settings(
    {
      "enabled": True,
      "recipient_email": "owner@example.com",
      "weekday": "FRI",
      "hour": 8,
      "minute": 15,
      "timezone": "Asia/Tokyo",
    },
    base_dir=tmp_path / "v9_runs",
    environ=env,
  )
  saved = dict(result["settings"])
  loaded = load_weekly_delivery_settings(base_dir=tmp_path / "v9_runs", environ=env)
  assert saved["revision"] == 1
  assert loaded["recipient_email"] == "owner@example.com"
  assert loaded["cron_expression"] == "15 8 * * 5"


def test_save_weekly_delivery_settings_can_preserve_revision(tmp_path: Path) -> None:
  env = _email_env()
  first = save_weekly_delivery_settings(
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
  second = save_weekly_delivery_settings(
    {
      **dict(first["settings"]),
      "scheduler_applied_revision": 1,
      "last_scheduler_apply_status": "success",
    },
    base_dir=tmp_path / "v9_runs",
    environ=env,
    increment_revision=False,
  )
  assert second["settings"]["revision"] == 1
  assert second["settings"]["scheduler_applied_revision"] == 1


def test_load_weekly_delivery_settings_falls_back_from_broken_json(tmp_path: Path) -> None:
  path = resolve_weekly_delivery_settings_path(
    base_dir=tmp_path / "v9_runs",
    environ={"V9_RUNTIME_MODE": "local"},
  )
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text("{broken", encoding="utf-8")
  loaded = load_weekly_delivery_settings(
    base_dir=tmp_path / "v9_runs",
    environ={"V9_RUNTIME_MODE": "local"},
  )
  assert loaded["enabled"] is False
  assert loaded["revision"] == 0


def test_save_and_load_weekly_delivery_settings_in_cloud_mode() -> None:
  storage_client = _FakeStorageClient()
  env = {
    **_email_env(),
    "V9_RUNTIME_MODE": "cloud",
    "V9_PERSIST_BUCKET": "bucket-a",
    "V9_WEEKLY_CONFIG_OBJECT": "v9_config/weekly_delivery_config.json",
  }
  result = save_weekly_delivery_settings(
    {
      "enabled": True,
      "recipient_email": "owner@example.com",
      "weekday": "TUE",
      "hour": 7,
      "minute": 45,
      "timezone": "UTC",
    },
    environ=env,
    storage_client=storage_client,
  )
  loaded = load_weekly_delivery_settings(environ=env, storage_client=storage_client)
  assert result["storage_mode"] == "cloud"
  assert loaded["weekday"] == "TUE"
  assert loaded["cron_expression"] == "45 7 * * 2"
  blob_payload = storage_client.bucket("bucket-a").objects["v9_config/weekly_delivery_config.json"]["payload"]
  assert "SMTP_PASSWORD" not in str(blob_payload)
  assert json.loads(str(blob_payload))["recipient_email"] == "owner@example.com"
