"""Theme draft mapping pipeline for temporary search promotion."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Mapping, Sequence

from services_v9.study_demo_theme_term_dictionary import (
  CANONICAL_DEDUP_GROUPS,
  bucket_to_keyword_key,
  iter_dictionary_entries,
)
from services_v9.watch_profile_schema import normalize_terms, parse_publication_numbers, parse_terms

JA_RE = re.compile(r"[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]")
EN_RE = re.compile(r"[A-Za-z]")


def _normalize_value(value: str) -> str:
  text = unicodedata.normalize("NFKC", str(value or "").strip())
  return re.sub(r"\s+", " ", text)


def detect_term_language(term: str) -> str:
  text = _normalize_value(term)
  if not text:
    return "unknown"
  has_ja = bool(JA_RE.search(text))
  has_en = bool(EN_RE.search(text))
  if has_ja and not has_en:
    return "ja"
  if has_en and not has_ja:
    return "en"
  if has_ja and has_en:
    return "ja" if len([ch for ch in text if JA_RE.match(ch)]) >= len([ch for ch in text if EN_RE.match(ch)]) else "en"
  if re.fullmatch(r"[\d\W_]+", text):
    return "unknown"
  return "unknown"


def classify_theme_term(term: str, *, bucket_hint: str | None = None) -> str:
  if bucket_hint:
    return bucket_hint
  normalized = _normalize_value(term).lower()
  for entry in iter_dictionary_entries():
    for candidate in list(entry.get("ja_terms", [])) + list(entry.get("en_terms", [])):
      if _normalize_value(candidate).lower() == normalized:
        return str(entry.get("bucket", "unclassified"))
  return "unclassified"


def extract_temporary_search_request_terms(search_request: Mapping[str, Any]) -> list[dict[str, Any]]:
  terms: list[dict[str, Any]] = []
  theme_text = str(search_request.get("theme", "") or "")

  def _append(value: str, *, source_field: str, bucket_hint: str | None = None) -> None:
    text = _normalize_value(value)
    if not text:
      return
    language = detect_term_language(text)
    bucket = classify_theme_term(text, bucket_hint=bucket_hint)
    terms.append(
      _term_record(
        value=text,
        language=language,
        bucket=bucket,
        provenance="explicit_request_field",
        source_field=source_field,
        source_text_span=text,
        mapping_method="direct_field_mapping",
        confidence="high",
        requires_user_review=False,
        accepted_for_theme=True,
      )
    )

  for item in parse_terms(str(search_request.get("keywords_ja", "") or "")):
    _append(item, source_field="keywords_ja", bucket_hint="core")
  for item in parse_terms(str(search_request.get("keywords_en", "") or "")):
    _append(item, source_field="keywords_en", bucket_hint="core")
  for item in parse_terms(str(search_request.get("exclude_keywords", "") or "")):
    _append(item, source_field="exclude_keywords", bucket_hint="exclude")
  exact = _normalize_value(str(search_request.get("exact_phrase", "") or ""))
  if exact:
    terms.append(
      _term_record(
        value=exact,
        language=detect_term_language(exact),
        bucket="exact_phrase",
        provenance="explicit_request_field",
        source_field="exact_phrase",
        source_text_span=exact,
        mapping_method="direct_field_mapping",
        confidence="high",
        requires_user_review=False,
        accepted_for_theme=True,
      )
    )
  for pub in parse_publication_numbers(str(search_request.get("seed_patent", "") or "")):
    terms.append(
      _term_record(
        value=pub,
        language="unknown",
        bucket="seed_publication",
        provenance="explicit_request_field",
        source_field="seed_patent",
        source_text_span=pub,
        mapping_method="direct_field_mapping",
        confidence="high",
        requires_user_review=False,
        accepted_for_theme=True,
      )
    )
  terms.extend(extract_exact_theme_concepts(theme_text))
  return terms


def extract_exact_theme_concepts(theme_text: str) -> list[dict[str, Any]]:
  text = str(theme_text or "")
  if not text.strip():
    return []
  found: list[dict[str, Any]] = []
  seen_spans: set[tuple[str, str]] = set()
  for entry in iter_dictionary_entries():
    bucket = str(entry.get("bucket", "unclassified"))
    canonical = str(entry.get("canonical_concept", ""))
    for ja_term in list(entry.get("ja_terms", []) or []):
      if ja_term and ja_term in text:
        key = (ja_term, bucket)
        if key in seen_spans:
          continue
        seen_spans.add(key)
        found.append(
          _term_record(
            value=ja_term,
            language="ja",
            bucket=bucket,
            provenance="exact_theme_text_match",
            source_field="theme",
            source_text_span=ja_term,
            mapping_method="exact_phrase_dictionary",
            confidence="high",
            requires_user_review=False,
            accepted_for_theme=True,
            canonical_concept=canonical,
          )
        )
    for en_term in list(entry.get("en_terms", []) or []):
      if en_term and en_term.lower() in text.lower():
        key = (en_term.lower(), bucket)
        if key in seen_spans:
          continue
        seen_spans.add(key)
        found.append(
          _term_record(
            value=en_term,
            language="en",
            bucket=bucket,
            provenance="exact_theme_text_match",
            source_field="theme",
            source_text_span=en_term,
            mapping_method="exact_phrase_dictionary",
            confidence="high",
            requires_user_review=False,
            accepted_for_theme=True,
            canonical_concept=canonical,
          )
        )
  return found


def build_canonical_term_suggestions(
  terms: Sequence[Mapping[str, Any]],
  *,
  theme_text: str,
) -> list[dict[str, Any]]:
  suggestions: list[dict[str, Any]] = []
  accepted_concepts = {
    str(item.get("canonical_concept", "") or item.get("normalized_value", ""))
    for item in terms
    if item.get("accepted_for_theme")
  }
  theme_lower = theme_text.lower()
  sizing_context = any(token in theme_text for token in ("サイジング", "sizing", "炭素繊維", "carbon fiber"))
  for entry in iter_dictionary_entries():
    if not entry.get("safe_alias"):
      continue
    canonical = str(entry.get("canonical_concept", ""))
    bucket = str(entry.get("bucket", "unclassified"))
    domain = str(entry.get("domain", "general"))
    if domain == "carbon_fiber_sizing" and not sizing_context:
      continue
    ja_present = any(ja and ja in theme_text for ja in list(entry.get("ja_terms", []) or []))
    for en_term in list(entry.get("en_terms", []) or []):
      if not en_term:
        continue
      if en_term.lower() in theme_lower:
        continue
      if any(
        _normalize_value(str(item.get("value", ""))).lower() == en_term.lower()
        for item in terms
        if item.get("accepted_for_theme")
      ):
        continue
      if bucket == "exclude" or ja_present or canonical in accepted_concepts:
        suggestions.append(
          _term_record(
            value=en_term,
            language="en",
            bucket=bucket,
            provenance="canonical_alias_suggestion",
            source_field="dictionary",
            source_text_span=en_term,
            mapping_method="canonical_alias_lookup",
            confidence="medium",
            requires_user_review=True,
            accepted_for_theme=False,
            canonical_concept=canonical,
          )
        )
  return suggestions


def _term_record(
  *,
  value: str,
  language: str,
  bucket: str,
  provenance: str,
  source_field: str,
  source_text_span: str,
  mapping_method: str,
  confidence: str,
  requires_user_review: bool,
  accepted_for_theme: bool,
  canonical_concept: str = "",
) -> dict[str, Any]:
  normalized = _normalize_value(value)
  return {
    "value": normalized,
    "normalized_value": normalized.lower(),
    "language": language,
    "semantic_bucket": bucket,
    "provenance": provenance,
    "source_field": source_field,
    "source_text_span": source_text_span,
    "mapping_method": mapping_method,
    "confidence": confidence,
    "requires_user_review": requires_user_review,
    "accepted_for_theme": accepted_for_theme,
    "canonical_concept": canonical_concept or _canonical_for_value(normalized),
  }


def _canonical_for_value(value: str) -> str:
  normalized = _normalize_value(value).lower()
  for canonical, aliases in CANONICAL_DEDUP_GROUPS.items():
    if normalized in {a.lower() for a in aliases}:
      return canonical
  for entry in iter_dictionary_entries():
    aliases = [str(x).lower() for x in list(entry.get("ja_terms", [])) + list(entry.get("en_terms", []))]
    if normalized in aliases:
      return str(entry.get("canonical_concept", ""))
  return normalized


def merge_terms_with_provenance(
  raw_terms: Sequence[Mapping[str, Any]],
  suggestions: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
  merged: list[dict[str, Any]] = []
  candidates: list[dict[str, Any]] = []
  seen: set[tuple[str, str, str]] = set()

  def _key(item: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
      str(item.get("semantic_bucket", "")),
      str(item.get("language", "")),
      str(item.get("normalized_value", "")),
    )

  for item in list(raw_terms) + list(suggestions):
    record = dict(item)
    if record.get("requires_user_review"):
      if _key(record) not in seen:
        candidates.append(record)
        seen.add(_key(record))
      continue
    if _key(record) in seen:
      continue
    merged.append(record)
    seen.add(_key(record))
  return merged, candidates


def _rebucket_by_language(terms: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
  rebucketed: list[dict[str, Any]] = []
  for item in terms:
    record = dict(item)
    value = str(record.get("value", "") or "")
    detected = detect_term_language(value)
    if detected == "unknown":
      record["language"] = "unknown"
    else:
      record["language"] = detected
      if record.get("mapping_method") == "direct_field_mapping" and detected != record.get("language"):
        record["mapping_method"] = "language_rebucket"
    rebucketed.append(record)
  return rebucketed


def build_keywords_from_terms(terms: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
  keywords = {
    "core_ja": [],
    "core_en": [],
    "use_ja": [],
    "use_en": [],
    "material_process_ja": [],
    "material_process_en": [],
    "exclude_ja": [],
    "exclude_en": [],
  }
  for item in terms:
    if not item.get("accepted_for_theme"):
      continue
    bucket = str(item.get("semantic_bucket", ""))
    language = str(item.get("language", ""))
    key = bucket_to_keyword_key(bucket, language)
    if not key:
      continue
    value = str(item.get("value", "") or "")
    if value and value not in keywords[key]:
      keywords[key].append(value)
  for key in keywords:
    keywords[key] = normalize_terms(keywords[key])
  return keywords


def suggest_concise_theme_name(theme_text: str, search_request: Mapping[str, Any] | None = None) -> str:
  req = dict(search_request or {})
  explicit = _normalize_value(str(req.get("short_title", "") or req.get("theme_short_name", "") or ""))
  if explicit:
    return explicit[:100]
  text = _normalize_value(theme_text).replace("\n", " ")
  if not text:
    return ""
  subject = text.split("について")[0].strip() if "について" in text else text
  if "サイジング剤" in subject and "用サイジング剤" not in subject:
    subject = subject.replace("のサイジング剤", "用サイジング剤")
  process_labels: list[str] = []
  for label, token in (("組成", "組成"), ("付与", "付与量"), ("乾燥条件", "乾燥条件")):
    if token in text and label not in process_labels:
      process_labels.append(label)
  if "乾燥" in text and "乾燥条件" not in process_labels and "乾燥" not in "・".join(process_labels):
    process_labels.append("乾燥")
  if process_labels and "について" in text:
    name = f"{subject}の{'・'.join(process_labels[:4])}"
  else:
    name = subject
  name = name.rstrip("について").strip()
  if len(name) > 60:
    return name[:57] + "..."
  return name


def validate_theme_name(name: str, *, description: str = "") -> list[dict[str, str]]:
  issues: list[dict[str, str]] = []
  cleaned = _normalize_value(name).replace("\n", " ")
  if not cleaned:
    issues.append({"severity": "error", "code": "theme_name_empty", "message": "テーマ名を入力してください。"})
  if len(cleaned) > 100:
    issues.append({"severity": "warning", "code": "theme_name_too_long", "message": "テーマ名が100文字を超えています。"})
  if len(cleaned) > 60:
    issues.append({"severity": "warning", "code": "theme_name_list_display", "message": "一覧表示で長すぎます。"})
  if description and cleaned == _normalize_value(description):
    issues.append({"severity": "warning", "code": "theme_name_equals_description", "message": "テーマ名が説明文と同一です。"})
  return issues


def validate_theme_draft_mapping(
  terms: Sequence[Mapping[str, Any]],
  keywords: Mapping[str, Sequence[str]],
  *,
  old_theme_keywords: Mapping[str, Sequence[str]] | None = None,
) -> list[dict[str, str]]:
  issues: list[dict[str, str]] = []
  for key, values in dict(keywords).items():
    expected_lang = "ja" if key.endswith("_ja") else "en" if key.endswith("_en") else ""
    for value in list(values or []):
      lang = detect_term_language(str(value))
      if expected_lang == "ja" and lang == "en":
        issues.append({"severity": "error", "code": "language_bucket_mismatch", "message": f"{value} in {key}"})
      if expected_lang == "en" and lang == "ja":
        issues.append({"severity": "error", "code": "language_bucket_mismatch", "message": f"{value} in {key}"})
      if lang == "unknown":
        issues.append({"severity": "warning", "code": "unknown_language", "message": str(value)})
  include_values = {
    str(v).lower()
    for bucket in ("core_ja", "core_en", "use_ja", "use_en", "material_process_ja", "material_process_en")
    for v in list(keywords.get(bucket, []) or [])
  }
  for value in list(keywords.get("exclude_ja", []) or []) + list(keywords.get("exclude_en", []) or []):
    if str(value).lower() in include_values:
      issues.append({"severity": "error", "code": "include_exclude_conflict", "message": str(value)})
  pending = sum(1 for item in terms if item.get("requires_user_review") and not item.get("accepted_for_theme"))
  if pending:
    issues.append({"severity": "info", "code": "alias_candidates_pending", "message": f"{pending} pending"})
  if old_theme_keywords:
    old_seeds = set(normalize_terms(list(old_theme_keywords.get("seed_publication_numbers", []) or [])))
    new_seeds = set(normalize_terms(list(keywords.get("seed_publication_numbers", []) or [])))
    if old_seeds & new_seeds:
      issues.append({"severity": "error", "code": "old_theme_contamination", "message": "seed overlap"})
  unclassified = [str(item.get("value", "")) for item in terms if str(item.get("semantic_bucket", "")) == "unclassified"]
  if unclassified:
    issues.append({"severity": "warning", "code": "unclassified_terms", "message": ", ".join(unclassified[:3])})
  return issues


def build_theme_draft_mapping_report(
  terms: Sequence[Mapping[str, Any]],
  candidates: Sequence[Mapping[str, Any]],
  validation: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
  return {
    "raw_term_count": len(terms),
    "ja_count": sum(1 for item in terms if item.get("language") == "ja"),
    "en_count": sum(1 for item in terms if item.get("language") == "en"),
    "unknown_count": sum(1 for item in terms if item.get("language") == "unknown"),
    "bucket_counts": _bucket_counts(terms),
    "exact_match_count": sum(1 for item in terms if item.get("provenance") == "exact_theme_text_match"),
    "alias_suggestion_count": len(candidates),
    "language_rebucket_count": sum(1 for item in terms if item.get("mapping_method") == "language_rebucket"),
    "duplicate_concept_count": _duplicate_concept_count(terms),
    "unclassified_count": sum(1 for item in terms if item.get("semantic_bucket") == "unclassified"),
    "blocking_error_count": sum(1 for item in validation if item.get("severity") == "error"),
    "warning_count": sum(1 for item in validation if item.get("severity") == "warning"),
    "old_theme_contamination_count": sum(1 for item in validation if item.get("code") == "old_theme_contamination"),
    "external_api_calls": 0,
    "cloud_writes": 0,
  }


def _bucket_counts(terms: Sequence[Mapping[str, Any]]) -> dict[str, int]:
  counts: dict[str, int] = {}
  for item in terms:
    bucket = str(item.get("semantic_bucket", "unclassified"))
    counts[bucket] = counts.get(bucket, 0) + 1
  return counts


def _duplicate_concept_count(terms: Sequence[Mapping[str, Any]]) -> int:
  canonicals = [str(item.get("canonical_concept", "") or item.get("normalized_value", "")) for item in terms]
  return max(0, len(canonicals) - len(set(canonicals)))


def apply_mapping_to_draft_payload(
  search_request: Mapping[str, Any],
  *,
  old_theme_keywords: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, Any]:
  theme_text = str(search_request.get("theme", "") or "")
  raw = extract_temporary_search_request_terms(search_request)
  raw = _rebucket_by_language(raw)
  suggestions = build_canonical_term_suggestions(raw, theme_text=theme_text)
  merged, candidates = merge_terms_with_provenance(raw, suggestions)
  keywords = build_keywords_from_terms(merged)
  validation = validate_theme_draft_mapping(merged, keywords, old_theme_keywords=old_theme_keywords)
  report = build_theme_draft_mapping_report(merged, candidates, validation)
  suggested_name = suggest_concise_theme_name(theme_text, search_request)
  return {
    "keywords": keywords,
    "mapping_terms": merged,
    "term_candidates": candidates,
    "mapping_validation": validation,
    "mapping_report": report,
    "suggested_name": suggested_name,
    "original_theme_text": theme_text,
    "exact_phrase": _normalize_value(str(search_request.get("exact_phrase", "") or "")),
    "seed_publication_numbers": parse_publication_numbers(str(search_request.get("seed_patent", "") or "")),
  }


def adopt_term_candidates(
  terms: Sequence[Mapping[str, Any]],
  candidates: Sequence[Mapping[str, Any]],
  adopted_values: Sequence[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
  adopted = {_normalize_value(value) for value in adopted_values}
  updated_terms = [dict(item) for item in terms]
  remaining: list[dict[str, Any]] = []
  for candidate in candidates:
    record = dict(candidate)
    if record.get("value") in adopted:
      record["accepted_for_theme"] = True
      record["requires_user_review"] = False
      record["provenance"] = "user_edited"
      record["mapping_method"] = "manual_edit"
      updated_terms.append(record)
    else:
      remaining.append(record)
  return updated_terms, remaining
