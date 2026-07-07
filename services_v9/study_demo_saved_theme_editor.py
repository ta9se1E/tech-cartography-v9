"""Saved Theme editor synchronization for Study Demo (selector ↔ editor SSOT)."""

from __future__ import annotations

import re
from typing import Any, Mapping

from services_v9.study_demo_theme_lineage import (
  build_theme_record,
  compute_theme_signature,
  parse_publication_numbers,
  parse_terms,
  theme_dirty,
)

EDITOR_FIELDS = (
  "name",
  "description",
  "core_en",
  "core_ja",
  "use_en",
  "use_ja",
  "material_process_en",
  "material_process_ja",
  "exclude_en",
  "exclude_ja",
  "seed_publications",
  "candidate_publications",
  "year_start",
  "year_end",
)


def saved_theme_editor_widget_key(theme_id: str, theme_version: int, field: str) -> str:
  safe_id = re.sub(r"[^A-Za-z0-9._-]+", "_", str(theme_id or "unknown"))
  return f"saved_theme_editor_{safe_id}_v{int(theme_version or 1)}_{field}"


def _join_lines(values: list[str]) -> str:
  return "\n".join(str(item) for item in values if str(item).strip())


def theme_to_editor_values(theme: Mapping[str, Any]) -> dict[str, Any]:
  keywords = dict(theme.get("keywords", {}) or {})
  year_range = dict(theme.get("year_range", {}) or {})
  return {
    "name": str(theme.get("name", "") or ""),
    "description": str(theme.get("description", "") or ""),
    "core_en": _join_lines(list(keywords.get("core_en", []) or [])),
    "core_ja": _join_lines(list(keywords.get("core_ja", []) or [])),
    "use_en": _join_lines(list(keywords.get("use_en", keywords.get("application_en", [])) or [])),
    "use_ja": _join_lines(list(keywords.get("use_ja", keywords.get("application_ja", [])) or [])),
    "material_process_en": _join_lines(list(keywords.get("material_process_en", []) or [])),
    "material_process_ja": _join_lines(list(keywords.get("material_process_ja", []) or [])),
    "exclude_en": _join_lines(list(keywords.get("exclude_en", []) or [])),
    "exclude_ja": _join_lines(list(keywords.get("exclude_ja", []) or [])),
    "seed_publications": _join_lines(list(theme.get("seed_publication_numbers", []) or [])),
    "candidate_publications": _join_lines(list(theme.get("additional_candidate_publication_numbers", []) or [])),
    "year_start": year_range.get("start"),
    "year_end": year_range.get("end"),
  }


def editor_values_to_theme_record(
  values: Mapping[str, Any],
  *,
  base_theme: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
  base = dict(base_theme or {})
  return build_theme_record(
    {
      "theme_id": base.get("theme_id"),
      "theme_version": base.get("theme_version", 1),
      "theme_signature": base.get("theme_signature"),
      "status": base.get("status", "saved"),
      "source": base.get("source", "manual"),
      "source_search_run_id": base.get("source_search_run_id"),
      "name": values.get("name", ""),
      "description": values.get("description", ""),
      "keywords": {
        "core_en": parse_terms(str(values.get("core_en", "") or "")),
        "core_ja": parse_terms(str(values.get("core_ja", "") or "")),
        "use_en": parse_terms(str(values.get("use_en", "") or "")),
        "use_ja": parse_terms(str(values.get("use_ja", "") or "")),
        "material_process_en": parse_terms(str(values.get("material_process_en", "") or "")),
        "material_process_ja": parse_terms(str(values.get("material_process_ja", "") or "")),
        "exclude_en": parse_terms(str(values.get("exclude_en", "") or "")),
        "exclude_ja": parse_terms(str(values.get("exclude_ja", "") or "")),
      },
      "seed_publication_numbers": parse_publication_numbers(str(values.get("seed_publications", "") or "")),
      "additional_candidate_publication_numbers": parse_publication_numbers(
        str(values.get("candidate_publications", "") or "")
      ),
      "year_range": {
        "start": values.get("year_start"),
        "end": values.get("year_end"),
      },
    }
  )


def apply_editor_selection_metadata(
  theme_state: Mapping[str, Any],
  theme: Mapping[str, Any],
) -> dict[str, Any]:
  state = dict(theme_state or {})
  theme_id = str(theme.get("theme_id", "") or "")
  version = int(theme.get("theme_version", 1) or 1)
  state["selected_saved_theme_id"] = theme_id
  state["selected_saved_theme_version"] = version
  state["selected_saved_theme_signature"] = str(theme.get("theme_signature", "") or "")
  state["editor_hydrated_theme_id"] = theme_id
  state["editor_hydrated_theme_version"] = version
  state["saved_theme"] = dict(theme)
  state["widget_theme"] = dict(theme)
  state["editor_values"] = theme_to_editor_values(theme)
  state["editor_dirty"] = False
  return state


def read_editor_values_from_session(
  session_values: Mapping[str, Any],
  *,
  theme_id: str,
  theme_version: int,
) -> dict[str, Any]:
  values: dict[str, Any] = {}
  for field in EDITOR_FIELDS:
    key = saved_theme_editor_widget_key(theme_id, theme_version, field)
    if key in session_values:
      values[field] = session_values.get(key)
  return values


def validate_theme_update_save_guard(
  *,
  selected_theme_id: str,
  editor_theme_id: str,
) -> list[str]:
  if not selected_theme_id or not editor_theme_id:
    return ["theme_id_missing"]
  if selected_theme_id != editor_theme_id:
    return ["selector_editor_mismatch"]
  return []


def editor_dirty_vs_saved(saved_theme: Mapping[str, Any], editor_values: Mapping[str, Any]) -> bool:
  candidate = editor_values_to_theme_record(editor_values, base_theme=saved_theme)
  return theme_dirty(saved_theme, candidate)


def theme_editor_mismatch_message(errors: list[str]) -> str | None:
  if "selector_editor_mismatch" in errors:
    return "選択中Themeと編集対象Themeが一致しないため保存できません。"
  return None


__all__ = [
  "EDITOR_FIELDS",
  "apply_editor_selection_metadata",
  "editor_dirty_vs_saved",
  "editor_values_to_theme_record",
  "read_editor_values_from_session",
  "saved_theme_editor_widget_key",
  "theme_editor_mismatch_message",
  "theme_to_editor_values",
  "validate_theme_update_save_guard",
]
