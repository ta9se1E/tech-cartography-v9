"""Load saved Theme / Watch Profile / Search Plan lineage artifacts for Study Demo UI."""

from __future__ import annotations

import json
from typing import Any, Mapping

from services_v9.study_demo_config import get_study_demo_bucket
from services_v9.study_demo_lineage_storage import (
  load_json_object,
  search_plan_latest_path,
  theme_latest_path,
  watch_profile_latest_path,
)
from services_v9.study_demo_storage import validate_study_demo_write_target
from services_v9.study_demo_theme_lineage import (
  compute_search_plan_signature,
  compute_theme_signature,
  compute_watch_profile_signature,
  default_saved_theme_fixture,
)

LINEAGE_REF_FIELDS = (
  "source_theme_id",
  "source_theme_version",
  "source_theme_signature",
  "source_watch_profile_id",
  "source_watch_profile_version",
  "source_watch_profile_signature",
  "source_search_plan_id",
  "source_search_plan_version",
  "source_search_plan_signature",
)


def _build_client():
  from google.cloud import storage

  return storage.Client()


def list_saved_themes_from_storage(
  *,
  environ: Mapping[str, str] | None = None,
  storage_client: Any | None = None,
) -> list[dict[str, Any]]:
  bucket_name = get_study_demo_bucket(environ)
  validate_study_demo_write_target(bucket_name, environ=environ)
  client = storage_client if storage_client is not None else _build_client()
  themes: list[dict[str, Any]] = []
  seen: set[str] = set()
  for blob in client.bucket(bucket_name).list_blobs(prefix="themes/"):
    name = str(blob.name or "")
    if not name.endswith("/latest.json"):
      continue
    try:
      payload = json.loads(blob.download_as_bytes().decode("utf-8"))
    except (json.JSONDecodeError, OSError):
      continue
    theme_id = str(payload.get("theme_id", "") or "")
    if not theme_id or theme_id in seen:
      continue
    if str(payload.get("status", "")) not in {"saved", "draft"}:
      continue
    seen.add(theme_id)
    themes.append(dict(payload))
  themes.sort(key=lambda item: (str(item.get("name", "")), str(item.get("theme_id", ""))))
  default = dict(default_saved_theme_fixture())
  if not any(str(item.get("theme_id", "")) == str(default.get("theme_id", "")) for item in themes):
    themes.append(default)
    themes.sort(key=lambda item: (str(item.get("name", "")), str(item.get("theme_id", ""))))
  if not themes:
    return [default]
  return themes


def load_theme_by_id(
  theme_id: str,
  *,
  environ: Mapping[str, str] | None = None,
  storage_client: Any | None = None,
) -> dict[str, Any] | None:
  if not str(theme_id or "").strip():
    return None
  bucket_name = get_study_demo_bucket(environ)
  try:
    payload = load_json_object(theme_latest_path(theme_id), bucket_name=bucket_name, storage_client=storage_client)
  except FileNotFoundError:
    return None
  if compute_theme_signature(payload) != str(payload.get("theme_signature", "") or ""):
    return None
  return dict(payload)


def load_watch_profile_by_id(
  watch_profile_id: str,
  *,
  environ: Mapping[str, str] | None = None,
  storage_client: Any | None = None,
) -> dict[str, Any] | None:
  if not str(watch_profile_id or "").strip():
    return None
  bucket_name = get_study_demo_bucket(environ)
  try:
    payload = load_json_object(
      watch_profile_latest_path(watch_profile_id),
      bucket_name=bucket_name,
      storage_client=storage_client,
    )
  except FileNotFoundError:
    return None
  if compute_watch_profile_signature(payload) != str(payload.get("watch_profile_signature", "") or ""):
    return None
  return dict(payload)


def load_search_plan_by_id(
  search_plan_id: str,
  *,
  environ: Mapping[str, str] | None = None,
  storage_client: Any | None = None,
  require_signature_match: bool = True,
) -> dict[str, Any] | None:
  if not str(search_plan_id or "").strip():
    return None
  bucket_name = get_study_demo_bucket(environ)
  try:
    payload = load_json_object(
      search_plan_latest_path(search_plan_id),
      bucket_name=bucket_name,
      storage_client=storage_client,
    )
  except FileNotFoundError:
    return None
  stored_signature = str(payload.get("search_plan_signature", "") or "")
  if not stored_signature:
    return None
  if require_signature_match:
    recomputed = compute_search_plan_signature(payload)
    if recomputed != stored_signature:
      payload = dict(payload)
      payload["signature_recompute_mismatch"] = True
      return payload
  return dict(payload)


def lineage_refs_from_search_request(request: Mapping[str, Any]) -> dict[str, Any]:
  req = dict(request or {})
  refs: dict[str, Any] = {}
  mapping = {
    "source_theme_id": "source_theme_id",
    "source_theme_version": "source_theme_version",
    "source_theme_signature": "source_theme_signature",
    "source_watch_profile_id": "source_watch_profile_id",
    "source_watch_profile_version": "source_watch_profile_version",
    "source_watch_profile_signature": "source_watch_profile_signature",
    "source_search_plan_id": "source_search_plan_id",
    "source_search_plan_version": "source_search_plan_version",
    "source_search_plan_signature": "source_search_plan_signature",
  }
  for target, source in mapping.items():
    value = req.get(source)
    if value not in (None, ""):
      refs[target] = value
  if req.get("search_plan_id") and not refs.get("source_search_plan_id"):
    refs["source_search_plan_id"] = req.get("search_plan_id")
    refs["source_search_plan_version"] = req.get("search_plan_version")
    refs["source_search_plan_signature"] = req.get("search_plan_signature")
  return refs


