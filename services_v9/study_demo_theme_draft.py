"""Theme draft state model for Study Demo temporary-search promotion."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from services_v9.study_demo_theme_lineage import (
  build_theme_record,
  compute_theme_signature,
  new_theme_id,
  promote_temporary_search_to_theme_draft,
)
from services_v9.watch_profile_schema import normalize_terms, parse_publication_numbers, parse_terms

THEME_DRAFT_SCHEMA_VERSION = 1
THEMES_PREFIX = "themes/"


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).isoformat()


def _new_draft_id() -> str:
  return f"draft_{uuid.uuid4().hex[:12]}"


def _terms_to_text(values: Sequence[str]) -> str:
  return "\n".join(normalize_terms(list(values)))


def build_theme_draft_from_temporary_search(
  search_request: Mapping[str, Any],
  *,
  search_run_id: str,
  active_context: Mapping[str, Any] | None = None,
  context_generation: int | None = None,
) -> dict[str, Any]:
  base = promote_temporary_search_to_theme_draft(search_request, search_run_id=search_run_id)
  draft_id = _new_draft_id()
  now = _utc_now_iso()
  keywords = dict(base.get("keywords", {}) or {})
  provider_settings = {
    "enable_patent": bool(search_request.get("enable_patent", True)),
    "enable_paper": bool(search_request.get("enable_paper", True)),
    "enable_web": bool(search_request.get("enable_web", True)),
    "patent_display_limit": int(search_request.get("patent_display_limit", 50) or 50),
    "paper_display_limit": int(search_request.get("paper_display_limit", 50) or 50),
    "web_max_results": int(search_request.get("web_max_results", 10) or 10),
  }
  draft = {
    **base,
    "draft_id": draft_id,
    "schema_version": THEME_DRAFT_SCHEMA_VERSION,
    "status": "draft",
    "source_run_origin": "temporary_search",
    "original_active_theme_text": str((active_context or {}).get("theme", search_request.get("theme", "")) or ""),
    "original_search_request_ref": f"search_runs/{search_run_id}/search_request.json",
    "created_from_context_generation": context_generation,
    "year_range": {
      "start": str(search_request.get("year_start", "") or ""),
      "end": str(search_request.get("year_end", "") or ""),
    },
    "provider_settings": provider_settings,
    "exact_phrase": str(search_request.get("exact_phrase", "") or ""),
    "dirty": False,
    "loaded_into_editor": False,
    "save_status": "unsaved",
    "created_at": now,
    "updated_at": now,
    "application_scope": "study_demo_only",
    "audit_event_type": "theme_draft_created",
  }
  draft["theme_draft_signature"] = compute_theme_draft_signature(draft)
  return draft


def compute_theme_draft_signature(draft: Mapping[str, Any]) -> str:
  exclude = frozenset(
    {
      "draft_id",
      "created_at",
      "updated_at",
      "theme_draft_signature",
      "dirty",
      "loaded_into_editor",
      "save_status",
      "audit_event_type",
    }
  )
  payload = {key: value for key, value in dict(draft).items() if key not in exclude}
  blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
  return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def validate_theme_draft(draft: Mapping[str, Any]) -> list[str]:
  errors: list[str] = []
  if str(draft.get("status", "")) != "draft":
    errors.append("status must be draft")
  if str(draft.get("source", "")) != "promoted_from_temporary_search":
    errors.append("invalid source")
  if not str(draft.get("source_search_run_id", "")).strip():
    errors.append("source_search_run_id required")
  if not str(draft.get("name", "")).strip():
    errors.append("name required")
  if not str(draft.get("description", "")).strip():
    errors.append("description required")
  return errors


def validate_draft_generation_precondition(
  draft: Mapping[str, Any],
  active_context: Mapping[str, Any] | None,
) -> list[str]:
  errors: list[str] = []
  if not active_context:
    errors.append("active_context_missing")
    return errors
  run_id = str(active_context.get("active_search_run_id", "") or "")
  if str(draft.get("source_search_run_id", "")) != run_id:
    errors.append("source_run_mismatch")
  ctx_gen = active_context.get("active_context_generation", active_context.get("context_generation"))
  draft_gen = draft.get("created_from_context_generation")
  if draft_gen is not None and ctx_gen is not None and int(draft_gen) != int(ctx_gen):
    errors.append("context_generation_mismatch")
  return errors


def update_theme_draft(
  draft: Mapping[str, Any],
  edits: Mapping[str, Any],
  *,
  expected_signature: str | None = None,
) -> dict[str, Any]:
  if expected_signature and str(draft.get("theme_draft_signature", "")) != expected_signature:
    raise ValueError("theme draft signature is stale")
  updated = copy.deepcopy(dict(draft))
  for key in ("name", "description", "exact_phrase"):
    if key in edits:
      updated[key] = str(edits.get(key, "") or "")
  if "keywords" in edits:
    updated["keywords"] = dict(edits.get("keywords", {}) or {})
  if "seed_publication_numbers" in edits:
    updated["seed_publication_numbers"] = normalize_terms(list(edits.get("seed_publication_numbers", []) or []))
  if "additional_candidate_publication_numbers" in edits:
    updated["additional_candidate_publication_numbers"] = normalize_terms(
      list(edits.get("additional_candidate_publication_numbers", []) or [])
    )
  if "year_range" in edits:
    updated["year_range"] = dict(edits.get("year_range", {}) or {})
  if "provider_settings" in edits:
    updated["provider_settings"] = dict(edits.get("provider_settings", {}) or {})
  updated["updated_at"] = _utc_now_iso()
  updated["dirty"] = True
  updated["save_status"] = "unsaved"
  updated["theme_draft_signature"] = compute_theme_draft_signature(updated)
  return updated


def draft_from_editor_payload(draft: Mapping[str, Any], editor: Mapping[str, Any]) -> dict[str, Any]:
  keywords = {
    "core_ja": parse_terms(str(editor.get("core_ja", "") or "")),
    "core_en": parse_terms(str(editor.get("core_en", "") or "")),
    "use_ja": parse_terms(str(editor.get("use_ja", "") or "")),
    "use_en": parse_terms(str(editor.get("use_en", "") or "")),
    "material_process_ja": parse_terms(str(editor.get("material_process_ja", "") or "")),
    "material_process_en": parse_terms(str(editor.get("material_process_en", "") or "")),
    "exclude_ja": parse_terms(str(editor.get("exclude_ja", "") or "")),
    "exclude_en": parse_terms(str(editor.get("exclude_en", "") or "")),
  }
  return update_theme_draft(
    draft,
    {
      "name": str(editor.get("name", "") or ""),
      "description": str(editor.get("description", "") or ""),
      "exact_phrase": str(editor.get("exact_phrase", "") or ""),
      "keywords": keywords,
      "seed_publication_numbers": parse_publication_numbers(str(editor.get("seed_publications", "") or "")),
      "additional_candidate_publication_numbers": parse_publication_numbers(
        str(editor.get("candidate_publications", "") or "")
      ),
      "year_range": {
        "start": str(editor.get("year_start", "") or ""),
        "end": str(editor.get("year_end", "") or ""),
      },
      "provider_settings": {
        "enable_patent": bool(editor.get("enable_patent", True)),
        "enable_paper": bool(editor.get("enable_paper", True)),
        "enable_web": bool(editor.get("enable_web", True)),
        "patent_display_limit": int(editor.get("patent_display_limit", 50) or 50),
        "paper_display_limit": int(editor.get("paper_display_limit", 50) or 50),
        "web_max_results": int(editor.get("web_max_results", 10) or 10),
      },
    },
    expected_signature=str(draft.get("theme_draft_signature", "") or "") or None,
  )


def compare_draft_with_saved_theme(draft: Mapping[str, Any], saved_theme: Mapping[str, Any]) -> dict[str, Any]:
  return {
    "same_theme_id": str(draft.get("theme_id", "")) == str(saved_theme.get("theme_id", "")),
    "same_name": str(draft.get("name", "")).strip() == str(saved_theme.get("name", "")).strip(),
    "draft_signature": draft.get("theme_draft_signature"),
    "saved_signature": compute_theme_signature(saved_theme),
  }


def build_new_saved_theme_from_draft(
  draft: Mapping[str, Any],
  *,
  existing_themes: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
  errors = validate_theme_draft(draft)
  if errors:
    raise ValueError("; ".join(errors))
  new_id = new_theme_id()
  existing_ids = {str(item.get("theme_id", "")) for item in existing_themes}
  while new_id in existing_ids:
    new_id = new_theme_id()
  same_name = any(str(item.get("name", "")).strip() == str(draft.get("name", "")).strip() for item in existing_themes)
  saved = build_theme_record(
    {
      "name": draft.get("name"),
      "description": draft.get("description"),
      "keywords": draft.get("keywords"),
      "seed_publication_numbers": draft.get("seed_publication_numbers", []),
      "additional_candidate_publication_numbers": draft.get("additional_candidate_publication_numbers", []),
      "status": "saved",
      "source": "promoted_from_temporary_search",
      "source_search_run_id": draft.get("source_search_run_id"),
      "theme_id": new_id,
      "theme_version": 1,
    },
    theme_id=new_id,
    theme_version=1,
  )
  saved["created_from_draft_id"] = draft.get("draft_id")
  saved["source_run_origin"] = draft.get("source_run_origin", "temporary_search")
  saved["source_theme_draft_signature"] = draft.get("theme_draft_signature")
  saved["created_from_context_generation"] = draft.get("created_from_context_generation")
  saved["application_scope"] = "study_demo_only"
  saved["audit_event_type"] = "theme_saved_as_new"
  saved["year_range"] = dict(draft.get("year_range", {}) or {})
  saved["provider_settings"] = dict(draft.get("provider_settings", {}) or {})
  saved["exact_phrase"] = str(draft.get("exact_phrase", "") or "")
  saved["same_name_warning"] = same_name
  return saved


def discard_theme_draft(_draft: Mapping[str, Any] | None) -> None:
  return None


def summarize_theme_draft_state(
  draft: Mapping[str, Any] | None,
  *,
  saved_theme: Mapping[str, Any] | None = None,
  search_plan: Mapping[str, Any] | None = None,
  theme_saved: bool = False,
) -> dict[str, Any]:
  if not draft:
    return {
      "has_draft": False,
      "workflow": {
        "draft_created": False,
        "draft_reviewed": False,
        "theme_saved": theme_saved,
        "watch_profile_generated": False,
        "search_plan_generated": bool(search_plan),
        "live_search_executed": False,
      },
    }
  reviewed = bool(draft.get("loaded_into_editor")) and not bool(draft.get("dirty"))
  return {
    "has_draft": True,
    "draft_id": draft.get("draft_id"),
    "theme_id": draft.get("theme_id"),
    "source_search_run_id": draft.get("source_search_run_id"),
    "theme_draft_signature_short": str(draft.get("theme_draft_signature", ""))[:8],
    "dirty": bool(draft.get("dirty")),
    "save_status": draft.get("save_status"),
    "workflow": {
      "draft_created": True,
      "draft_reviewed": reviewed,
      "theme_saved": theme_saved,
      "watch_profile_generated": False,
      "search_plan_generated": bool(search_plan) and not should_show_old_plan_warning(draft, search_plan, saved_theme),
      "live_search_executed": False,
    },
  }


def should_show_old_plan_warning(
  draft: Mapping[str, Any] | None,
  search_plan: Mapping[str, Any] | None,
  saved_theme: Mapping[str, Any] | None,
) -> bool:
  if not draft or not search_plan:
    return False
  if str(draft.get("status", "")) != "draft":
    return False
  plan_theme_id = str(search_plan.get("source_theme_id", "") or "")
  saved_theme_id = str((saved_theme or {}).get("theme_id", "") or "")
  return bool(plan_theme_id and saved_theme_id and plan_theme_id == saved_theme_id)


def can_generate_plan_for_draft(draft: Mapping[str, Any] | None, *, theme_saved: bool) -> bool:
  if draft and str(draft.get("status", "")) == "draft":
    return False
  return theme_saved


def can_generate_watch_profile_for_draft(draft: Mapping[str, Any] | None, *, theme_saved: bool) -> bool:
  return can_generate_plan_for_draft(draft, theme_saved=theme_saved)


def find_existing_draft_for_run(draft: Mapping[str, Any] | None, search_run_id: str) -> bool:
  return bool(draft and str(draft.get("source_search_run_id", "")) == str(search_run_id or ""))


def theme_object_path(theme_id: str, version: int = 1) -> str:
  safe = re.sub(r"[^A-Za-z0-9._-]+", "_", str(theme_id or ""))
  return f"{THEMES_PREFIX}{safe}/versions/v{int(version)}.json"


def save_theme_to_storage(
  theme: Mapping[str, Any],
  *,
  storage_client: Any | None = None,
  persist_to_cloud: bool = False,
  environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
  if not persist_to_cloud:
    return {"status": "session_only", "path": theme_object_path(str(theme.get("theme_id", "")))}
  from services_v9.study_demo_config import get_study_demo_bucket
  from services_v9.study_demo_storage import validate_study_demo_write_target

  bucket_name = get_study_demo_bucket(environ)
  validate_study_demo_write_target(bucket_name, environ=environ)
  path = theme_object_path(str(theme.get("theme_id", "")))
  payload = json.dumps(dict(theme), ensure_ascii=False, indent=2) + "\n"
  client = storage_client if storage_client is not None else _build_client()
  blob = client.bucket(bucket_name).blob(path)
  blob.upload_from_string(payload, content_type="application/json")
  return {"status": "saved", "path": path}


def draft_editor_defaults(draft: Mapping[str, Any]) -> dict[str, Any]:
  keywords = dict(draft.get("keywords", {}) or {})
  provider = dict(draft.get("provider_settings", {}) or {})
  year_range = dict(draft.get("year_range", {}) or {})
  return {
    "name": str(draft.get("name", "") or ""),
    "description": str(draft.get("description", "") or ""),
    "core_ja": _terms_to_text(keywords.get("core_ja", [])),
    "core_en": _terms_to_text(keywords.get("core_en", [])),
    "use_ja": _terms_to_text(keywords.get("use_ja", [])),
    "use_en": _terms_to_text(keywords.get("use_en", [])),
    "material_process_ja": _terms_to_text(keywords.get("material_process_ja", [])),
    "material_process_en": _terms_to_text(keywords.get("material_process_en", [])),
    "exclude_ja": _terms_to_text(keywords.get("exclude_ja", [])),
    "exclude_en": _terms_to_text(keywords.get("exclude_en", [])),
    "seed_publications": _terms_to_text(draft.get("seed_publication_numbers", [])),
    "candidate_publications": _terms_to_text(draft.get("additional_candidate_publication_numbers", [])),
    "year_start": str(year_range.get("start", "") or ""),
    "year_end": str(year_range.get("end", "") or ""),
    "exact_phrase": str(draft.get("exact_phrase", "") or ""),
    "enable_patent": bool(provider.get("enable_patent", True)),
    "enable_paper": bool(provider.get("enable_paper", True)),
    "enable_web": bool(provider.get("enable_web", True)),
    "patent_display_limit": int(provider.get("patent_display_limit", 50) or 50),
    "paper_display_limit": int(provider.get("paper_display_limit", 50) or 50),
    "web_max_results": int(provider.get("web_max_results", 10) or 10),
  }


def draft_widget_key(draft_id: str, field: str) -> str:
  safe = re.sub(r"[^A-Za-z0-9._-]+", "_", str(draft_id or "draft"))
  return f"theme_draft_{safe}_{field}"


def _build_client():
  from google.cloud import storage

  return storage.Client()
