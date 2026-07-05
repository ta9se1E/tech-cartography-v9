#!/usr/bin/env python3
"""Normalize Study Demo Active Context lineage fields for a saved watch_profile run."""

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

APPLY_ENV = "V9_STUDY_DEMO_LIVE_LINEAGE_APPROVED"
DEFAULT_SEARCH_RUN_ID = "study_demo_search_20260705_145711_c06e0a1b"


def _build_client():
  from google.cloud import storage

  return storage.Client()


def build_normalized_context(
  *,
  search_run_id: str,
  environ: dict[str, str] | None = None,
  storage_client: Any | None = None,
) -> dict[str, Any]:
  from services_v9.study_demo_analysis_context import (
    load_active_context_from_storage,
    normalize_active_context_types,
    sanitize_active_context,
  )
  from services_v9.study_demo_live_lineage_loader import resolve_active_lineage_artifacts
  from services_v9.study_demo_search.storage import load_search_run
  from services_v9.study_demo_theme_lineage import enrich_active_context_with_lineage, summarize_lineage_status

  env = dict(environ or os.environ)
  client = storage_client if storage_client is not None else _build_client()
  loaded = load_active_context_from_storage(environ=env, storage_client=client)
  if loaded.get("status") not in {"ok", "invalid"} or not loaded.get("context"):
    return {"status": "blocked", "message": "active context missing or invalid", "loaded": loaded}

  current = sanitize_active_context(normalize_active_context_types(dict(loaded.get("context", {}) or {})))
  if str(current.get("active_search_run_id", "")) != search_run_id:
    return {
      "status": "blocked",
      "message": "active context run mismatch",
      "expected": search_run_id,
      "actual": current.get("active_search_run_id"),
    }

  run_loaded = load_search_run(search_run_id, environ=env, storage_client=client)
  search_request = dict((run_loaded.get("artifacts", {}) or {}).get("search_request.json", {}) or {})
  resolved = resolve_active_lineage_artifacts(current, environ=env, storage_client=client)
  if not resolved.get("signatures_match"):
    return {"status": "blocked", "message": "lineage signatures do not match", "resolved": resolved}

  enriched = enrich_active_context_with_lineage(current, search_request=search_request)
  enriched["context_type"] = "watch_profile"
  enriched["active_data_source"] = "watch_profile"
  enriched["run_origin"] = "watch_profile"
  prior_generation = int(current.get("active_context_generation", 0) or 0)
  enriched["active_context_generation"] = prior_generation + 1
  enriched["lineage_status"] = summarize_lineage_status(enriched).get("lineage_status", "connected")

  return {
    "status": "ok",
    "generation_before": loaded.get("generation"),
    "active_context_generation_before": prior_generation,
    "active_context_generation_after": enriched.get("active_context_generation"),
    "context": enriched,
    "resolved": {
      "theme_id": (resolved.get("theme") or {}).get("theme_id"),
      "watch_profile_id": (resolved.get("watch_profile") or {}).get("watch_profile_id"),
      "search_plan_id": (resolved.get("search_plan") or {}).get("search_plan_id"),
      "signatures_match": resolved.get("signatures_match"),
    },
    "external_api_calls": 0,
    "artifact_rewrites": 0,
  }


def run_apply(*, search_run_id: str, environ: dict[str, str] | None = None) -> dict[str, Any]:
  from services_v9.study_demo_analysis_context import save_active_context_to_storage

  env = dict(environ or os.environ)
  client = _build_client()
  plan = build_normalized_context(search_run_id=search_run_id, environ=env, storage_client=client)
  if plan.get("status") != "ok":
    return plan

  save_result = save_active_context_to_storage(
    dict(plan.get("context", {}) or {}),
    expected_generation=plan.get("generation_before"),
    environ=env,
    storage_client=client,
    selected_by="live_lineage_finalize",
  )
  return {
    **plan,
    "save_result": save_result,
    "applied": save_result.get("status") in {"saved", "unchanged"},
  }


def main() -> int:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--plan", action="store_true")
  parser.add_argument("--apply", action="store_true")
  parser.add_argument("--search-run-id", default=DEFAULT_SEARCH_RUN_ID)
  args = parser.parse_args()

  if args.apply:
    if os.environ.get(APPLY_ENV) != "true":
      print(json.dumps({"status": "blocked", "message": f"Set {APPLY_ENV}=true"}, ensure_ascii=False, indent=2))
      return 2
    result = run_apply(search_run_id=str(args.search_run_id))
  elif args.plan:
    result = build_normalized_context(search_run_id=str(args.search_run_id))
  else:
    print(json.dumps({"status": "blocked", "message": "Use --plan or --apply"}, ensure_ascii=False, indent=2))
    return 2

  preview = dict(result)
  ctx = dict(preview.pop("context", {}) or {})
  preview["context_preview"] = {
    key: ctx.get(key)
    for key in (
      "active_search_run_id",
      "context_type",
      "run_origin",
      "source_theme_id",
      "source_watch_profile_id",
      "source_search_plan_id",
      "lineage_status",
      "active_context_generation",
    )
  }
  print(json.dumps(preview, ensure_ascii=False, indent=2))
  return 0 if result.get("status") == "ok" and (not args.apply or result.get("applied")) else 1


if __name__ == "__main__":
  raise SystemExit(main())