def resolve_active_lineage_artifacts(
  context: Mapping[str, Any],
  *,
  environ: Mapping[str, str] | None = None,
  storage_client: Any | None = None,
) -> dict[str, Any]:
  ctx = dict(context or {})
  theme = load_theme_by_id(str(ctx.get("source_theme_id", "") or ""), environ=environ, storage_client=storage_client)
  profile = load_watch_profile_by_id(
    str(ctx.get("source_watch_profile_id", "") or ""),
    environ=environ,
    storage_client=storage_client,
  )
  plan = load_search_plan_by_id(
    str(ctx.get("source_search_plan_id", "") or ""),
    environ=environ,
    storage_client=storage_client,
  )
  signatures_match = bool(
    theme
    and profile
    and plan
    and str(profile.get("source_theme_signature", "")) == str(theme.get("theme_signature", ""))
    and str(plan.get("source_watch_profile_signature", "")) == str(profile.get("watch_profile_signature", ""))
    and str(plan.get("source_theme_signature", "")) == str(theme.get("theme_signature", ""))
  )
  return {
    "theme": theme,
    "watch_profile": profile,
    "search_plan": plan,
    "theme_found": theme is not None,
    "watch_profile_found": profile is not None,
    "search_plan_found": plan is not None,
    "signatures_match": signatures_match,
  }


def pick_active_saved_theme(
  themes: list[dict[str, Any]],
  *,
  active_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
  saved_themes = list(themes or [])
  if not saved_themes:
    return dict(default_saved_theme_fixture())
  ctx = dict(active_context or {})
  target_id = str(ctx.get("source_theme_id", "") or "")
  if target_id:
    for item in saved_themes:
      if str(item.get("theme_id", "")) == target_id:
        expected_sig = str(ctx.get("source_theme_signature", "") or "")
        if expected_sig and str(item.get("theme_signature", "")) != expected_sig:
          break
        return dict(item)
  return dict(saved_themes[0])


def hydrate_theme_lineage_session_state(
  active_context: Mapping[str, Any] | None,
  base_state: Mapping[str, Any] | None = None,
  *,
  environ: Mapping[str, str] | None = None,
  storage_client: Any | None = None,
) -> dict[str, Any]:
  state = dict(base_state or {})
  ctx = dict(active_context or {})
  saved_themes = list_saved_themes_from_storage(environ=environ, storage_client=storage_client)
  resolved = resolve_active_lineage_artifacts(ctx, environ=environ, storage_client=storage_client)
  active_theme = pick_active_saved_theme(saved_themes, active_context=ctx)
  if resolved.get("theme"):
    active_theme = dict(resolved["theme"])
  state["saved_themes"] = saved_themes
  state["saved_theme"] = active_theme
  state["selected_saved_theme_id"] = str(active_theme.get("theme_id", ""))
  state["widget_theme"] = dict(active_theme)
  if resolved.get("watch_profile"):
    state["watch_profile"] = dict(resolved["watch_profile"])
  if resolved.get("search_plan"):
    state["search_plan"] = dict(resolved["search_plan"])
    state["active_lineage_search_plan"] = dict(resolved["search_plan"])
  state["theme_saved_from_draft"] = str(active_theme.get("source", "")) == "promoted_from_temporary_search"
  state["live_lineage_hydrated"] = True
  state["live_lineage_signatures_match"] = bool(resolved.get("signatures_match"))
  return state


def load_lineage_for_theme_id(
  theme_id: str,
  *,
  environ: Mapping[str, str] | None = None,
  storage_client: Any | None = None,
) -> dict[str, Any]:
  from services_v9.study_demo_theme_lineage import new_search_plan_id, new_watch_profile_id

  theme = load_theme_by_id(theme_id, environ=environ, storage_client=storage_client)
  if not theme:
    return {"theme": None, "watch_profile": None, "search_plan": None}
  profile = load_watch_profile_by_id(
    new_watch_profile_id(theme_id),
    environ=environ,
    storage_client=storage_client,
  )
  plan = None
  if profile:
    plan = load_search_plan_by_id(
      new_search_plan_id(str(profile.get("watch_profile_id", "") or "")),
      environ=environ,
      storage_client=storage_client,
    )
  return {"theme": theme, "watch_profile": profile, "search_plan": plan}


def resolve_display_search_plan(
  *,
  active_context: Mapping[str, Any] | None,
  theme_state: Mapping[str, Any],
) -> dict[str, Any] | None:
  state = dict(theme_state or {})
  ctx = dict(active_context or {})
  selected_theme_id = str(state.get("selected_saved_theme_id", "") or "")
  active_theme_id = str(ctx.get("source_theme_id", "") or "")
  if active_theme_id and selected_theme_id and selected_theme_id != active_theme_id:
    lineage = load_lineage_for_theme_id(selected_theme_id)
    plan = lineage.get("search_plan")
    return dict(plan) if plan else None
  plan = state.get("active_lineage_search_plan") or state.get("search_plan")
  return dict(plan) if plan else None


__all__ = [
  "LINEAGE_REF_FIELDS",
  "hydrate_theme_lineage_session_state",
  "lineage_refs_from_search_request",
  "list_saved_themes_from_storage",
  "load_lineage_for_theme_id",
  "load_search_plan_by_id",
  "load_theme_by_id",
  "load_watch_profile_by_id",
  "pick_active_saved_theme",
  "resolve_active_lineage_artifacts",
  "resolve_display_search_plan",
]
