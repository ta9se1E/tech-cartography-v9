"""Tests for study demo GCS copy/reset helpers."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from services_v9.study_demo_gcs import (
  copy_seed_from_production,
  reset_active_from_seed,
  validate_sanitized_text,
)
from services_v9.study_demo_storage import dumps_json, sanitize_weekly_delivery_settings


class _FakeBlob:
  def __init__(self, name: str, payload: bytes, *, exists: bool = True) -> None:
    self.name = name
    self._payload = payload
    self._exists = exists
    self.uploaded: bytes | None = None

  def exists(self) -> bool:
    return self._exists

  def download_as_bytes(self) -> bytes:
    return self._payload

  def upload_from_string(self, data: str | bytes, *, content_type: str | None = None) -> None:
    self.uploaded = data if isinstance(data, bytes) else data.encode("utf-8")
    self._exists = True


class _FakeBucket:
  def __init__(self, name: str, blobs: dict[str, _FakeBlob]) -> None:
    self.name = name
    self._blobs = blobs

  def blob(self, name: str) -> _FakeBlob:
    if name not in self._blobs:
      self._blobs[name] = _FakeBlob(name, b"", exists=False)
    return self._blobs[name]

  def list_blobs(self, *, prefix: str = "") -> list[_FakeBlob]:
    return [
      blob
      for blob_name, blob in sorted(self._blobs.items())
      if blob_name.startswith(prefix) and blob._exists and blob.uploaded is not None
    ]

  def copy_blob(self, source_blob: _FakeBlob, destination_bucket: "_FakeBucket", new_name: str) -> _FakeBlob:
    copied = _FakeBlob(new_name, source_blob.uploaded or source_blob._payload, exists=True)
    destination_bucket._blobs[new_name] = copied
    return copied


class _FakeClient:
  def __init__(self, buckets: dict[str, _FakeBucket]) -> None:
    self._buckets = buckets

  def bucket(self, name: str) -> _FakeBucket:
    return self._buckets[name]


def _production_client() -> _FakeClient:
  run = "weekly_runs/cloud_weekly_job_20260704_181253/"
  prod_blobs = {
    f"{run}weekly_digest.md": _FakeBlob(f"{run}weekly_digest.md", b"# digest\n", exists=True),
    f"{run}weekly_diff.json": _FakeBlob(f"{run}weekly_diff.json", b"{}", exists=True),
    f"{run}weekly_run_status.json": _FakeBlob(
      f"{run}weekly_run_status.json",
      dumps_json({"overall_status": "success", "recipient": "secret@example.com"}).encode(),
      exists=True,
    ),
    f"{run}retrieval_run_manifest.json": _FakeBlob(f"{run}retrieval_run_manifest.json", b"{}", exists=True),
    f"{run}provider_log.json": _FakeBlob(f"{run}provider_log.json", b"{}", exists=True),
    f"{run}integrated_signals.json": _FakeBlob(f"{run}integrated_signals.json", b"{}", exists=True),
    f"{run}stage_log.json": _FakeBlob(f"{run}stage_log.json", b"{}", exists=True),
    "watch_profile_current.json": _FakeBlob("watch_profile_current.json", b"{}", exists=True),
    "v9_config/weekly_delivery_config.json": _FakeBlob(
      "v9_config/weekly_delivery_config.json",
      dumps_json({"enabled": True, "email_mode": "self_only", "recipient": "secret@example.com"}).encode(),
      exists=True,
    ),
  }
  demo_blobs: dict[str, _FakeBlob] = {}
  return _FakeClient(
    {
      "tech-cartography-v9-weekly-persist-1020686343587": _FakeBucket(
        "tech-cartography-v9-weekly-persist-1020686343587",
        prod_blobs,
      ),
      "tech-cartography-v9-study-demo-1020686343587": _FakeBucket(
        "tech-cartography-v9-study-demo-1020686343587",
        demo_blobs,
      ),
    }
  )


def test_validate_sanitized_text_rejects_recipient() -> None:
  issues = validate_sanitized_text('{"recipient":"x@example.com"}', object_name="seed/x.json")
  assert "sensitive_key:recipient" in issues


def test_validate_weekly_delivery_settings_preview_only() -> None:
  cleaned = sanitize_weekly_delivery_settings({"enabled": False, "email_mode": "preview", "recipient": ""})
  issues = validate_sanitized_text(
    dumps_json(cleaned),
    object_name="seed/v9_config/weekly_delivery_config.json",
  )
  assert issues == []


def test_copy_seed_from_production_with_fake_client() -> None:
  client = _production_client()
  result = copy_seed_from_production(client)
  assert result["status"] == "copied"
  assert result["copied_object_count"] >= 8
  demo_bucket = client.bucket("tech-cartography-v9-study-demo-1020686343587")
  status_blob = demo_bucket.blob("seed/weekly_runs/cloud_weekly_job_20260704_181253/weekly_run_status.json")
  payload = json.loads((status_blob.uploaded or b"{}").decode())
  assert "recipient" not in payload


def test_reset_active_from_seed_with_fake_client() -> None:
  client = _production_client()
  copy_seed_from_production(client)
  result = reset_active_from_seed(client)
  assert result["status"] == "reset"
  assert result["active_object_count"] >= 1
