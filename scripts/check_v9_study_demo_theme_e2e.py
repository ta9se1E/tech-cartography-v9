#!/usr/bin/env python3
"""Fixture-only end-to-end theme lineage checks for Study Demo Stage C5A."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
  sys.path.insert(0, str(ROOT / "src"))


def _load_fixture_samples() -> dict:
  fixture_path = ROOT / "tests" / "fixtures" / "study_demo_active_run_connection_samples.json"
  return json.loads(fixture_path.read_text(encoding="utf-8"))


def run_plan(*, fixture_theme: str, provider_limit: int, environ: dict | None = None) -> dict:
  import os

  env = dict(environ or os.environ)
  bucket = str(env.get("V9_STUDY_DEMO_BUCKET", "tech-cartography-v9-study-demo-local-fixture"))
  from services_v9.study_demo_analysis_context import build_active_context_from_run
  from services_v9.study_demo_downstream import build_downstream_bundle
  from services_v9.study_demo_theme_lineage import (
    build_search_plan_from_watch_profile,
    build_search_run_lineage,
    build_theme_lineage,
    build_watch_profile_from_theme,
    enrich_active_context_with_lineage,
    sizing_fixture_theme,
    summarize_lineage_status,
    validate_theme_lineage,
  )

  external_api_calls = 0
  cloud_writes = 0

  if fixture_theme == "sizing":
    theme = sizing_fixture_theme()
  else:
    theme = sizing_fixture_theme()

  theme["status"] = "saved"
  profile = build_watch_profile_from_theme(theme)
  plan = build_search_plan_from_watch_profile(
    profile,
    theme,
    provider_limits={"patent": provider_limit, "paper": provider_limit, "web": provider_limit},
    external_execution_allowed=False,
  )
  lineage = build_theme_lineage(theme=theme, watch_profile=profile, search_plan=plan, search_run={})
  lineage_errors = validate_theme_lineage(lineage)
  if lineage_errors:
    raise RuntimeError(f"lineage validation failed: {lineage_errors}")

  samples = _load_fixture_samples()
  run_id = str(samples.get("search_run_id", ""))
  artifacts = dict(samples.get("artifacts", {}) or {})
  temp_request = dict(artifacts.get("search_request.json", {}) or {})
  temp_request["run_origin"] = "temporary_search"

  temp_context = build_active_context_from_run(search_run_id=run_id, artifacts=artifacts, bucket_name=bucket)
  temp_enriched = enrich_active_context_with_lineage(temp_context, search_request=temp_request)
  temp_status = summarize_lineage_status(temp_enriched)

  watch_request = dict(temp_request)
  watch_request.update(
    {
      "run_origin": "watch_profile",
      "source_search_plan_id": plan.get("search_plan_id"),
      "source_search_plan_version": plan.get("search_plan_version"),
      "source_search_plan_signature": plan.get("search_plan_signature"),
      "source_watch_profile_id": profile.get("watch_profile_id"),
      "source_watch_profile_version": profile.get("watch_profile_version"),
      "source_watch_profile_signature": profile.get("watch_profile_signature"),
      "source_theme_id": theme.get("theme_id"),
      "source_theme_version": theme.get("theme_version"),
      "source_theme_signature": theme.get("theme_signature"),
    }
  )
  watch_run_lineage = build_search_run_lineage(
    search_run_id=f"{run_id}_watch",
    search_plan=plan,
    theme=theme,
    watch_profile=profile,
    run_origin="watch_profile",
  )
  watch_context = enrich_active_context_with_lineage(
    {
      **temp_context,
      "active_search_run_id": f"{run_id}_watch",
      "theme": theme.get("name"),
    },
    search_request=watch_request,
    run_lineage=watch_run_lineage,
  )
  watch_status = summarize_lineage_status(watch_context)

  class _FakeBlob:
    def __init__(self, name: str, payload: bytes | None = None):
      self.name = name
      self._payload = payload

    def exists(self) -> bool:
      return self._payload is not None

    def download_as_bytes(self) -> bytes:
      return self._payload or b"{}"

  class _FakeBucket:
    def __init__(self, objects: dict[str, bytes]):
      self._objects = objects

    def blob(self, name: str) -> _FakeBlob:
      return _FakeBlob(name, self._objects.get(name))

    def list_blobs(self, *, prefix: str = ""):
      for name in self._objects:
        if name.startswith(prefix):
          yield _FakeBlob(name, self._objects[name])

  class _FakeClient:
    def __init__(self, objects: dict[str, bytes]):
      self._objects = objects

    def bucket(self, _name: str) -> _FakeBucket:
      return _FakeBucket(self._objects)

  prefix = f"search_runs/{run_id}/"
  objects = {f"{prefix}{key}": json.dumps(value, ensure_ascii=False).encode("utf-8") for key, value in artifacts.items()}
  client = _FakeClient(objects)
  bundle = build_downstream_bundle(temp_enriched, storage_client=client, environ={"V9_STUDY_DEMO_MODE": "true"})

  banner_status = dict(bundle.get("lineage_status", {}) or {})
  proposal_count = int(dict(bundle.get("review_proposals", {}).get("summary", {})).get("proposal_count", 0))

  return {
    "status": "ok",
    "mode": "plan",
    "fixture_theme": fixture_theme,
    "provider_limit": provider_limit,
    "theme_id_short": str(theme.get("theme_id", ""))[:12],
    "theme_signature_short": str(theme.get("theme_signature", ""))[:8],
    "watch_profile_id_short": str(profile.get("watch_profile_id", ""))[:12],
    "search_plan_id_short": str(plan.get("search_plan_id", ""))[:12],
    "temporary_lineage_status": temp_status.get("lineage_status"),
    "watch_lineage_status": watch_status.get("lineage_status"),
    "banner_lineage_status": banner_status.get("lineage_status"),
    "downstream_tier_count": len(dict(bundle.get("tier_counts", {}) or {})),
    "proposal_count": proposal_count,
    "lineage_validation_errors": len(lineage_errors),
    "external_api_calls": external_api_calls,
    "cloud_writes": cloud_writes,
    "production_references": False,
  }


def main() -> int:
  parser = argparse.ArgumentParser()
  parser.add_argument("--plan", action="store_true")
  parser.add_argument("--fixture-theme", default="sizing")
  parser.add_argument("--provider-limit", type=int, default=5)
  args = parser.parse_args()

  os.environ.setdefault("V9_STUDY_DEMO_MODE", "true")
  bucket = os.environ.get("V9_STUDY_DEMO_BUCKET", "tech-cartography-v9-study-demo-local-fixture")
  os.environ.setdefault("V9_STUDY_DEMO_BUCKET", bucket)

  if not args.plan:
    print(json.dumps({"status": "plan_required"}, ensure_ascii=False))
    return 2

  payload = run_plan(fixture_theme=args.fixture_theme, provider_limit=args.provider_limit, environ=os.environ)
  print(json.dumps(payload, ensure_ascii=False, indent=2))
  return 0 if payload.get("status") == "ok" else 1


if __name__ == "__main__":
  raise SystemExit(main())
