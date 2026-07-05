#!/usr/bin/env python3
"""Validate Study Demo active search run downstream connection (Stage C4A plan)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
  sys.path.insert(0, str(ROOT / "src"))

from services_v9.study_demo_analysis_context import build_active_context_from_run, sanitize_active_context
from services_v9.study_demo_active_loader import build_temporary_search_source_payload
from services_v9.study_demo_config import STUDY_DEMO_BUCKET_DEFAULT
from services_v9.study_demo_downstream import build_downstream_bundle, build_profile_draft_from_search_request

FIXTURE_PATH = ROOT / "tests/fixtures/study_demo_active_run_connection_samples.json"
DEFAULT_RUN_ID = "study_demo_search_20260705_061319_e973e4c2"


def _load_fixture() -> tuple[str, dict[str, Any]]:
  payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
  return str(payload.get("search_run_id", "")), dict(payload.get("artifacts", {}) or {})


def _preview_plan(search_run_id: str) -> dict[str, Any]:
  _, artifacts = _load_fixture()
  ctx = build_active_context_from_run(
    search_run_id=search_run_id,
    artifacts=artifacts,
    bucket_name=STUDY_DEMO_BUCKET_DEFAULT,
  )
  source = build_temporary_search_source_payload(ctx, storage_client=_FakeStorage(artifacts))
  bundle = build_downstream_bundle(ctx, storage_client=_FakeStorage(artifacts))
  draft = dict(bundle.get("profile_draft", {}) or {})
  return {
    "status": "ok",
    "mode": "plan",
    "fixture": FIXTURE_PATH.name,
    "search_run_id": search_run_id,
    "active_context_preview": {k: ctx.get(k) for k in (
      "active_search_run_id", "theme", "provider_counts", "tier_counts", "active_data_source"
    )},
    "loaded_count": source.get("loaded_count"),
    "top_reads_count": len(bundle.get("top_reads_raw", []) or []),
    "profile_draft_status": draft.get("status"),
    "weekly_state": dict(bundle.get("weekly_state", {}) or {}).get("state"),
    "external_api_calls": 0,
    "production_bucket_referenced": False,
  }


class _FakeBlob:
  def __init__(self, store: dict[str, str], name: str) -> None:
    self.name = name
    self._store = store
    self.generation = 1

  def exists(self) -> bool:
    return self.name in self._store

  def reload(self) -> None:
    return None

  def download_as_bytes(self) -> bytes:
    return self._store[self.name].encode()

  def upload_from_string(self, text: str, **kwargs: object) -> None:
    if kwargs.get("if_generation_match") not in (None, 0, self.generation):
      raise RuntimeError("generation mismatch")
    self._store[self.name] = text
    self.generation += 1

  def list_blobs(self, prefix: str = "") -> list["_FakeBlob"]:
    return [self.__class__(self._store, key) for key in self._store if key.startswith(prefix)]


class _FakeBucket:
  def __init__(self, artifacts: dict[str, Any], search_run_id: str) -> None:
    self._store: dict[str, str] = {}
    prefix = f"search_runs/{search_run_id}/"
    mapping = {
      f"{prefix}search_request.json": artifacts.get("search_request.json", {}),
      f"{prefix}provider_status.json": artifacts.get("provider_status.json", {}),
      f"{prefix}integrated_signals.json": artifacts.get("integrated_signals.json", {}),
      f"{prefix}usage_metrics.json": artifacts.get("usage_metrics.json", {}),
      f"{prefix}search_report.md": artifacts.get("search_report.md", ""),
    }
    for key, value in mapping.items():
      if isinstance(value, str):
        self._store[key] = value
      else:
        self._store[key] = json.dumps(value, ensure_ascii=False)

  def blob(self, name: str) -> _FakeBlob:
    return _FakeBlob(self._store, name)

  def list_blobs(self, prefix: str = "") -> list[_FakeBlob]:
    return [_FakeBlob(self._store, name) for name in sorted(self._store) if name.startswith(prefix)]


class _FakeStorage:
  def __init__(self, artifacts: dict[str, Any], search_run_id: str = DEFAULT_RUN_ID) -> None:
    self._bucket = _FakeBucket(artifacts, search_run_id)

  def bucket(self, _name: str) -> _FakeBucket:
    return self._bucket


def main() -> int:
  parser = argparse.ArgumentParser()
  parser.add_argument("--plan", action="store_true")
  parser.add_argument("--search-run-id", default=DEFAULT_RUN_ID)
  args = parser.parse_args()
  if not args.plan:
    print(json.dumps({"status": "blocked", "message": "Stage C4A supports --plan only"}, ensure_ascii=False))
    return 1
  payload = _preview_plan(args.search_run_id)
  print(json.dumps(payload, ensure_ascii=False, indent=2))
  return 0 if payload.get("status") == "ok" else 1


if __name__ == "__main__":
  raise SystemExit(main())
