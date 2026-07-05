"""Theme → Watch Profile → Search Plan → Run lineage for Study Demo."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from services_v9.watch_profile_schema import (
  KEYWORD_GROUPS,
  default_bilingual_watch_profile,
  migrate_watch_profile,
  normalize_terms,
  parse_publication_numbers,
  parse_terms,
)

THEME_SCHEMA_VERSION = 1
WATCH_PROFILE_LINEAGE_SCHEMA_VERSION = 1
SEARCH_PLAN_LINEAGE_SCHEMA_VERSION = 1

RUN_ORIGINS = frozenset(
  {
    "watch_profile",
    "temporary_search",
    "uploaded_csv",
    "uploaded_json",
    "stored_artifact",
    "legacy_demo",
  }
)

LINEAGE_STATUSES = frozenset(
  {
    "connected",
    "temporary_unconnected",
    "partial",
    "mismatch",
    "unavailable",
  }
)

SIGNATURE_EXCLUDE_KEYS = frozenset(
  {
    "created_at",
    "updated_at",
    "generated_at",
    "theme_id",
    "theme_version",
    "theme_signature",
    "watch_profile_id",
    "watch_profile_version",
    "watch_profile_signature",
    "search_plan_id",
    "search_plan_version",
    "search_plan_signature",
    "search_run_id",
    "run_origin",
    "active_context_generation",
    "lineage_status",
    "theme_lineage_ref",
    "status",
    "generated_by",
    "source_search_run_id",
    "temporary_search_request_id",
    "validation_messages",
    "validation_status",
    "email_enabled",
    "scheduler_enabled",
    "estimated_cost_usd",
    "audit_metadata",
    "proposal_set_id",
    "draft_id",
  }
)

THEMES_PREFIX = "themes/"
DEFAULT_SAVED_THEME_NAME = "PAN系炭素繊維前駆体の表面・内部欠陥制御"


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).isoformat()


def _short(value: str, length: int = 8) -> str:
  text = str(value or "")
  return text[:length] if text else ""


def _sorted_json(value: Any) -> Any:
  if isinstance(value, Mapping):
    return {key: _sorted_json(value[key]) for key in sorted(value.keys())}
  if isinstance(value, list):
    return [_sorted_json(item) for item in value]
  return value


def _canonical_payload(payload: Mapping[str, Any], *, exclude: frozenset[str] | None = None) -> dict[str, Any]:
  excluded = SIGNATURE_EXCLUDE_KEYS if exclude is None else exclude
  cleaned: dict[str, Any] = {}
  for key, value in dict(payload).items():
    if key in excluded:
      continue
    cleaned[key] = _sorted_json(value)
  return cleaned


def compute_content_signature(payload: Mapping[str, Any], *, exclude: frozenset[str] | None = None) -> str:
  canonical = _canonical_payload(payload, exclude=exclude)
  blob = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
  return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def new_theme_id() -> str:
  return f"theme_{uuid.uuid4().hex[:12]}"


def new_watch_profile_id(theme_id: str) -> str:
  safe = re.sub(r"[^A-Za-z0-9._-]+", "_", str(theme_id or ""))
  return f"wp_{safe}"


def new_search_plan_id(watch_profile_id: str) -> str:
  safe = re.sub(r"[^A-Za-z0-9._-]+", "_", str(watch_profile_id or ""))
  return f"plan_{safe}"


def empty_keywords_block() -> dict[str, list[str]]:
  return {key: [] for key in KEYWORD_GROUPS}


def canonicalize_theme_payload(raw: Mapping[str, Any]) -> dict[str, Any]:
  keywords_raw = dict(raw.get("keywords", {}) or {})
  keywords = empty_keywords_block()
  for key in KEYWORD_GROUPS:
    if isinstance(keywords_raw.get(key), list):
      keywords[key] = normalize_terms(list(keywords_raw.get(key, [])))
    elif isinstance(keywords_raw.get(key), str):
      keywords[key] = parse_terms(str(keywords_raw.get(key, "")))

  seeds = raw.get("seed_publication_numbers", raw.get("seed_publications", []))
  candidates = raw.get("additional_candidate_publication_numbers", raw.get("candidate_publications", []))
  if isinstance(seeds, str):
    seeds = parse_publication_numbers(seeds)
  if isinstance(candidates, str):
    candidates = parse_publication_numbers(candidates)

  return {
    "schema_version": THEME_SCHEMA_VERSION,
    "name": str(raw.get("name", raw.get("theme_name", "")) or "").strip(),
    "description": str(raw.get("description", raw.get("theme_description", "")) or "").strip(),
    "keywords": keywords,
    "seed_publication_numbers": normalize_terms([str(item) for item in list(seeds or [])]),
    "additional_candidate_publication_numbers": normalize_terms([str(item) for item in list(candidates or [])]),
    "status": str(raw.get("status", "draft") or "draft"),
    "source": str(raw.get("source", "manual") or "manual"),
    "source_search_run_id": raw.get("source_search_run_id"),
  }


def compute_theme_signature(theme: Mapping[str, Any]) -> str:
  return compute_content_signature(canonicalize_theme_payload(theme))


def build_theme_record(
  raw: Mapping[str, Any],
  *,
  theme_id: str | None = None,
  theme_version: int = 1,
  created_at: str | None = None,
) -> dict[str, Any]:
  canonical = canonicalize_theme_payload(raw)
  record = dict(canonical)
  record["theme_id"] = str(theme_id or raw.get("theme_id") or new_theme_id())
  record["theme_version"] = int(theme_version or raw.get("theme_version", 1) or 1)
  record["theme_signature"] = compute_theme_signature(record)
  record["created_at"] = str(created_at or raw.get("created_at") or _utc_now_iso())
  record["updated_at"] = _utc_now_iso()
  if record["source"] not in {"manual", "promoted_from_temporary_search"}:
    record["source"] = "manual"
  if record["status"] not in {"draft", "saved", "archived"}:
    record["status"] = "draft"
  return record


def theme_object_paths(theme_id: str, theme_version: int) -> tuple[str, str]:
  safe_id = re.sub(r"[^A-Za-z0-9._-]+", "_", str(theme_id or ""))
  version_path = f"{THEMES_PREFIX}{safe_id}/versions/v{int(theme_version)}.json"
  latest_path = f"{THEMES_PREFIX}{safe_id}/latest.json"
  return version_path, latest_path


def theme_from_form_widgets(form: Mapping[str, Any]) -> dict[str, Any]:
  return build_theme_record(
    {
      "name": form.get("theme_name", form.get("name", "")),
      "description": form.get("theme_description", form.get("description", "")),
      "keywords": {
        "core_en": parse_terms(str(form.get("core_en", form.get("ui_core_en_input", "")) or "")),
        "core_ja": parse_terms(str(form.get("core_ja", form.get("ui_core_ja_input", "")) or "")),
        "use_en": parse_terms(str(form.get("application_en", form.get("ui_application_en_input", "")) or "")),
        "use_ja": parse_terms(str(form.get("application_ja", form.get("ui_application_ja_input", "")) or "")),
        "material_process_en": parse_terms(str(form.get("material_process_en", form.get("ui_material_process_en_input", "")) or "")),
        "material_process_ja": parse_terms(str(form.get("material_process_ja", form.get("ui_material_process_ja_input", "")) or "")),
        "exclude_en": parse_terms(str(form.get("exclude_en", form.get("ui_exclude_en_input", "")) or "")),
        "exclude_ja": parse_terms(str(form.get("exclude_ja", form.get("ui_exclude_ja_input", "")) or "")),
      },
      "seed_publication_numbers": parse_publication_numbers(str(form.get("seed_publications", form.get("ui_seed_publications_input", "")) or "")),
      "additional_candidate_publication_numbers": parse_publication_numbers(
        str(form.get("candidate_publications", form.get("ui_candidate_publications_input", "")) or "")
      ),
      "status": form.get("status", "draft"),
      "source": form.get("source", "manual"),
      "source_search_run_id": form.get("source_search_run_id"),
      "theme_id": form.get("theme_id"),
      "theme_version": form.get("theme_version", 1),
    }
  )


def theme_dirty(saved: Mapping[str, Any] | None, candidate: Mapping[str, Any]) -> bool:
  if not saved:
    return bool(candidate)
  return compute_theme_signature(saved) != compute_theme_signature(candidate)


def build_watch_profile_from_theme(theme: Mapping[str, Any], *, generated_by: str = "study_demo_user") -> dict[str, Any]:
  keywords = dict(theme.get("keywords", {}) or {})
  profile = migrate_watch_profile(default_bilingual_watch_profile())
  profile["theme_name"] = str(theme.get("name", "") or "")
  profile["theme_description"] = str(theme.get("description", "") or "")
  profile["keywords"] = {
    "core_en": list(keywords.get("core_en", [])),
    "core_ja": list(keywords.get("core_ja", [])),
    "application_en": list(keywords.get("use_en", keywords.get("application_en", []))),
    "application_ja": list(keywords.get("use_ja", keywords.get("application_ja", []))),
    "material_process_en": list(keywords.get("material_process_en", [])),
    "material_process_ja": list(keywords.get("material_process_ja", [])),
    "exclude_en": list(keywords.get("exclude_en", [])),
    "exclude_ja": list(keywords.get("exclude_ja", [])),
  }
  profile["seed_publications"] = list(theme.get("seed_publication_numbers", []) or [])
  profile["candidate_publications"] = list(theme.get("additional_candidate_publication_numbers", []) or [])
  theme_id = str(theme.get("theme_id", "") or "")
  profile_version = int(theme.get("watch_profile_version", 1) or 1)
  profile["watch_profile_id"] = str(theme.get("watch_profile_id", "") or new_watch_profile_id(theme_id))
  profile["watch_profile_version"] = profile_version
  profile["source_theme_id"] = theme_id
  profile["source_theme_version"] = int(theme.get("theme_version", 1) or 1)
  profile["source_theme_signature"] = str(theme.get("theme_signature", "") or compute_theme_signature(theme))
  profile["generated_at"] = _utc_now_iso()
  profile["generated_by"] = generated_by
  profile["status"] = "generated_from_theme"
  profile["watch_profile_signature"] = compute_watch_profile_signature(profile)
  return profile


def compute_watch_profile_signature(profile: Mapping[str, Any]) -> str:
  return compute_content_signature(profile)


def _collect_include_keywords(profile: Mapping[str, Any]) -> list[str]:
  keywords = dict(profile.get("keywords", {}) or {})
  terms: list[str] = []
  for key in ("core_en", "core_ja", "application_en", "application_ja", "material_process_en", "material_process_ja"):
    terms.extend(normalize_terms(list(keywords.get(key, []) or [])))
  return normalize_terms(terms)


def _collect_exclude_keywords(profile: Mapping[str, Any]) -> list[str]:
  keywords = dict(profile.get("keywords", {}) or {})
  return normalize_terms(list(keywords.get("exclude_en", []) or []) + list(keywords.get("exclude_ja", []) or []))


def build_search_plan_from_watch_profile(
  profile: Mapping[str, Any],
  theme: Mapping[str, Any],
  *,
  provider_limits: Mapping[str, int] | None = None,
  external_execution_allowed: bool = False,
) -> dict[str, Any]:
  limits = {"patent": 50, "paper": 50, "web": 10}
  limits.update({key: int(value) for key, value in dict(provider_limits or {}).items()})
  include_keywords = _collect_include_keywords(profile)
  exclude_keywords = _collect_exclude_keywords(profile)
  exact_phrases = normalize_terms(list(profile.get("exact_phrases", []) or []))
  seeds = normalize_terms(list(profile.get("seed_publications", []) or []))
  year_start = str(profile.get("year_start", "") or "")
  year_end = str(profile.get("year_end", "") or "")

  provider_plans: dict[str, Any] = {}
  for provider in ("patent", "paper", "web"):
    provider_plans[provider] = {
      "query_groups": [include_keywords[:8]] if include_keywords else [],
      "required_terms": include_keywords[:5],
      "optional_terms": include_keywords[5:15],
      "exclusions": exclude_keywords,
      "max_results": int(limits.get(provider, 50)),
      "language": "ja" if provider != "patent" else "mixed",
      "query_text_summary": " / ".join(include_keywords[:6]) or str(theme.get("name", "")),
    }

  estimated_query_count = sum(len(plan.get("query_groups", []) or []) for plan in provider_plans.values())
  watch_profile_id = str(profile.get("watch_profile_id", "") or "")
  plan = {
    "schema_version": SEARCH_PLAN_LINEAGE_SCHEMA_VERSION,
    "search_plan_id": str(profile.get("search_plan_id", "") or new_search_plan_id(watch_profile_id)),
    "search_plan_version": int(profile.get("search_plan_version", 1) or 1),
    "source_watch_profile_id": watch_profile_id,
    "source_watch_profile_version": int(profile.get("watch_profile_version", 1) or 1),
    "source_watch_profile_signature": str(profile.get("watch_profile_signature", "") or compute_watch_profile_signature(profile)),
    "source_theme_id": str(theme.get("theme_id", profile.get("source_theme_id", "")) or ""),
    "source_theme_version": int(theme.get("theme_version", profile.get("source_theme_version", 1)) or 1),
    "source_theme_signature": str(theme.get("theme_signature", profile.get("source_theme_signature", "")) or compute_theme_signature(theme)),
    "generated_at": _utc_now_iso(),
    "provider_plans": provider_plans,
    "exact_phrases": exact_phrases,
    "include_keywords": include_keywords,
    "exclude_keywords": exclude_keywords,
    "seed_publications": seeds,
    "year_range": {"start": year_start, "end": year_end},
    "provider_limits": limits,
    "estimated_query_count": estimated_query_count,
    "external_execution_allowed": bool(external_execution_allowed),
    "validation_status": "ready_for_preview",
    "validation_messages": [],
  }
  plan["search_plan_signature"] = compute_search_plan_signature(plan)
  return plan


def compute_search_plan_signature(plan: Mapping[str, Any]) -> str:
  return compute_content_signature(plan)


def build_search_plan_preview_summary(plan: Mapping[str, Any]) -> dict[str, Any]:
  provider_plans = dict(plan.get("provider_plans", {}) or {})
  return {
    "search_plan_id": plan.get("search_plan_id"),
    "search_plan_version": plan.get("search_plan_version"),
    "search_plan_signature_short": _short(str(plan.get("search_plan_signature", "")), 8),
    "source_theme_id": plan.get("source_theme_id"),
    "source_theme_version": plan.get("source_theme_version"),
    "source_theme_signature_short": _short(str(plan.get("source_theme_signature", "")), 8),
    "source_watch_profile_id": plan.get("source_watch_profile_id"),
    "source_watch_profile_version": plan.get("source_watch_profile_version"),
    "source_watch_profile_signature_short": _short(str(plan.get("source_watch_profile_signature", "")), 8),
    "patent_query_summary": dict(provider_plans.get("patent", {}) or {}).get("query_text_summary", ""),
    "paper_query_summary": dict(provider_plans.get("paper", {}) or {}).get("query_text_summary", ""),
    "web_query_summary": dict(provider_plans.get("web", {}) or {}).get("query_text_summary", ""),
    "exact_phrases": list(plan.get("exact_phrases", []) or []),
    "exclude_keywords": list(plan.get("exclude_keywords", []) or []),
    "year_range": dict(plan.get("year_range", {}) or {}),
    "seed_publications": list(plan.get("seed_publications", []) or []),
    "provider_limits": dict(plan.get("provider_limits", {}) or {}),
    "estimated_query_count": int(plan.get("estimated_query_count", 0) or 0),
    "external_execution_allowed": bool(plan.get("external_execution_allowed", False)),
    "validation_status": plan.get("validation_status"),
    "validation_messages": list(plan.get("validation_messages", []) or []),
  }


def infer_run_origin(search_request: Mapping[str, Any]) -> str:
  explicit = str(search_request.get("run_origin", "") or "").strip()
  if explicit in RUN_ORIGINS:
    return explicit
  if search_request.get("source_search_plan_id") or search_request.get("source_watch_profile_id"):
    return "watch_profile"
  if search_request.get("temporary_search_request_id") is not None or search_request.get("study_demo_temporary_search"):
    return "temporary_search"
  mode = str(search_request.get("data_source_mode", "") or "")
  if mode == "temporary_search":
    return "temporary_search"
  if mode in {"csv", "uploaded_csv"}:
    return "uploaded_csv"
  if mode in {"json", "uploaded_json"}:
    return "uploaded_json"
  if mode == "legacy_demo":
    return "legacy_demo"
  if mode == "retrieval_saved":
    return "stored_artifact"
  if any(search_request.get(key) for key in ("theme", "keywords_ja", "keywords_en")):
    return "temporary_search"
  return "legacy_demo"


def build_search_run_lineage(
  *,
  search_run_id: str,
  search_plan: Mapping[str, Any] | None,
  theme: Mapping[str, Any] | None,
  watch_profile: Mapping[str, Any] | None,
  run_origin: str,
  temporary_search_request_id: str | None = None,
  search_request: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
  lineage = {
    "search_run_id": search_run_id,
    "run_origin": run_origin,
    "temporary_search_request_id": temporary_search_request_id,
    "source_theme_id": None,
    "source_theme_version": None,
    "source_theme_signature": None,
    "source_watch_profile_id": None,
    "source_watch_profile_version": None,
    "source_watch_profile_signature": None,
    "source_search_plan_id": None,
    "source_search_plan_version": None,
    "source_search_plan_signature": None,
  }
  request = dict(search_request or {})
  if run_origin == "watch_profile" and request.get("source_theme_id"):
    from services_v9.study_demo_live_lineage_loader import lineage_refs_from_search_request

    lineage.update(lineage_refs_from_search_request(request))
  if run_origin == "watch_profile" and search_plan:
    lineage.update(
      {
        "source_theme_id": search_plan.get("source_theme_id"),
        "source_theme_version": search_plan.get("source_theme_version"),
        "source_theme_signature": search_plan.get("source_theme_signature"),
        "source_watch_profile_id": search_plan.get("source_watch_profile_id"),
        "source_watch_profile_version": search_plan.get("source_watch_profile_version"),
        "source_watch_profile_signature": search_plan.get("source_watch_profile_signature"),
        "source_search_plan_id": search_plan.get("search_plan_id"),
        "source_search_plan_version": search_plan.get("search_plan_version"),
        "source_search_plan_signature": search_plan.get("search_plan_signature"),
      }
    )
  elif theme and run_origin == "watch_profile":
    lineage.update(
      {
        "source_theme_id": theme.get("theme_id"),
        "source_theme_version": theme.get("theme_version"),
        "source_theme_signature": theme.get("theme_signature"),
      }
    )
    if watch_profile:
      lineage.update(
        {
          "source_watch_profile_id": watch_profile.get("watch_profile_id"),
          "source_watch_profile_version": watch_profile.get("watch_profile_version"),
          "source_watch_profile_signature": watch_profile.get("watch_profile_signature"),
        }
      )
  return lineage


def enrich_active_context_with_lineage(
  context: Mapping[str, Any],
  *,
  search_request: Mapping[str, Any] | None = None,
  run_lineage: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
  enriched = dict(context)
  preserved = {
    key: enriched.get(key)
    for key in (
      "source_theme_id",
      "source_theme_version",
      "source_theme_signature",
      "source_watch_profile_id",
      "source_watch_profile_version",
      "source_watch_profile_signature",
      "source_search_plan_id",
      "source_search_plan_version",
      "source_search_plan_signature",
      "run_origin",
      "context_type",
      "active_data_source",
    )
    if enriched.get(key) not in (None, "")
  }
  request = dict(search_request or {})
  lineage = dict(run_lineage or {})
  if not lineage and request:
    run_origin = infer_run_origin(request)
    lineage = build_search_run_lineage(
      search_run_id=str(context.get("active_search_run_id", "") or ""),
      search_plan=request if request.get("search_plan_id") else None,
      theme=None,
      watch_profile=None,
      run_origin=run_origin,
      temporary_search_request_id=str(request.get("temporary_search_request_id", "") or "") or None,
      search_request=request,
    )
    if request.get("lineage"):
      lineage = {**lineage, **dict(request.get("lineage", {}) or {})}

  run_origin = str(
    lineage.get("run_origin")
    or preserved.get("run_origin")
    or request.get("run_origin")
    or infer_run_origin(request)
    or enriched.get("run_origin")
    or "temporary_search"
  )
  enriched["run_origin"] = run_origin
  if run_origin == "watch_profile":
    enriched["context_type"] = "watch_profile"
    enriched["active_data_source"] = "watch_profile"
  for key in (
    "source_theme_id",
    "source_theme_version",
    "source_theme_signature",
    "source_watch_profile_id",
    "source_watch_profile_version",
    "source_watch_profile_signature",
    "source_search_plan_id",
    "source_search_plan_version",
    "source_search_plan_signature",
  ):
    value = lineage.get(key)
    if value in (None, "") and preserved.get(key) not in (None, ""):
      value = preserved.get(key)
    if value not in (None, ""):
      enriched[key] = value
  enriched["theme_lineage_ref"] = {
    "theme_id": enriched.get("source_theme_id"),
    "theme_version": enriched.get("source_theme_version"),
    "watch_profile_version": enriched.get("source_watch_profile_version"),
    "search_plan_id": enriched.get("source_search_plan_id"),
  }
  enriched["lineage_status"] = summarize_lineage_status(enriched).get("lineage_status", "unavailable")
  return enriched


def build_theme_lineage(
  *,
  theme: Mapping[str, Any] | None,
  watch_profile: Mapping[str, Any] | None,
  search_plan: Mapping[str, Any] | None,
  search_run: Mapping[str, Any] | None,
) -> dict[str, Any]:
  return {
    "theme": dict(theme or {}),
    "watch_profile": dict(watch_profile or {}),
    "search_plan": dict(search_plan or {}),
    "search_run": dict(search_run or {}),
  }


def validate_theme_lineage(lineage: Mapping[str, Any]) -> list[str]:
  errors: list[str] = []
  theme = dict(lineage.get("theme", {}) or {})
  profile = dict(lineage.get("watch_profile", {}) or {})
  plan = dict(lineage.get("search_plan", {}) or {})
  run = dict(lineage.get("search_run", {}) or {})
  if theme and profile:
    if str(profile.get("source_theme_signature", "")) and str(theme.get("theme_signature", "")):
      if profile.get("source_theme_signature") != theme.get("theme_signature"):
        errors.append("watch_profile theme signature mismatch")
  if profile and plan:
    if str(plan.get("source_watch_profile_signature", "")) and str(profile.get("watch_profile_signature", "")):
      if plan.get("source_watch_profile_signature") != profile.get("watch_profile_signature"):
        errors.append("search_plan watch_profile signature mismatch")
  if plan and run:
    run_origin = str(run.get("run_origin", "") or "")
    if run_origin == "watch_profile":
      if str(run.get("source_search_plan_signature", "")) and str(plan.get("search_plan_signature", "")):
        if run.get("source_search_plan_signature") != plan.get("search_plan_signature"):
          errors.append("search_run search_plan signature mismatch")
  blob = json.dumps(lineage, ensure_ascii=False).lower()
  if any(token in blob for token in ("password", "api_key", "secret", "cookie")):
    errors.append("forbidden secret in lineage")
  return errors


def compare_lineage(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
  fields = (
    "source_theme_signature",
    "source_watch_profile_signature",
    "source_search_plan_signature",
  )
  mismatches: list[str] = []
  for field in fields:
    if str(left.get(field, "") or "") and str(right.get(field, "") or ""):
      if left.get(field) != right.get(field):
        mismatches.append(field)
  return {"matches": not mismatches, "mismatched_fields": mismatches}


def summarize_lineage_status(context: Mapping[str, Any]) -> dict[str, Any]:
  run_origin = str(context.get("run_origin", "") or infer_run_origin(context))
  if run_origin == "temporary_search":
    return {
      "lineage_status": "temporary_unconnected",
      "creation_path_label": "一時キーワード検索",
      "watch_profile_connection": "未接続",
      "standard_theme_name": DEFAULT_SAVED_THEME_NAME,
      "active_run_theme": str(context.get("theme", "") or ""),
    }
  required = (
    context.get("source_theme_id"),
    context.get("source_watch_profile_id"),
    context.get("source_search_plan_id"),
  )
  if run_origin == "watch_profile":
    if all(required):
      mismatches = compare_lineage(context, context).get("mismatched_fields", [])
      if mismatches:
        return {
          "lineage_status": "mismatch",
          "creation_path_label": "標準監視テーマ",
          "watch_profile_connection": "署名不一致",
          "mismatched_fields": mismatches,
        }
      return {
        "lineage_status": "connected",
        "creation_path_label": "標準監視テーマ",
        "watch_profile_connection": "接続済み",
      }
    return {
      "lineage_status": "partial",
      "creation_path_label": "標準監視テーマ",
      "watch_profile_connection": "部分接続",
    }
  return {
    "lineage_status": "unavailable",
    "creation_path_label": run_origin,
    "watch_profile_connection": "未接続",
  }


def promote_temporary_search_to_theme_draft(
  search_request: Mapping[str, Any],
  *,
  search_run_id: str,
) -> dict[str, Any]:
  keywords_ja = parse_terms(str(search_request.get("keywords_ja", "") or ""))
  keywords_en = parse_terms(str(search_request.get("keywords_en", "") or ""))
  exclude = parse_terms(str(search_request.get("exclude_keywords", "") or ""))
  return build_theme_record(
    {
      "name": str(search_request.get("theme", "") or "")[:120],
      "description": str(search_request.get("theme", "") or ""),
      "keywords": {
        "core_ja": keywords_ja,
        "core_en": keywords_en,
        "use_ja": [],
        "use_en": [],
        "material_process_ja": [],
        "material_process_en": [],
        "exclude_ja": exclude,
        "exclude_en": [],
      },
      "seed_publication_numbers": parse_publication_numbers(str(search_request.get("seed_patent", "") or "")),
      "additional_candidate_publication_numbers": [],
      "status": "draft",
      "source": "promoted_from_temporary_search",
      "source_search_run_id": search_run_id,
    }
  )


def sizing_fixture_theme() -> dict[str, Any]:
  return build_theme_record(
    {
      "name": "PAN系炭素繊維のサイジング剤",
      "description": (
        "PAN系炭素繊維のサイジング剤について、サイジング剤の組成、付与量、乾燥条件が、"
        "集束性、開繊性、毛羽、耐擦過性、樹脂含浸性、界面接着性、引張強度、引張弾性率に与える影響"
      ),
      "keywords": {
        "core_ja": ["炭素繊維", "サイジング剤", "PAN"],
        "core_en": ["carbon fiber", "sizing agent", "PAN"],
        "use_ja": [],
        "use_en": [],
        "material_process_ja": ["乾燥条件", "付与量"],
        "material_process_en": ["drying condition", "add-on amount"],
        "exclude_ja": [],
        "exclude_en": ["textile"],
      },
      "seed_publication_numbers": [],
      "additional_candidate_publication_numbers": [],
      "status": "saved",
      "source": "manual",
      "theme_id": "theme_sizing_fixture",
      "theme_version": 1,
    }
  )


def default_saved_theme_fixture() -> dict[str, Any]:
  return build_theme_record(
    {
      "name": DEFAULT_SAVED_THEME_NAME,
      "description": "Study Demo seed theme for standard monitoring",
      "keywords": {
        "core_ja": ["PAN", "前駆体", "欠陥制御"],
        "core_en": ["PAN precursor", "defect control"],
        "use_ja": [],
        "use_en": [],
        "material_process_ja": ["表面", "内部欠陥"],
        "material_process_en": ["surface defect", "internal defect"],
        "exclude_ja": [],
        "exclude_en": [],
      },
      "seed_publication_numbers": [],
      "additional_candidate_publication_numbers": [],
      "status": "saved",
      "source": "manual",
      "theme_id": "theme_default_saved",
      "theme_version": 1,
    }
  )


def lineage_blocks_search_on_mismatch(context: Mapping[str, Any]) -> bool:
  return str(context.get("lineage_status", "") or summarize_lineage_status(context).get("lineage_status")) == "mismatch"


def bump_theme_version(theme: Mapping[str, Any]) -> dict[str, Any]:
  updated = build_theme_record(
    theme,
    theme_id=str(theme.get("theme_id", "") or new_theme_id()),
    theme_version=int(theme.get("theme_version", 1) or 1) + 1,
    created_at=str(theme.get("created_at", "") or _utc_now_iso()),
  )
  updated["status"] = "saved"
  return updated
