#!/usr/bin/env python3
"""Theme / Watch Profile / Search Plan lineage checks for Study Demo.

Two validation scopes share the same evaluation logic:

* ``--scope live-cloud`` (default): read-only against the real Study Demo GCS
  bucket. Requires Application Default Credentials. Used by the Deploy workflow
  after WIF authentication.
* ``--scope offline-ci``: deterministic, network-free validation that seeds an
  in-memory storage backend from frozen lineage fixtures and runs the identical
  loaders / validators. Used by GitHub Actions CI. No ADC, no Cloud reads or
  writes; any attempt to reach live Cloud fails loudly (never silently falls
  back to offline).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
  sys.path.insert(0, str(ROOT / "src"))

DEFAULT_SEARCH_RUN_ID = "study_demo_search_20260705_145711_c06e0a1b"
VALID_SCOPES = ("offline-ci", "live-cloud")


def _build_client():
  from google.cloud import storage

  return storage.Client()


# ---------------------------------------------------------------------------
# Shared evaluation logic (scope-independent).
# ---------------------------------------------------------------------------
def evaluate_lineage(
  *,
  search_run_id: str,
  environ: dict[str, str],
  storage_client: Any,
) -> dict[str, Any]:
  """Run lineage validation against whatever storage backend is provided.

  The same real loaders/validators are used for both offline fixtures and live
  Cloud; only the injected ``storage_client`` differs.
  """
  from services_v9.study_demo_analysis_context import (
    detect_context_lineage_inconsistency,
    load_active_context_from_storage,
    normalize_active_context_types,
    sanitize_active_context,
  )
  from services_v9.study_demo_config import get_study_demo_bucket
  from services_v9.study_demo_live_lineage_loader import (
    list_saved_themes_from_storage,
    resolve_active_lineage_artifacts,
  )
  from services_v9.study_demo_search.storage import load_search_run
  from services_v9.study_demo_theme_lineage import enrich_active_context_with_lineage, summarize_lineage_status

  env = dict(environ)
  bucket = get_study_demo_bucket(env)

  active_loaded = load_active_context_from_storage(environ=env, storage_client=storage_client)
  active_context = sanitize_active_context(normalize_active_context_types(dict(active_loaded.get("context", {}) or {})))
  run_prefix = f"search_runs/{search_run_id}/"
  run_loaded = load_search_run(search_run_id, environ=env, storage_client=storage_client)
  search_request = dict((run_loaded.get("artifacts", {}) or {}).get("search_request.json", {}) or {})

  resolved = resolve_active_lineage_artifacts(active_context, environ=env, storage_client=storage_client)
  enriched = enrich_active_context_with_lineage(active_context, search_request=search_request)
  lineage_status = summarize_lineage_status(enriched)
  saved_themes = list_saved_themes_from_storage(environ=env, storage_client=storage_client)
  theme_ids = {str(item.get("theme_id", "")) for item in saved_themes}

  integrated = dict((run_loaded.get("artifacts", {}) or {}).get("integrated_signals.json", {}) or {})
  tier_counts = dict(integrated.get("tier_counts", {}) or {})
  signals = list(integrated.get("signals", []) or [])

  provider_counts = {"patent": 0, "paper": 0, "web": 0}
  for item in signals:
    source = str(item.get("source_type", "") or "").lower()
    if source in provider_counts:
      provider_counts[source] += 1

  inconsistencies = detect_context_lineage_inconsistency(active_context)
  desired_context_type = "watch_profile" if str(enriched.get("run_origin", "")) == "watch_profile" else str(
    enriched.get("context_type", "")
  )

  return {
    "status": "ok",
    "mode": "plan",
    "search_run_id": search_run_id,
    "bucket": bucket,
    "theme_found": bool(resolved.get("theme_found")),
    "watch_profile_found": bool(resolved.get("watch_profile_found")),
    "search_plan_found": bool(resolved.get("search_plan_found")),
    "search_run_found": bool((run_loaded.get("artifacts", {}) or {}).get("search_request.json")),
    "signatures_match": bool(resolved.get("signatures_match")),
    "desired_context_type": desired_context_type,
    "desired_lineage_status": "connected" if resolved.get("signatures_match") else lineage_status.get("lineage_status"),
    "active_context": {
      "active_search_run_id": active_context.get("active_search_run_id"),
      "context_type": active_context.get("context_type"),
      "run_origin": active_context.get("run_origin"),
      "source_theme_id": active_context.get("source_theme_id"),
      "source_watch_profile_id": active_context.get("source_watch_profile_id"),
      "source_search_plan_id": active_context.get("source_search_plan_id"),
      "lineage_status": active_context.get("lineage_status"),
      "active_context_generation": active_context.get("active_context_generation"),
      "context_lineage_inconsistencies": inconsistencies,
    },
    "enriched_preview": {
      "context_type": enriched.get("context_type"),
      "run_origin": enriched.get("run_origin"),
      "lineage_status": enriched.get("lineage_status"),
      "source_theme_id": enriched.get("source_theme_id"),
      "source_watch_profile_id": enriched.get("source_watch_profile_id"),
      "source_search_plan_id": enriched.get("source_search_plan_id"),
    },
    "theme_selector_theme_ids": sorted(theme_ids),
    "theme_selector_includes_new_theme": "theme_6d2dfb753f7e" in theme_ids,
    "theme_selector_includes_default_theme": "theme_default_saved" in theme_ids,
    "integrated_count": len(signals),
    "tier_counts": tier_counts,
    "provider_counts": provider_counts,
    "search_run_prefix": run_prefix,
  }


def _required_checks(result: dict[str, Any]) -> tuple[Any, ...]:
  return (
    result.get("theme_found"),
    result.get("watch_profile_found"),
    result.get("search_plan_found"),
    result.get("search_run_found"),
    result.get("signatures_match"),
    result.get("theme_selector_includes_new_theme"),
    result.get("theme_selector_includes_default_theme"),
  )


# ---------------------------------------------------------------------------
# Live-cloud scope.
# ---------------------------------------------------------------------------
class _ReadCountingClient:
  """Best-effort proxy that counts live Cloud read operations."""

  def __init__(self, inner: Any) -> None:
    self._inner = inner
    self.read_count = 0

  def bucket(self, name: str) -> "_ReadCountingBucket":
    return _ReadCountingBucket(self._inner.bucket(name), self)

  def __getattr__(self, item: str) -> Any:  # pragma: no cover - delegation
    return getattr(self._inner, item)


class _ReadCountingBucket:
  def __init__(self, inner: Any, counter: "_ReadCountingClient") -> None:
    self._inner = inner
    self._counter = counter

  def blob(self, name: str) -> "_ReadCountingBlob":
    return _ReadCountingBlob(self._inner.blob(name), self._counter)

  def list_blobs(self, *args: Any, **kwargs: Any) -> Any:
    self._counter.read_count += 1
    return self._inner.list_blobs(*args, **kwargs)

  def __getattr__(self, item: str) -> Any:  # pragma: no cover - delegation
    return getattr(self._inner, item)


class _ReadCountingBlob:
  def __init__(self, inner: Any, counter: "_ReadCountingClient") -> None:
    self._inner = inner
    self._counter = counter

  def exists(self, *args: Any, **kwargs: Any) -> Any:
    self._counter.read_count += 1
    return self._inner.exists(*args, **kwargs)

  def download_as_bytes(self, *args: Any, **kwargs: Any) -> Any:
    self._counter.read_count += 1
    return self._inner.download_as_bytes(*args, **kwargs)

  def download_as_text(self, *args: Any, **kwargs: Any) -> Any:
    self._counter.read_count += 1
    return self._inner.download_as_text(*args, **kwargs)

  def __getattr__(self, item: str) -> Any:  # pragma: no cover - delegation
    return getattr(self._inner, item)


def run_live_cloud(*, search_run_id: str, environ: dict[str, str] | None = None) -> dict[str, Any]:
  env = dict(environ if environ is not None else os.environ)
  client = _ReadCountingClient(_build_client())
  result = evaluate_lineage(search_run_id=search_run_id, environ=env, storage_client=client)
  active = dict(result.get("active_context", {}) or {})
  result.update(
    {
      "validation_scope": "live-cloud",
      "cloud_auth_required": True,
      "cloud_reads": int(client.read_count),
      "cloud_writes": 0,
      "production_modifications": False,
      "external_api_calls": 0,
      "active_context_generation": active.get("active_context_generation"),
      "active_run_id": active.get("active_search_run_id"),
    }
  )
  return result


# ---------------------------------------------------------------------------
# Offline-ci scope: in-memory storage seeded from frozen lineage fixtures.
# ---------------------------------------------------------------------------
OFFLINE_BUCKET = "tech-cartography-v9-study-demo-1020686343587"
OFFLINE_THEME_ID = "theme_6d2dfb753f7e"


class _MemoryBlob:
  def __init__(self, bucket: "_MemoryBucket", name: str) -> None:
    self.bucket = bucket
    self.name = name
    self.generation = None

  def exists(self) -> bool:
    return self.name in self.bucket.objects

  def reload(self) -> None:
    if self.exists():
      self.generation = self.bucket.objects[self.name]["generation"]

  def upload_from_string(self, payload: str, content_type: str | None = None, if_generation_match: Any = None) -> None:
    existing = self.bucket.objects.get(self.name)
    if if_generation_match == 0 and existing is not None:
      raise RuntimeError("already exists")
    if if_generation_match not in (None, 0) and existing is not None and existing["generation"] != if_generation_match:
      raise RuntimeError("generation mismatch")
    generation = (existing["generation"] if existing else 0) + 1
    self.bucket.objects[self.name] = {"payload": payload, "generation": generation}
    self.generation = generation

  def download_as_bytes(self) -> bytes:
    return str(self.bucket.objects[self.name]["payload"]).encode("utf-8")

  def download_as_text(self, encoding: str = "utf-8") -> str:
    return str(self.bucket.objects[self.name]["payload"])


class _MemoryBucket:
  def __init__(self) -> None:
    self.objects: dict[str, dict[str, Any]] = {}

  def blob(self, name: str) -> _MemoryBlob:
    return _MemoryBlob(self, name)

  def list_blobs(self, *, prefix: str = "") -> Any:
    for name in sorted(self.objects):
      if name.startswith(prefix):
        yield _MemoryBlob(self, name)


class _MemoryStorageClient:
  def __init__(self) -> None:
    self.buckets: dict[str, _MemoryBucket] = {}

  def bucket(self, name: str) -> _MemoryBucket:
    self.buckets.setdefault(name, _MemoryBucket())
    return self.buckets[name]


def _sample_saved_theme() -> dict[str, Any]:
  from services_v9.study_demo_theme_lineage import compute_theme_signature, sizing_fixture_theme

  theme = sizing_fixture_theme()
  theme.update({"theme_id": OFFLINE_THEME_ID, "theme_version": 1, "status": "saved"})
  theme["theme_signature"] = compute_theme_signature(theme)
  return theme


def _offline_integrated_signals() -> dict[str, Any]:
  signals: list[dict[str, Any]] = []
  tier_cycle = ["A", "A", "A", "B", "B", "C", "C", "C", "D", "D", "D", "D", "D", "D", "D"]
  providers = ["patent"] * 5 + ["paper"] * 5 + ["web"] * 5
  for index, source_type in enumerate(providers):
    signals.append(
      {
        "signal_id": f"offline-{source_type}-{index}",
        "source_type": source_type,
        "title": f"offline {source_type} signal {index}",
        "summary": "frozen offline fixture signal",
        "tier": tier_cycle[index],
      }
    )
  return {
    "signals": signals,
    "tier_counts": {"A": 3, "B": 2, "C": 3, "D": 7},
  }


def build_offline_fixture(search_run_id: str) -> tuple[dict[str, str], _MemoryStorageClient, dict[str, Any]]:
  """Seed an in-memory storage backend with a deterministic lineage chain."""
  from services_v9.study_demo_analysis_context import build_active_context_from_run, save_active_context_to_storage
  from services_v9.study_demo_lineage_storage import (
    save_search_plan_lineage_object,
    save_theme_lineage_object,
    save_watch_profile_lineage_object,
  )
  from services_v9.study_demo_theme_lineage import (
    build_search_plan_from_watch_profile,
    build_watch_profile_from_theme,
    default_saved_theme_fixture,
  )

  env = {"V9_STUDY_DEMO_MODE": "true", "V9_STUDY_DEMO_BUCKET": OFFLINE_BUCKET}
  client = _MemoryStorageClient()

  theme = _sample_saved_theme()
  profile = build_watch_profile_from_theme(theme)
  plan = build_search_plan_from_watch_profile(
    profile,
    theme,
    provider_limits={"patent": 5, "paper": 5, "web": 5},
  )
  plan["validation_status"] = "ready_for_execution"

  save_theme_lineage_object(theme, environ=env, storage_client=client)
  save_theme_lineage_object(default_saved_theme_fixture(), environ=env, storage_client=client)
  save_watch_profile_lineage_object(profile, environ=env, storage_client=client)
  save_search_plan_lineage_object(plan, environ=env, storage_client=client)

  integrated = _offline_integrated_signals()
  search_request = {
    "theme": str(theme.get("name", "") or ""),
    "run_origin": "watch_profile",
    "source_theme_id": theme["theme_id"],
    "source_theme_version": theme["theme_version"],
    "source_theme_signature": theme["theme_signature"],
    "source_watch_profile_id": profile["watch_profile_id"],
    "source_watch_profile_version": profile["watch_profile_version"],
    "source_watch_profile_signature": profile["watch_profile_signature"],
    "source_search_plan_id": plan["search_plan_id"],
    "source_search_plan_version": plan["search_plan_version"],
    "source_search_plan_signature": plan["search_plan_signature"],
  }
  artifacts = {"search_request.json": search_request, "integrated_signals.json": integrated}

  prefix = f"search_runs/{search_run_id}/"
  run_bucket = client.bucket(OFFLINE_BUCKET)
  run_bucket.blob(f"{prefix}search_request.json").upload_from_string(json.dumps(search_request))
  run_bucket.blob(f"{prefix}integrated_signals.json").upload_from_string(json.dumps(integrated))

  context = build_active_context_from_run(
    search_run_id=search_run_id,
    artifacts=artifacts,
    bucket_name=OFFLINE_BUCKET,
  )
  save_active_context_to_storage(context, environ=env, storage_client=client)

  return env, client, {"theme": theme, "watch_profile": profile, "search_plan": plan}


def install_no_cloud_guard() -> None:
  """Make any live-Cloud access raise instead of silently falling back."""

  def _raise(*_args: Any, **_kwargs: Any) -> Any:
    raise RuntimeError("offline-ci scope must not access live Cloud")

  import services_v9.study_demo_analysis_context as analysis_context
  import services_v9.study_demo_lineage_storage as lineage_storage
  import services_v9.study_demo_live_lineage_loader as lineage_loader
  import services_v9.study_demo_search.storage as search_storage

  for module in (analysis_context, lineage_storage, lineage_loader, search_storage):
    if hasattr(module, "_build_client"):
      module._build_client = _raise  # type: ignore[attr-defined]

  try:
    import google.auth

    google.auth.default = _raise  # type: ignore[assignment]
  except Exception:  # noqa: BLE001
    pass
  try:
    from google.cloud import storage

    storage.Client = _raise  # type: ignore[assignment]
  except Exception:  # noqa: BLE001
    pass


def run_offline_ci(*, search_run_id: str) -> dict[str, Any]:
  install_no_cloud_guard()
  env, client, _artifacts = build_offline_fixture(search_run_id)
  result = evaluate_lineage(search_run_id=search_run_id, environ=env, storage_client=client)
  result.update(
    {
      "validation_scope": "offline-ci",
      "cloud_auth_required": False,
      "cloud_reads": 0,
      "cloud_writes": 0,
      "production_modifications": False,
      "external_api_calls": 0,
      "fixture": search_run_id,
    }
  )
  return result


# ---------------------------------------------------------------------------
# Backwards-compatible entry points.
# ---------------------------------------------------------------------------
def run_plan(*, search_run_id: str, environ: dict[str, str] | None = None) -> dict[str, Any]:
  """Backwards-compatible live-cloud plan (used when no scope is given)."""
  return run_live_cloud(search_run_id=search_run_id, environ=environ)


def run_scope(*, scope: str, search_run_id: str) -> dict[str, Any]:
  if scope == "offline-ci":
    return run_offline_ci(search_run_id=search_run_id)
  if scope == "live-cloud":
    return run_live_cloud(search_run_id=search_run_id)
  raise ValueError(f"invalid scope: {scope}")


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--plan", action="store_true", help="Read-only plan mode")
  parser.add_argument("--scope", choices=VALID_SCOPES, default="live-cloud", help="Validation scope")
  parser.add_argument("--search-run-id", default=DEFAULT_SEARCH_RUN_ID)
  args = parser.parse_args(argv)
  if not args.plan:
    print(json.dumps({"status": "blocked", "message": "Use --plan for read-only validation"}, ensure_ascii=False, indent=2))
    return 2
  result = run_scope(scope=str(args.scope), search_run_id=str(args.search_run_id))
  if not all(_required_checks(result)):
    result["status"] = "failed"
  print(json.dumps(result, ensure_ascii=False, indent=2))
  return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
  raise SystemExit(main())
