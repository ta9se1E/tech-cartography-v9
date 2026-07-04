"""Tests for v9 cloud lock helpers."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from services_v9.cloud_weekly_job import CLOUD_JOB_LOCK_NAMESPACE
from services_v9.cloud_lock import acquire_cloud_weekly_lock, release_cloud_weekly_lock
from services_v9.weekly_scheduler import acquire_weekly_run_lock, release_weekly_run_lock


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
    existing = self.bucket.objects.get(self.name)
    if existing is None:
      return
    if if_generation_match is not None and existing["generation"] != if_generation_match:
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


def _signature() -> str:
  return "a" * 64


def _signature_b() -> str:
  return "b" * 64


def test_acquire_and_release_cloud_lock() -> None:
  client = _FakeStorageClient()
  acquired = acquire_cloud_weekly_lock(_signature(), "run-1", bucket_name="bucket", storage_client=client)
  released = release_cloud_weekly_lock(acquired, storage_client=client)
  assert acquired["acquired"] is True
  assert released["released"] is True


def test_second_acquire_is_blocked_when_lock_is_fresh() -> None:
  client = _FakeStorageClient()
  first = acquire_cloud_weekly_lock(_signature(), "run-1", bucket_name="bucket", storage_client=client)
  second = acquire_cloud_weekly_lock(_signature(), "run-2", bucket_name="bucket", storage_client=client)
  assert first["acquired"] is True
  assert second["status"] == "blocked"


def test_stale_cloud_lock_is_replaced() -> None:
  client = _FakeStorageClient()
  past = datetime.now().astimezone() - timedelta(hours=8)
  first = acquire_cloud_weekly_lock(
    _signature(),
    "run-1",
    bucket_name="bucket",
    storage_client=client,
    stale_timeout_seconds=60,
    now=past,
  )
  second = acquire_cloud_weekly_lock(
    _signature(),
    "run-2",
    bucket_name="bucket",
    storage_client=client,
    stale_timeout_seconds=60,
    now=datetime.now().astimezone(),
  )
  assert first["acquired"] is True
  assert second["acquired"] is True
  assert second["payload"]["weekly_run_id"] == "run-2"


def test_release_cloud_lock_keeps_other_owner_lock() -> None:
  client = _FakeStorageClient()
  first = acquire_cloud_weekly_lock(_signature(), "run-1", bucket_name="bucket", storage_client=client)
  result = release_cloud_weekly_lock(
    {**first, "payload": {**dict(first["payload"]), "weekly_run_id": "run-2"}},
    storage_client=client,
  )
  assert result["status"] == "ignored"
  assert client.bucket("bucket").blob(first["lock_name"]).exists() is True


def test_cloud_job_namespace_is_used_for_outer_lock() -> None:
  client = _FakeStorageClient()
  acquired = acquire_cloud_weekly_lock(
    _signature(),
    "run-1",
    bucket_name="bucket",
    object_prefix=CLOUD_JOB_LOCK_NAMESPACE,
    storage_client=client,
  )
  assert acquired["acquired"] is True
  assert acquired["lock_name"] == f"{CLOUD_JOB_LOCK_NAMESPACE}/{_signature()}.lock"


def test_different_signatures_can_acquire_cloud_locks() -> None:
  client = _FakeStorageClient()
  first = acquire_cloud_weekly_lock(
    _signature(),
    "run-1",
    bucket_name="bucket",
    object_prefix=CLOUD_JOB_LOCK_NAMESPACE,
    storage_client=client,
  )
  second = acquire_cloud_weekly_lock(
    _signature_b(),
    "run-2",
    bucket_name="bucket",
    object_prefix=CLOUD_JOB_LOCK_NAMESPACE,
    storage_client=client,
  )
  assert first["acquired"] is True
  assert second["acquired"] is True


def test_cloud_job_and_weekly_scheduler_locks_do_not_conflict(tmp_path: Path) -> None:
  client = _FakeStorageClient()
  outer = acquire_cloud_weekly_lock(
    _signature(),
    "cloud-job-run",
    bucket_name="bucket",
    object_prefix=CLOUD_JOB_LOCK_NAMESPACE,
    storage_client=client,
  )
  inner_root = tmp_path / "v9_runs" / "weekly_locks"
  inner = acquire_weekly_run_lock(_signature(), "weekly-run", inner_root)
  assert outer["acquired"] is True
  assert inner["acquired"] is True
  assert outer["lock_name"] == f"{CLOUD_JOB_LOCK_NAMESPACE}/{_signature()}.lock"
  assert Path(inner["path"]).name == f"{_signature()}.lock"
  assert "weekly_locks" in Path(inner["path"]).parts

  outer_release = release_cloud_weekly_lock(outer, storage_client=client)
  assert outer_release["released"] is True
  assert Path(inner["path"]).exists() is True

  inner_release = release_weekly_run_lock(inner)
  assert inner_release["released"] is True
  assert client.bucket("bucket").blob(outer["lock_name"]).exists() is False


def test_weekly_lock_release_does_not_delete_cloud_job_lock(tmp_path: Path) -> None:
  client = _FakeStorageClient()
  outer = acquire_cloud_weekly_lock(
    _signature(),
    "cloud-job-run",
    bucket_name="bucket",
    object_prefix=CLOUD_JOB_LOCK_NAMESPACE,
    storage_client=client,
  )
  inner_root = tmp_path / "v9_runs" / "weekly_locks"
  inner = acquire_weekly_run_lock(_signature(), "weekly-run", inner_root)
  inner_release = release_weekly_run_lock(inner)
  assert inner_release["released"] is True
  assert client.bucket("bucket").blob(outer["lock_name"]).exists() is True
