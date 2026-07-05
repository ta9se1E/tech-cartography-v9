"""Tests for Study Demo active search run downstream connection (Stage C4A)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from services_v9.study_demo_analysis_context import (
  ACTIVE_CONTEXT_OBJECT,
  build_active_context_from_run,
  is_same_active_context,
  reject_production_bucket_path,
  save_active_context_to_storage,
  validate_active_context,
)
from services_v9.study_demo_active_loader import build_temporary_search_source_payload
from services_v9.study_demo_config import PRODUCTION_PERSIST_BUCKET, STUDY_DEMO_BUCKET_DEFAULT
from services_v9.study_demo_downstream import (
  build_downstream_bundle,
  build_profile_draft_from_search_request,
  build_weekly_state,
  compare_active_run_snapshots,
  save_baseline_snapshot,
  select_top_reads_from_active_signals,
  summarize_run_reviews,
)

FIXTURE_PATH = ROOT / "tests/fixtures/study_demo_active_run_connection_samples.json"


class _FakeBlob:
  def __init__(self, store: dict[str, str], name: str) -> None:
    self.name = name
    self._store = store
    self.generation = 1 if store.get(name, "") else 0

  def exists(self) -> bool:
    return bool(self._store.get(self.name, ""))

  def reload(self) -> None:
    return None

  def download_as_bytes(self) -> bytes:
    return self._store[self.name].encode()

  def upload_from_string(self, text: str, **kwargs: object) -> None:
    match = kwargs.get("if_generation_match")
    if match is not None and match != self.generation:
      raise RuntimeError("generation mismatch")
    self._store[self.name] = text
    self.generation += 1


class _FakeBucket:
  def __init__(self, artifacts: dict, search_run_id: str) -> None:
    self._store: dict[str, str] = {}
    self._blobs: dict[str, _FakeBlob] = {}
    prefix = f"search_runs/{search_run_id}/"
    for suffix, value in artifacts.items():
      key = f"{prefix}{suffix}"
      self._store[key] = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)

  def blob(self, name: str) -> _FakeBlob:
    if name not in self._blobs:
      self._store.setdefault(name, "")
      self._blobs[name] = _FakeBlob(self._store, name)
    return self._blobs[name]

  def list_blobs(self, prefix: str = "") -> list[_FakeBlob]:
    return [self.blob(name) for name in sorted(self._store) if name.startswith(prefix) and self._store[name]]


class _FakeClient:
  def __init__(self, artifacts: dict, search_run_id: str) -> None:
    self._bucket = _FakeBucket(artifacts, search_run_id)

  def bucket(self, _name: str) -> _FakeBucket:
    return self._bucket


def _fixture() -> tuple[str, dict]:
  payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
  return str(payload["search_run_id"]), dict(payload["artifacts"])


def _client() -> _FakeClient:
  run_id, artifacts = _fixture()
  return _FakeClient(artifacts, run_id)


def test_build_active_context_from_run() -> None:
  run_id, artifacts = _fixture()
  ctx = build_active_context_from_run(search_run_id=run_id, artifacts=artifacts, bucket_name=STUDY_DEMO_BUCKET_DEFAULT)
  assert ctx["active_search_run_id"] == run_id
  assert ctx["active_data_source"] == "temporary_search"


def test_active_context_keeps_refs_only() -> None:
  run_id, artifacts = _fixture()
  ctx = build_active_context_from_run(search_run_id=run_id, artifacts=artifacts)
  assert ctx["integrated_signals_ref"].endswith("integrated_signals.json")


def test_no_signal_bodies_in_context() -> None:
  run_id, artifacts = _fixture()
  ctx = build_active_context_from_run(search_run_id=run_id, artifacts=artifacts)
  assert "Bio-based aqueous" not in json.dumps(ctx)


def test_save_active_context_conflict() -> None:
  client = _client()
  run_id, artifacts = _fixture()
  ctx = build_active_context_from_run(search_run_id=run_id, artifacts=artifacts)
  first = save_active_context_to_storage(ctx, storage_client=client)
  other_ctx = build_active_context_from_run(search_run_id=f"{run_id}_other", artifacts=artifacts)
  second = save_active_context_to_storage(other_ctx, expected_generation=0, storage_client=client)
  assert first["status"] == "saved"
  assert second["status"] == "conflict"


def test_duplicate_active_context_idempotent() -> None:
  client = _client()
  run_id, artifacts = _fixture()
  ctx = build_active_context_from_run(search_run_id=run_id, artifacts=artifacts)
  first = save_active_context_to_storage(ctx, storage_client=client)
  second = save_active_context_to_storage(ctx, expected_generation=first.get("generation"), storage_client=client)
  assert second["status"] == "unchanged"


def test_reject_production_bucket_path() -> None:
  with pytest.raises(ValueError):
    reject_production_bucket_path(PRODUCTION_PERSIST_BUCKET)


def test_common_loader_temporary_search() -> None:
  run_id, artifacts = _fixture()
  ctx = build_active_context_from_run(search_run_id=run_id, artifacts=artifacts)
  payload = build_temporary_search_source_payload(ctx, storage_client=_client())
  assert payload["mode"] == "temporary_search"
  assert payload["loaded_count"] >= 1


def test_loader_does_not_call_providers() -> None:
  run_id, artifacts = _fixture()
  ctx = build_active_context_from_run(search_run_id=run_id, artifacts=artifacts)
  with patch("services_v9.study_demo_search.patent_provider.run_study_demo_patent_execute") as patent_mock:
    build_temporary_search_source_payload(ctx, storage_client=_client())
  patent_mock.assert_not_called()


def test_tier_a_priority_top_reads() -> None:
  run_id, artifacts = _fixture()
  bundle = build_downstream_bundle(build_active_context_from_run(search_run_id=run_id, artifacts=artifacts), storage_client=_client())
  titles = [str(item.get("title", "")) for item in bundle["top_reads_raw"]]
  assert any("Bio-based aqueous" in title for title in titles)


def test_no_forced_low_relevance_web_in_top3() -> None:
  run_id, artifacts = _fixture()
  bundle = build_downstream_bundle(build_active_context_from_run(search_run_id=run_id, artifacts=artifacts), storage_client=_client())
  titles = [str(item.get("title", "")) for item in bundle["top_reads_raw"]]
  assert not any("polyester fiber fabric" in title for title in titles[:3])


def test_no_demo_wording_in_adapter() -> None:
  run_id, artifacts = _fixture()
  bundle = build_downstream_bundle(build_active_context_from_run(search_run_id=run_id, artifacts=artifacts), storage_client=_client())
  assert "デモ用途" not in json.dumps(bundle["display_signals"], ensure_ascii=False)


def test_weekly_initial_baseline() -> None:
  run_id, artifacts = _fixture()
  ctx = build_active_context_from_run(search_run_id=run_id, artifacts=artifacts)
  integrated = build_downstream_bundle(ctx, storage_client=_client())["integrated"]
  state = build_weekly_state(context=ctx, snapshots=[], integrated=integrated)
  assert state["state"] == "initial_baseline"


def test_snapshot_save_explicit() -> None:
  run_id, artifacts = _fixture()
  ctx = build_active_context_from_run(search_run_id=run_id, artifacts=artifacts)
  integrated = build_downstream_bundle(ctx, storage_client=_client())["integrated"]
  saved = save_baseline_snapshot(context=ctx, integrated=integrated, profile_signature="abc", storage_client=_client())
  assert saved["source_run_id"] == run_id


def test_compare_stable_keys() -> None:
  prev = {"signals": [{"signal_key": "patent:family:F1", "relevance_score": 50, "relevance_tier": "B", "title": "A"}]}
  curr = [{"family_id": "F1", "source_type": "patent", "source_id": "X", "relevance_score": 70, "relevance_tier": "A", "title": "A"}]
  diff = compare_active_run_snapshots(prev, curr)
  assert diff["counts"]["score_up"] == 1


def test_profile_draft_status() -> None:
  run_id, artifacts = _fixture()
  ctx = build_active_context_from_run(search_run_id=run_id, artifacts=artifacts)
  integrated = build_downstream_bundle(ctx, storage_client=_client())["integrated"]
  draft = build_profile_draft_from_search_request(context=ctx, search_request=artifacts["search_request.json"], integrated=integrated)
  assert draft["status"] == "draft_not_applied"


def test_digest_contains_run_id() -> None:
  run_id, artifacts = _fixture()
  bundle = build_downstream_bundle(build_active_context_from_run(search_run_id=run_id, artifacts=artifacts), storage_client=_client())
  assert bundle["digest"]["search_run_id"] == run_id


def test_export_has_no_secrets() -> None:
  run_id, artifacts = _fixture()
  exports = build_downstream_bundle(build_active_context_from_run(search_run_id=run_id, artifacts=artifacts), storage_client=_client())["digest_exports"]
  blob = json.dumps(exports).lower()
  assert "api_key" not in blob
  assert "password" not in blob


def test_check_script_plan() -> None:
  completed = subprocess.run(
    [sys.executable, str(ROOT / "scripts/check_v9_study_demo_active_run_connection.py"), "--plan"],
    cwd=ROOT,
    check=True,
    capture_output=True,
    text=True,
  )
  assert json.loads(completed.stdout)["status"] == "ok"


def test_ui_wires_common_loader() -> None:
  source = Path(ROOT / "ui_v9/signal_watch_app.py").read_text(encoding="utf-8")
  assert "build_temporary_search_source_payload" in source
  assert "temporary_search" in source


def test_is_same_active_context() -> None:
  assert is_same_active_context({"active_search_run_id": "a"}, {"active_search_run_id": "a"})


def test_summarize_run_reviews() -> None:
  reviews = {"reviews": [{"signal_id": "a", "decision": "accepted", "source_run_id": "run1"}]}
  summary = summarize_run_reviews(reviews, ["a", "b"])
  assert summary["accepted"] == 1
  assert summary["unreviewed"] == 1


def test_select_top_reads_skips_low_web() -> None:
  signals = [
    {"signal_id": "1", "source_type": "patent", "relevance_tier": "A", "relevance_score": 90, "title": "p"},
    {"signal_id": "2", "source_type": "paper", "relevance_tier": "A", "relevance_score": 85, "title": "w"},
    {"signal_id": "3", "source_type": "web_company", "relevance_tier": "D", "relevance_score": 5, "title": "bad"},
  ]
  selected = select_top_reads_from_active_signals(signals, limit=3)
  assert all(item["source_type"] != "web_company" for item in selected)


def test_validate_active_context_rejects_bad_schema() -> None:
  assert validate_active_context({"schema_version": 99})
