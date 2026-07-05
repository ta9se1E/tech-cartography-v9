#!/usr/bin/env python3
"""Minimal live Theme → Watch Profile → Search Plan → 5/5/5 search E2E for Study Demo."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
  sys.path.insert(0, str(ROOT / "src"))

from services_v9.study_demo_config import (  # noqa: E402
  STUDY_DEMO_BUCKET_DEFAULT,
  STUDY_DEMO_OPENALEX_SECRET,
  STUDY_DEMO_PROJECT_DEFAULT,
  STUDY_DEMO_TAVILY_SECRET,
)
from services_v9.study_demo_search.execute import execute_three_source_search  # noqa: E402
from services_v9.study_demo_search.plan import build_search_plan_preview  # noqa: E402
from services_v9.study_demo_search.request import StudyDemoSearchRequest, parse_search_request  # noqa: E402
from services_v9.study_demo_search.storage import load_search_run  # noqa: E402
from services_v9.watch_profile_schema import normalize_terms  # noqa: E402

APPLY_ENV = "V9_STUDY_DEMO_THEME_TO_SEARCH_E2E_APPROVED"
SOURCE_RUN_ID_DEFAULT = "study_demo_search_20260705_061319_e973e4c2"
EXPECTED_THEME_NAME = "PAN系炭素繊維用サイジング剤の組成・付与・乾燥条件"
PROVIDER_LIMIT = 5
REQUIRED_USE_JA = [
  "集束性",
  "開繊性",
  "毛羽",
  "耐擦過性",
  "樹脂含浸性",
  "界面接着性",
  "引張強度",
  "引張弾性率",
]
REQUIRED_MATERIAL_JA = ["組成", "付与量", "乾燥条件"]
REQUIRED_EXCLUDE_EN = [
  "paper sizing",
  "starch sizing",
  "activated carbon",
  "carbon black",
  "battery electrode",
  "cement",
  "polyester fiber fabric",
  "antibacterial",
  "ultraviolet",
  "bamboo fiber",
  "TPU PP blend",
  "textile fabric",
]


def _utc_now() -> str:
  return datetime.now(timezone.utc).isoformat()


def _load_secret_version(secret_name: str, version: str = "1") -> str:
  from google.cloud import secretmanager

  client = secretmanager.SecretManagerServiceClient()
  resource = f"projects/{STUDY_DEMO_PROJECT_DEFAULT}/secrets/{secret_name}/versions/{version}"
  response = client.access_secret_version(request={"name": resource})
  return response.payload.data.decode("utf-8")


def build_e2e_environ(*, live: bool = False) -> dict[str, str]:
  env = dict(os.environ)
  env.update(
    {
      "GOOGLE_CLOUD_PROJECT": STUDY_DEMO_PROJECT_DEFAULT,
      "V9_STUDY_DEMO_MODE": "true",
      "V9_STUDY_DEMO_BUCKET": STUDY_DEMO_BUCKET_DEFAULT,
      "V9_STUDY_DEMO_SEARCH_ENABLED": "true",
      "V9_STUDY_DEMO_ENABLE_PATENT_SEARCH": "true",
      "V9_STUDY_DEMO_ENABLE_PAPER_SEARCH": "true",
      "V9_STUDY_DEMO_ENABLE_WEB_SEARCH": "true",
      "V9_STUDY_DEMO_BIGQUERY_DRY_RUN_FIRST": "true",
      "V9_STUDY_DEMO_BIGQUERY_MAX_BYTES_BILLED": "2199023255552",
      "V9_STUDY_DEMO_BIGQUERY_PRICE_PER_TIB_USD": "6.25",
      "V9_STUDY_DEMO_DISABLE_EXTERNAL_EXECUTION": "true",
    }
  )
  if live:
    env["V9_STUDY_DEMO_OPENALEX_API_KEY"] = _load_secret_version(STUDY_DEMO_OPENALEX_SECRET)
    env["V9_STUDY_DEMO_TAVILY_API_KEY"] = _load_secret_version(STUDY_DEMO_TAVILY_SECRET)
  return env


def _load_source_search_request(
  *,
  source_run_id: str,
  environ: Mapping[str, str],
  storage_client: Any | None = None,
) -> dict[str, Any]:
  from services_v9.study_demo_config import get_study_demo_bucket
  from services_v9.study_demo_lineage_storage import load_json_object

  bucket = get_study_demo_bucket(environ)
  path = f"search_runs/{source_run_id}/search_request.json"
  return load_json_object(path, bucket_name=bucket, storage_client=storage_client)


def _build_draft_from_source(
  search_request: Mapping[str, Any],
  *,
  source_run_id: str,
) -> dict[str, Any]:
  from services_v9.study_demo_theme_draft import build_theme_draft_from_temporary_search, complete_draft_review
  from services_v9.study_demo_theme_lineage import default_saved_theme_fixture

  saved = default_saved_theme_fixture()
  draft = build_theme_draft_from_temporary_search(
    search_request,
    search_run_id=source_run_id,
    old_theme_keywords=dict(saved.get("keywords", {}) or {}),
  )
  return complete_draft_review(draft)


def _join_keyword_terms(keywords: Mapping[str, Any], *keys: str) -> str:
  terms: list[str] = []
  for key in keys:
    terms.extend(list(keywords.get(key, []) or []))
  return ", ".join(normalize_terms(terms))


def build_save_payload_from_draft(
  draft: Mapping[str, Any],
  *,
  existing_themes: list[dict[str, Any]],
) -> dict[str, Any]:
  from services_v9.study_demo_theme_draft import build_new_saved_theme_from_draft

  saved = build_new_saved_theme_from_draft(draft, existing_themes=existing_themes)
  saved["name"] = str(draft.get("suggested_theme_name") or draft.get("name") or saved.get("name", ""))
  return saved


def validate_preflight_payload(theme: Mapping[str, Any]) -> dict[str, Any]:
  keywords = dict(theme.get("keywords", {}) or {})
  use_ja = list(keywords.get("application_ja", keywords.get("use_ja", [])) or [])
  material_ja = list(keywords.get("material_process_ja", []) or [])
  exclude_en = [str(item).lower() for item in list(keywords.get("exclude_en", []) or [])]
  missing_use = [term for term in REQUIRED_USE_JA if term not in use_ja]
  missing_material = [term for term in REQUIRED_MATERIAL_JA if term not in material_ja]
  missing_exclude = [term for term in REQUIRED_EXCLUDE_EN if term.lower() not in exclude_en]
  blocking: list[str] = []
  if str(theme.get("name", "")) != EXPECTED_THEME_NAME:
    blocking.append("theme_name_mismatch")
  if int(theme.get("theme_version", 0) or 0) != 1:
    blocking.append("theme_version_not_1")
  if str(theme.get("status", "")) != "saved":
    blocking.append("theme_status_not_saved")
  if str(theme.get("source", "")) != "promoted_from_temporary_search":
    blocking.append("theme_source_invalid")
  if missing_use:
    blocking.append("missing_use_ja")
  if missing_material:
    blocking.append("missing_material_process_ja")
  if missing_exclude:
    blocking.append("missing_exclude_en")
  return {
    "status": "ok" if not blocking else "blocked",
    "blocking_errors": blocking,
    "theme_name": theme.get("name"),
    "theme_version": theme.get("theme_version"),
    "theme_status": theme.get("status"),
    "theme_source": theme.get("source"),
    "source_search_run_id": theme.get("source_search_run_id"),
    "use_ja_count": len(use_ja),
    "material_process_ja_count": len(material_ja),
    "exclude_en_count": len(keywords.get("exclude_en", []) or []),
    "sample_use_ja": use_ja[:4],
    "sample_material_ja": material_ja,
    "sample_exclude_en": list(keywords.get("exclude_en", []) or [])[:4],
    "missing_use_ja": missing_use,
    "missing_material_process_ja": missing_material,
    "missing_exclude_en": missing_exclude,
  }


def build_search_request_payload_from_theme(
  theme: Mapping[str, Any],
  profile: Mapping[str, Any],
  lineage_plan: Mapping[str, Any],
  *,
  provider_limit: int = PROVIDER_LIMIT,
) -> dict[str, Any]:
  keywords = dict(theme.get("keywords", {}) or {})
  year = dict(theme.get("year_range", {}) or {})
  provider = dict(theme.get("provider_settings", {}) or {})
  seeds = list(theme.get("seed_publication_numbers", []) or [])
  return {
    "theme": str(theme.get("description", "") or theme.get("name", "")),
    "keywords_ja": _join_keyword_terms(keywords, "core_ja", "application_ja", "use_ja", "material_process_ja"),
    "keywords_en": _join_keyword_terms(keywords, "core_en", "application_en", "use_en", "material_process_en"),
    "exact_phrase": str(theme.get("exact_phrase", "") or ""),
    "exclude_keywords": _join_keyword_terms(keywords, "exclude_en", "exclude_ja"),
    "seed_patent": seeds[0] if seeds else "",
    "year_start": str(year.get("start", "") or ""),
    "year_end": str(year.get("end", "") or ""),
    "enable_patent": bool(provider.get("enable_patent", True)),
    "enable_paper": bool(provider.get("enable_paper", True)),
    "enable_web": bool(provider.get("enable_web", True)),
    "patent_display_limit": provider_limit,
    "paper_display_limit": provider_limit,
    "web_max_results": provider_limit,
    "run_origin": "watch_profile",
    "source_theme_id": theme.get("theme_id"),
    "source_theme_version": theme.get("theme_version"),
    "source_theme_signature": theme.get("theme_signature"),
    "source_watch_profile_id": profile.get("watch_profile_id"),
    "source_watch_profile_version": profile.get("watch_profile_version"),
    "source_watch_profile_signature": profile.get("watch_profile_signature"),
    "source_search_plan_id": lineage_plan.get("search_plan_id"),
    "source_search_plan_version": lineage_plan.get("search_plan_version"),
    "source_search_plan_signature": lineage_plan.get("search_plan_signature"),
  }


def run_preflight(*, source_run_id: str, environ: Mapping[str, str]) -> dict[str, Any]:
  from services_v9.study_demo_theme_lineage import default_saved_theme_fixture

  search_request = _load_source_search_request(source_run_id=source_run_id, environ=environ)
  draft = _build_draft_from_source(search_request, source_run_id=source_run_id)
  existing = [dict(default_saved_theme_fixture())]
  theme = build_save_payload_from_draft(draft, existing_themes=existing)
  preflight = validate_preflight_payload(theme)
  return {
    **preflight,
    "source_run_id": source_run_id,
    "description_length": len(str(theme.get("description", "") or "")),
    "created_from_draft_id": theme.get("created_from_draft_id"),
    "application_scope": theme.get("application_scope"),
    "cloud_writes": 0,
    "external_api_calls": 0,
  }


def _mark_aborted(
  *,
  bucket_name: str,
  paths: list[str],
  reason: str,
  storage_client: Any,
) -> None:
  for path in paths:
    try:
      blob = storage_client.bucket(bucket_name).blob(path)
      if not blob.exists():
        continue
      payload = json.loads(blob.download_as_bytes().decode("utf-8"))
      payload["status"] = "aborted"
      payload["abort_reason"] = reason
      payload["aborted_at"] = _utc_now()
      blob.upload_from_string(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", content_type="application/json")
    except Exception:
      continue


def run_apply(*, source_run_id: str, environ: Mapping[str, str]) -> dict[str, Any]:
  from google.cloud import storage

  from services_v9.study_demo_analysis_context import build_active_context_from_run, load_active_context_from_storage, save_active_context_to_storage
  from services_v9.study_demo_config import get_study_demo_bucket
  from services_v9.study_demo_downstream import build_downstream_bundle
  from services_v9.study_demo_lineage_storage import (
    load_json_object,
    save_search_plan_lineage_object,
    save_theme_lineage_object,
    save_watch_profile_lineage_object,
    search_plan_latest_path,
    theme_latest_path,
    watch_profile_latest_path,
  )
  from services_v9.study_demo_theme_lineage import (
    build_search_plan_from_watch_profile,
    build_search_plan_preview_summary,
    build_search_run_lineage,
    build_watch_profile_from_theme,
    compute_search_plan_signature,
    compute_theme_signature,
    compute_watch_profile_signature,
    default_saved_theme_fixture,
    enrich_active_context_with_lineage,
    summarize_lineage_status,
    validate_theme_lineage,
  )

  bucket_name = get_study_demo_bucket(environ)
  client = storage.Client()
  saved_paths: list[str] = []
  rollback_active_run_id = source_run_id

  try:
    prior_ctx = load_active_context_from_storage(environ=environ, storage_client=client)
    prior_generation = int((prior_ctx.get("context") or {}).get("active_context_generation") or 0)

    search_request = _load_source_search_request(source_run_id=source_run_id, environ=environ, storage_client=client)
    draft = _build_draft_from_source(search_request, source_run_id=source_run_id)
    existing = [dict(default_saved_theme_fixture())]
    theme = build_save_payload_from_draft(draft, existing_themes=existing)
    preflight = validate_preflight_payload(theme)
    if preflight.get("status") != "ok":
      return {"status": "blocked", "stage": "preflight", "preflight": preflight}

    theme_save = save_theme_lineage_object(theme, environ=environ, storage_client=client)
    saved_paths.extend([theme_save["version_path"], theme_save["latest_path"]])
    read_theme = load_json_object(theme_latest_path(str(theme.get("theme_id", ""))), bucket_name=bucket_name, storage_client=client)
    if compute_theme_signature(read_theme) != compute_theme_signature(theme):
      raise RuntimeError("theme signature mismatch on read-back")

    profile = build_watch_profile_from_theme(theme, generated_by="theme_to_search_e2e")
    profile["status"] = "saved"
    profile_save = save_watch_profile_lineage_object(profile, environ=environ, storage_client=client)
    saved_paths.extend([profile_save["version_path"], profile_save["latest_path"]])
    read_profile = load_json_object(
      watch_profile_latest_path(str(profile.get("watch_profile_id", ""))),
      bucket_name=bucket_name,
      storage_client=client,
    )
    if compute_watch_profile_signature(read_profile) != compute_watch_profile_signature(profile):
      raise RuntimeError("watch profile signature mismatch on read-back")

    lineage_plan = build_search_plan_from_watch_profile(
      profile,
      theme,
      provider_limits={"patent": PROVIDER_LIMIT, "paper": PROVIDER_LIMIT, "web": PROVIDER_LIMIT},
      external_execution_allowed=True,
    )
    lineage_plan["validation_status"] = "ready_for_execution"
    lineage_plan["email_enabled"] = False
    lineage_plan["scheduler_enabled"] = False
    plan_save = save_search_plan_lineage_object(lineage_plan, environ=environ, storage_client=client)
    saved_paths.extend([plan_save["version_path"], plan_save["latest_path"]])
    read_plan = load_json_object(
      search_plan_latest_path(str(lineage_plan.get("search_plan_id", ""))),
      bucket_name=bucket_name,
      storage_client=client,
    )
    if compute_search_plan_signature(read_plan) != compute_search_plan_signature(lineage_plan):
      raise RuntimeError("search plan signature mismatch on read-back")

    request_payload = build_search_request_payload_from_theme(theme, profile, lineage_plan, provider_limit=PROVIDER_LIMIT)
    request = parse_search_request(request_payload)
    exec_plan = build_search_plan_preview(request, environ=environ)
    if exec_plan.get("status") != "plan":
      return {"status": "blocked", "stage": "execution_plan", "plan": exec_plan}

    summary = dict(exec_plan.get("summary", {}) or {})
    summary.update(request_payload)
    exec_plan["summary"] = summary
    exec_plan["lineage_plan_id"] = lineage_plan.get("search_plan_id")
    exec_plan["lineage_plan_signature"] = lineage_plan.get("search_plan_signature")
    exec_plan["source_theme_id"] = theme.get("theme_id")
    exec_plan["source_watch_profile_id"] = profile.get("watch_profile_id")

    result = execute_three_source_search(
      request,
      plan=exec_plan,
      confirmed=True,
      executed_plan_ids=set(),
      environ=environ,
      storage_client=client,
    )
    if str(result.get("status", "")) == "blocked":
      return {"status": "blocked", "stage": "live_search", "result": result}

    provider_status = dict(result.get("provider_status", {}) or {})
    successes = [name for name, item in provider_status.items() if item.get("status") == "success"]
    if not successes:
      return {"status": "failed", "stage": "live_search", "message": "all providers failed", "provider_status": provider_status}

    new_run_id = str(result.get("search_run_id", "") or "")
    loaded = load_search_run(new_run_id, environ=environ, storage_client=client)
    artifacts = dict(loaded.get("artifacts", {}) or {})
    ctx = build_active_context_from_run(
      search_run_id=new_run_id,
      artifacts=artifacts,
      bucket_name=bucket_name,
      selected_by="theme_to_search_e2e",
    )
    run_lineage = build_search_run_lineage(
      search_run_id=new_run_id,
      search_plan=lineage_plan,
      theme=theme,
      watch_profile=profile,
      run_origin="watch_profile",
    )
    search_request_saved = dict(artifacts.get("search_request.json", {}) or {})
    search_request_saved.update(request_payload)
    artifacts["search_request.json"] = search_request_saved
    enriched = enrich_active_context_with_lineage(ctx, search_request=search_request_saved, run_lineage=run_lineage)
    enriched["active_context_generation"] = prior_generation + 1
    enriched["context_type"] = "watch_profile"
    enriched["active_data_source"] = "temporary_search"
    enriched["theme"] = str(theme.get("name", ""))

    lineage = validate_theme_lineage(
      {
        "theme": theme,
        "watch_profile": profile,
        "search_plan": lineage_plan,
        "search_run": {"search_run_id": new_run_id, **run_lineage},
      }
    )
    if lineage:
      return {"status": "failed", "stage": "lineage_validation", "errors": lineage}

    save_ctx = save_active_context_to_storage(
      enriched,
      expected_generation=prior_ctx.get("generation") if prior_ctx.get("status") == "ok" else 0,
      environ=environ,
      storage_client=client,
      selected_by="theme_to_search_e2e",
    )
    if save_ctx.get("status") not in {"saved", "unchanged"}:
      return {"status": "failed", "stage": "active_context", "save_context": save_ctx}

    integrated = dict(result.get("integrated_signals", {}) or {})
    patent_rows = len(list(dict(result.get("patent_results", {}) or {}).get("rows", []) or []))
    paper_rows = len(list(dict(result.get("paper_results", {}) or {}).get("rows", []) or []))
    web_rows = len(list(dict(result.get("web_results", {}) or {}).get("rows", []) or []))
    plan_summary = build_search_plan_preview_summary(lineage_plan)
    downstream = build_downstream_bundle(enriched, storage_client=client, environ=environ)

    return {
      "status": "ok",
      "source_run_id": source_run_id,
      "new_search_run_id": new_run_id,
      "theme_id": theme.get("theme_id"),
      "theme_version": theme.get("theme_version"),
      "theme_signature": theme.get("theme_signature"),
      "watch_profile_id": profile.get("watch_profile_id"),
      "watch_profile_signature": profile.get("watch_profile_signature"),
      "search_plan_id": lineage_plan.get("search_plan_id"),
      "search_plan_signature": lineage_plan.get("search_plan_signature"),
      "provider_limits": dict(lineage_plan.get("provider_limits", {}) or {}),
      "plan_query_summary": {
        "patent": plan_summary.get("patent_query_summary"),
        "paper": plan_summary.get("paper_query_summary"),
        "web": plan_summary.get("web_query_summary"),
        "exclude_keywords": plan_summary.get("exclude_keywords", [])[:6],
      },
      "live_search_executions": 1,
      "patent_result_count": patent_rows,
      "paper_result_count": paper_rows,
      "web_result_count": web_rows,
      "integrated_count": int(integrated.get("ranked_count", 0) or len(integrated.get("signals", []) or [])),
      "provider_status": provider_status,
      "cost_metadata": dict(result.get("cost_estimate", {}) or exec_plan.get("cost_estimate", {}) or {}),
      "usage_metrics": dict(result.get("usage_metrics", {}) or {}),
      "lineage_status": summarize_lineage_status(enriched).get("lineage_status"),
      "run_origin": enriched.get("run_origin"),
      "active_context_generation": enriched.get("active_context_generation"),
      "downstream_tier_count": len(dict(downstream.get("tier_counts", {}) or {})),
      "proposal_count": int(dict(downstream.get("review_proposals", {}).get("summary", {})).get("proposal_count", 0)),
      "rollback_active_run_id": rollback_active_run_id,
      "old_theme_preserved": str(existing[0].get("theme_id", "")),
      "production_resources_modified": False,
      "email_sent": False,
    }
  except Exception as exc:  # noqa: BLE001
    _mark_aborted(bucket_name=bucket_name, paths=saved_paths, reason=str(exc), storage_client=client)
    return {"status": "failed", "stage": "exception", "message": str(exc), "saved_paths": saved_paths}


def main() -> int:
  parser = argparse.ArgumentParser()
  parser.add_argument("--preflight", action="store_true")
  parser.add_argument("--apply", action="store_true")
  parser.add_argument("--source-run-id", default=SOURCE_RUN_ID_DEFAULT)
  args = parser.parse_args()

  if args.apply:
    if os.environ.get(APPLY_ENV, "").lower() != "true":
      print(json.dumps({"status": "blocked", "message": f"requires {APPLY_ENV}=true"}, ensure_ascii=False, indent=2))
      return 2
    environ = build_e2e_environ(live=True)
    try:
      payload = run_apply(source_run_id=str(args.source_run_id), environ=environ)
    finally:
      environ.pop("V9_STUDY_DEMO_OPENALEX_API_KEY", None)
      environ.pop("V9_STUDY_DEMO_TAVILY_API_KEY", None)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("status") == "ok" else 1

  if args.preflight:
    environ = build_e2e_environ(live=False)
    payload = run_preflight(source_run_id=str(args.source_run_id), environ=environ)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("status") == "ok" else 1

  parser.error("specify --preflight or --apply")
  return 2


if __name__ == "__main__":
  raise SystemExit(main())
