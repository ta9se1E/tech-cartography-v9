"""Schema helpers for the bilingual v9.2 watch profile."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

DEFAULT_SOURCE_TYPES = ["patent", "paper", "web", "company"]
DEFAULT_CADENCE = "weekly"
KEYWORD_GROUPS = (
  "core_en",
  "core_ja",
  "application_en",
  "application_ja",
  "material_process_en",
  "material_process_ja",
  "exclude_en",
  "exclude_ja",
)


def split_terms(text: str) -> list[str]:
  normalized = str(text or "")
  for sep in [",", "、", ";", "；", "\n"]:
    normalized = normalized.replace(sep, "\n")
  return normalized.splitlines()


def normalize_terms(terms: list[str]) -> list[str]:
  normalized: list[str] = []
  seen: set[str] = set()
  for item in terms:
    value = str(item or "").strip(" \t\r\n\u3000")
    if not value:
      continue
    if value in seen:
      continue
    seen.add(value)
    normalized.append(value)
  return normalized


def parse_terms(text: str) -> list[str]:
  return normalize_terms(split_terms(text))


def normalize_publication_number(value: str) -> str:
  compact = re.sub(r"[^A-Za-z0-9]", "", str(value or "").upper())
  return compact.strip()


def parse_publication_numbers(text: str) -> list[str]:
  numbers = [normalize_publication_number(item) for item in split_terms(text)]
  return normalize_terms(numbers)


def default_bilingual_watch_profile() -> dict[str, Any]:
  return {
    "schema_version": "v9.2",
    "theme_name": "",
    "theme_description": "",
    "keywords": {
      "core_en": [],
      "core_ja": [],
      "application_en": [],
      "application_ja": [],
      "material_process_en": [],
      "material_process_ja": [],
      "exclude_en": [],
      "exclude_ja": [],
    },
    "seed_publications": [],
    "candidate_publications": [],
    "target_companies": [],
    "countries": [],
    "source_types": list(DEFAULT_SOURCE_TYPES),
    "cadence": DEFAULT_CADENCE,
    "priority_rules": [],
    "notes": "",
  }


def _contains_ascii_letter(value: str) -> bool:
  return any("A" <= char <= "Z" or "a" <= char <= "z" for char in value)


def _merge_terms(target: list[str], values: list[str]) -> list[str]:
  return normalize_terms(list(target) + list(values))


def _normalize_keywords_block(raw_keywords: Any) -> dict[str, list[str]]:
  base = default_bilingual_watch_profile()["keywords"]
  if not isinstance(raw_keywords, dict):
    return base
  for key in KEYWORD_GROUPS:
    base[key] = normalize_terms(list(raw_keywords.get(key, [])))
  return base


def migrate_watch_profile(profile: dict[str, Any]) -> dict[str, Any]:
  migrated = default_bilingual_watch_profile()
  raw = deepcopy(profile or {})

  if raw.get("schema_version") == "v9.2":
    migrated["theme_name"] = str(raw.get("theme_name", "")).strip()
    migrated["theme_description"] = str(raw.get("theme_description", "")).strip()
    migrated["keywords"] = _normalize_keywords_block(raw.get("keywords"))
    migrated["seed_publications"] = parse_publication_numbers("\n".join(str(item) for item in raw.get("seed_publications", [])))
    migrated["candidate_publications"] = parse_publication_numbers("\n".join(str(item) for item in raw.get("candidate_publications", [])))
    migrated["target_companies"] = normalize_terms(list(raw.get("target_companies", [])))
    migrated["countries"] = normalize_terms(list(raw.get("countries", [])))
    migrated["source_types"] = normalize_terms([str(item).lower() for item in raw.get("source_types", DEFAULT_SOURCE_TYPES)])
    migrated["cadence"] = str(raw.get("cadence", DEFAULT_CADENCE)).strip().lower() or DEFAULT_CADENCE
    migrated["priority_rules"] = normalize_terms(list(raw.get("priority_rules", [])))
    migrated["notes"] = str(raw.get("notes", "")).strip()
    if not migrated["source_types"]:
      migrated["source_types"] = list(DEFAULT_SOURCE_TYPES)
    return migrated

  migrated["theme_name"] = str(raw.get("theme_name") or raw.get("theme") or "").strip()
  migrated["theme_description"] = str(raw.get("theme_description", "")).strip()
  migrated["target_companies"] = normalize_terms(list(raw.get("target_companies", [])))
  migrated["countries"] = normalize_terms(list(raw.get("countries", [])))
  migrated["source_types"] = normalize_terms([str(item).lower() for item in raw.get("source_types", DEFAULT_SOURCE_TYPES)])
  migrated["cadence"] = str(raw.get("cadence", DEFAULT_CADENCE)).strip().lower() or DEFAULT_CADENCE
  migrated["priority_rules"] = normalize_terms(list(raw.get("priority_rules", [])))
  migrated["notes"] = str(raw.get("notes", "")).strip()

  include_keywords = normalize_terms(list(raw.get("include_keywords", [])))
  for item in include_keywords:
    bucket = "core_en" if _contains_ascii_letter(item) else "core_ja"
    migrated["keywords"][bucket].append(item)

  exclude_keywords = normalize_terms(list(raw.get("exclude_keywords", [])))
  for item in exclude_keywords:
    bucket = "exclude_en" if _contains_ascii_letter(item) else "exclude_ja"
    migrated["keywords"][bucket].append(item)

  for key in KEYWORD_GROUPS:
    migrated["keywords"][key] = normalize_terms(migrated["keywords"][key])

  migrated["seed_publications"] = parse_publication_numbers("\n".join(str(item) for item in raw.get("seed_publications", [])))
  migrated["candidate_publications"] = parse_publication_numbers("\n".join(str(item) for item in raw.get("candidate_publications", [])))

  if not migrated["source_types"]:
    migrated["source_types"] = list(DEFAULT_SOURCE_TYPES)
  return migrated


def build_profile_from_form(form_values: dict[str, Any]) -> dict[str, Any]:
  profile = default_bilingual_watch_profile()
  profile["theme_name"] = str(
    form_values.get("theme_name")
    or form_values.get("ui_theme_name_input")
    or form_values.get("theme")
    or ""
  ).strip()
  profile["theme_description"] = str(
    form_values.get("theme_description")
    or form_values.get("ui_theme_description_input")
    or ""
  ).strip()
  profile["keywords"]["core_en"] = parse_terms(str(form_values.get("core_en") or form_values.get("ui_core_en_input") or ""))
  profile["keywords"]["core_ja"] = parse_terms(str(form_values.get("core_ja") or form_values.get("ui_core_ja_input") or ""))
  profile["keywords"]["application_en"] = parse_terms(str(form_values.get("application_en") or form_values.get("ui_application_en_input") or ""))
  profile["keywords"]["application_ja"] = parse_terms(str(form_values.get("application_ja") or form_values.get("ui_application_ja_input") or ""))
  profile["keywords"]["material_process_en"] = parse_terms(str(form_values.get("material_process_en") or form_values.get("ui_material_process_en_input") or ""))
  profile["keywords"]["material_process_ja"] = parse_terms(str(form_values.get("material_process_ja") or form_values.get("ui_material_process_ja_input") or ""))
  profile["keywords"]["exclude_en"] = parse_terms(str(form_values.get("exclude_en") or form_values.get("ui_exclude_en_input") or ""))
  profile["keywords"]["exclude_ja"] = parse_terms(str(form_values.get("exclude_ja") or form_values.get("ui_exclude_ja_input") or ""))
  profile["seed_publications"] = parse_publication_numbers(str(form_values.get("seed_publications") or form_values.get("ui_seed_publications_input") or ""))
  profile["candidate_publications"] = parse_publication_numbers(str(form_values.get("candidate_publications") or form_values.get("ui_candidate_publications_input") or ""))
  profile["target_companies"] = parse_terms(str(form_values.get("target_companies") or form_values.get("ui_target_companies_input") or ""))
  profile["countries"] = parse_terms(str(form_values.get("countries") or form_values.get("ui_countries_input") or ""))
  source_types = form_values.get("source_types") or form_values.get("ui_source_types_input") or DEFAULT_SOURCE_TYPES
  profile["source_types"] = normalize_terms([str(item).strip().lower() for item in list(source_types)])
  if not profile["source_types"]:
    profile["source_types"] = list(DEFAULT_SOURCE_TYPES)
  profile["cadence"] = str(form_values.get("cadence") or form_values.get("ui_cadence_input") or DEFAULT_CADENCE).strip().lower() or DEFAULT_CADENCE
  profile["priority_rules"] = parse_terms(str(form_values.get("priority_rules") or form_values.get("ui_priority_rules_input") or ""))
  profile["notes"] = str(form_values.get("notes") or form_values.get("ui_notes_input") or "").strip()
  return migrate_watch_profile(profile)


def watch_profile_summary(profile: dict[str, Any]) -> dict[str, Any]:
  migrated = migrate_watch_profile(profile)
  keywords = migrated["keywords"]
  counts = {
    "core_en": len(keywords["core_en"]),
    "core_ja": len(keywords["core_ja"]),
    "application_en": len(keywords["application_en"]),
    "application_ja": len(keywords["application_ja"]),
    "material_process_en": len(keywords["material_process_en"]),
    "material_process_ja": len(keywords["material_process_ja"]),
    "exclude_en": len(keywords["exclude_en"]),
    "exclude_ja": len(keywords["exclude_ja"]),
    "seed_publications": len(migrated["seed_publications"]),
    "candidate_publications": len(migrated["candidate_publications"]),
    "target_companies": len(migrated["target_companies"]),
    "countries": len(migrated["countries"]),
  }
  return {
    "schema_version": migrated["schema_version"],
    "theme_name": migrated["theme_name"],
    "theme_description": migrated["theme_description"],
    "counts": counts,
    "source_types": list(migrated["source_types"]),
    "cadence": migrated["cadence"],
    "priority_rule_count": len(migrated["priority_rules"]),
    "seed_publications": list(migrated["seed_publications"]),
    "candidate_publications": list(migrated["candidate_publications"]),
    "target_companies": list(migrated["target_companies"]),
    "notes": migrated["notes"],
  }
