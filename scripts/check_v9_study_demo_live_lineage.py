#!/usr/bin/env python3
"""Read-only live Theme / Watch Profile / Search Plan lineage checks for Study Demo."""

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

DEFAULT_SEARCH_RUN_ID = "study_demo_search_20260705_145711_c06e0a1b"


def _build_client():
  from google.cloud import storage

  return storage.Client()


def run_plan(*, search_run_id: str, environ: dict[str, str] | None = None) -> dict[str, Any]:
  import os

  from services_v9.study_demo_analysis_context import (
    detect_context_lineage_inconsistency,
    load_active_context_from_storage,
    normalize_active_context_types,
    sanitize_active_context,
  )
  from services_v9.study_demo_config import get_study_demo_bucket
  from services_v9.study_demo_lineage_storage import load_json_object
  from services_v9.study_demo_live_lineage_loader import (
    list_saved_themes_from_storage,
    resolve_active_lineage_artifacts,
  )
  from services_v9.study_demo_search.storage import load_search_run
  from services_v9.study_demo_theme_lineage import enrich_active_context_with_lineage, summarize_lineage_status

  env = dict(environ or os.environ)
  client = _build_client()
  bucket = get_study_demo_bucket(env)

  active_loaded = load_active_context_from_storage(environ=env, storage_client=client)
  active_context = sanitize_active_context(normalize_active_context_types(dict(active_loaded.get("context", {}) or {})))
  run_prefix = f"search_runs/{search_run_id}/"
  run_loaded = load_search_run(search_run_id, environ=env, storage_client=client)
  search_request = dict((run_loaded.get("artifacts", {}) or {}).get("search_request.json", {}) or {})

  resolved = resolve_active_lineage_artifacts(active_context, environ=env, storage_client=client)
  enriched = enrich_active_context_with_lineage(active_context, search_request=search_request)
  lineage_status = summarize_lineage_status(enriched)
  saved_themes = list_saved_themes_from_storage(environ=env, storage_client=client)
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
    "external_api_calls": 0,
    "cloud_writes": 0,
    "production_modifications": False,
  }


def main() -> int:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--plan", action="store_true", help="Read-only plan mode")
  parser.add_argument("--search-run-id", default=DEFAULT_SEARCH_RUN_ID)
  args = parser.parse_args()
  if not args.plan:
    print(json.dumps({"status": "blocked", "message": "Use --plan for read-only validation"}, ensure_ascii=False, indent=2))
    return 2
  result = run_plan(search_run_id=str(args.search_run_id))
  print(json.dumps(result, ensure_ascii=False, indent=2))
  required = (
    result.get("theme_found"),
    result.get("watch_profile_found"),
    result.get("search_plan_found"),
    result.get("search_run_found"),
    result.get("signatures_match"),
    result.get("theme_selector_includes_new_theme"),
    result.get("theme_selector_includes_default_theme"),
  )
  return 0 if all(required) else 1


if __name__ == "__main__":
  raise SystemExit(main())
