"""Tests for the v9 cloud watch profile sync helpers."""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime
from pathlib import Path

from services_v9.cloud_watch_profile_sync import (
  DEFAULT_CLOUD_WATCH_PROFILE_OBJECT,
  MISSING_SIGNATURE,
  apply_cloud_watch_profile_sync,
  load_source_watch_profile,
  plan_cloud_watch_profile_sync,
  resolve_cloud_watch_profile_target,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class _FakeBlob:
  def __init__(self, bucket: "_FakeBucket", name: str) -> None:
    self.bucket = bucket
    self.name = name
    self.generation = None

  def exists(self) -> bool:
    return self.name in self.bucket.objects

  def upload_from_string(self, payload: str, content_type: str | None = None, if_generation_match=None) -> None:
    del content_type
    if self.name in self.bucket.fail_uploads:
      raise RuntimeError(f"upload blocked: {self.name}")
    existing = self.bucket.objects.get(self.name)
    if if_generation_match == 0 and existing is not None:
      raise RuntimeError("exists")
    if existing is None and if_generation_match not in (None, 0):
      raise RuntimeError("generation mismatch")
    if existing is not None and if_generation_match not in (None, existing["generation"]):
      raise RuntimeError("generation mismatch")
    generation = int(existing["generation"] if existing else 0) + 1
    self.bucket.objects[self.name] = {"payload": payload, "generation": generation}
    self.bucket.upload_events.append(self.name)
    self.generation = generation

  def download_as_text(self, encoding: str = "utf-8") -> str:
    del encoding
    return str(self.bucket.objects[self.name]["payload"])

  def reload(self) -> None:
    if self.exists():
      self.generation = int(self.bucket.objects[self.name]["generation"])


class _FakeBucket:
  def __init__(self) -> None:
    self.objects: dict[str, dict[str, object]] = {}
    self.upload_events: list[str] = []
    self.fail_uploads: set[str] = set()

  def blob(self, name: str) -> _FakeBlob:
    return _FakeBlob(self, name)


class _FakeStorageClient:
  def __init__(self) -> None:
    self.buckets: dict[str, _FakeBucket] = {}

  def bucket(self, name: str) -> _FakeBucket:
    self.buckets.setdefault(name, _FakeBucket())
    return self.buckets[name]


def _load_sync_script_module():
  script_path = PROJECT_ROOT / "scripts" / "sync_v9_cloud_watch_profile.py"
  spec = importlib.util.spec_from_file_location("sync_v9_cloud_watch_profile_test", script_path)
  assert spec and spec.loader
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  return module


def test_sync_cli_defaults_to_plan(monkeypatch, capsys) -> None:
  module = _load_sync_script_module()
  calls: list[str] = []

  def fake_plan() -> dict[str, object]:
    calls.append("plan")
    return {"status": "ok", "mode": "plan"}

  def fake_apply(**kwargs) -> dict[str, object]:
    del kwargs
    calls.append("apply")
    return {"status": "success"}

  monkeypatch.setattr(module, "plan_cloud_watch_profile_sync", fake_plan)
  monkeypatch.setattr(module, "apply_cloud_watch_profile_sync", fake_apply)
  assert module.main([]) == 0
  assert calls == ["plan"]
  assert '"mode": "plan"' in capsys.readouterr().out


def test_plan_is_read_only_and_shows_signatures_and_diff_summary() -> None:
  storage = _FakeStorageClient()
  result = plan_cloud_watch_profile_sync(
    environ={"V9_PERSIST_BUCKET": "bucket-a"},
    storage_client=storage,
  )
  assert result["status"] == "ok"
  assert result["mode"] == "plan"
  assert result["source_signature"]
  assert result["current_signature"] == MISSING_SIGNATURE
  assert result["diff_summary"]["missing_in_cloud"]
  assert storage.bucket("bucket-a").upload_events == []
  dumped = json.dumps(result, ensure_ascii=False)
  assert '"profile"' not in dumped
  assert '"raw_text"' not in dumped


def test_apply_requires_approval_env() -> None:
  storage = _FakeStorageClient()
  source = load_source_watch_profile()
  result = apply_cloud_watch_profile_sync(
    expected_current_signature=MISSING_SIGNATURE,
    expected_source_signature=source["signature"],
    environ={"V9_PERSIST_BUCKET": "bucket-a"},
    storage_client=storage,
  )
  assert result["status"] == "blocked"
  assert "APPROVED" in result["message"]


def test_apply_blocks_on_expected_signature_mismatch() -> None:
  storage = _FakeStorageClient()
  source = load_source_watch_profile()
  current_bucket = storage.bucket("bucket-a")
  current_bucket.objects[DEFAULT_CLOUD_WATCH_PROFILE_OBJECT] = {
    "payload": json.dumps({"schema_version": "v9.2", "theme_name": "Old", "keywords": {}, "seed_publications": [], "candidate_publications": [], "target_companies": [], "countries": [], "source_types": ["paper"], "cadence": "weekly", "priority_rules": [], "notes": ""}, ensure_ascii=False),
    "generation": 3,
  }
  result_current = apply_cloud_watch_profile_sync(
    expected_current_signature="wrong",
    expected_source_signature=source["signature"],
    environ={"V9_CLOUD_CHANGE_APPROVED": "true", "V9_PERSIST_BUCKET": "bucket-a"},
    storage_client=storage,
  )
  assert result_current["status"] == "blocked"
  result_source = apply_cloud_watch_profile_sync(
    expected_current_signature=result_current["current_signature"],
    expected_source_signature="wrong-source",
    environ={"V9_CLOUD_CHANGE_APPROVED": "true", "V9_PERSIST_BUCKET": "bucket-a"},
    storage_client=storage,
  )
  assert result_source["status"] == "blocked"


def test_apply_backs_up_before_overwrite_and_confirms_saved_signature() -> None:
  storage = _FakeStorageClient()
  source = load_source_watch_profile()
  result = apply_cloud_watch_profile_sync(
    expected_current_signature=MISSING_SIGNATURE,
    expected_source_signature=source["signature"],
    environ={"V9_CLOUD_CHANGE_APPROVED": "true", "V9_PERSIST_BUCKET": "bucket-a"},
    storage_client=storage,
    now=datetime(2026, 7, 4, 12, 0, 0),
  )
  assert result["status"] == "success"
  events = storage.bucket("bucket-a").upload_events
  assert events[0].startswith("watch_profile_backups/20260704_120000_missing.json")
  assert events[1] == DEFAULT_CLOUD_WATCH_PROFILE_OBJECT
  assert result["current_signature_after"] == source["signature"]


def test_apply_stops_if_backup_fails_before_destination_write() -> None:
  storage = _FakeStorageClient()
  source = load_source_watch_profile()
  bucket = storage.bucket("bucket-a")
  bucket.fail_uploads.add("watch_profile_backups/20260704_120000_missing.json")
  result = apply_cloud_watch_profile_sync(
    expected_current_signature=MISSING_SIGNATURE,
    expected_source_signature=source["signature"],
    environ={"V9_CLOUD_CHANGE_APPROVED": "true", "V9_PERSIST_BUCKET": "bucket-a"},
    storage_client=storage,
    now=datetime(2026, 7, 4, 12, 0, 0),
  )
  assert result["status"] == "failed"
  assert DEFAULT_CLOUD_WATCH_PROFILE_OBJECT not in bucket.objects
  assert bucket.upload_events == []


def test_cloud_target_object_is_fixed() -> None:
  target = resolve_cloud_watch_profile_target(
    {
      "GOOGLE_CLOUD_PROJECT": "project-a",
      "V9_PERSIST_BUCKET": "bucket-a",
      "V9_CLOUD_WATCH_PROFILE_OBJECT": "ignored.json",
    }
  )
  assert target["project"] == "project-a"
  assert target["bucket"] == "bucket-a"
  assert target["object_name"] == DEFAULT_CLOUD_WATCH_PROFILE_OBJECT
