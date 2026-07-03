"""Pure score explanation helpers for v9."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .watch_profile_schema import migrate_watch_profile

SIGNAL_TEXT_FIELDS = (
  "title",
  "summary",
  "tags",
  "why_read",
  "what_to_check",
  "next_action",
  "companies",
  "source_name",
)


def _contains_ascii_letter(value: str) -> bool:
  return any("A" <= char <= "Z" or "a" <= char <= "z" for char in value)


def _normalize_text_value(value: Any) -> list[str]:
  if value is None:
    return []
  if isinstance(value, list):
    return [str(item).strip() for item in value if str(item).strip()]
  text = str(value).strip()
  return [text] if text else []


def _score_level(score: float) -> str:
  if score >= 0.75:
    return "high"
  if score >= 0.55:
    return "medium"
  return "low"


def build_signal_text_blob(signal: dict[str, Any]) -> str:
  parts: list[str] = []
  for field in SIGNAL_TEXT_FIELDS:
    parts.extend(_normalize_text_value(signal.get(field)))
  return " ".join(parts)


def find_keyword_hits(text: str, keywords: list[str]) -> list[str]:
  hits: list[str] = []
  seen: set[str] = set()
  original_text = str(text or "")
  lowered_text = original_text.lower()

  for keyword in keywords:
    normalized = str(keyword or "").strip()
    if not normalized:
      continue

    is_ascii_keyword = _contains_ascii_letter(normalized)
    match = normalized.lower() in lowered_text if is_ascii_keyword else normalized in original_text
    if not match:
      continue

    dedupe_key = normalized.lower() if is_ascii_keyword else normalized
    if dedupe_key in seen:
      continue
    seen.add(dedupe_key)
    hits.append(normalized)

  return hits


def explain_action(signal: dict[str, Any]) -> str:
  action = str(signal.get("action", "") or "").strip()
  if action == "Read Now":
    return "スコアが高く、新規または注目度上昇のため、今週優先して読む候補です。"
  if action == "Watch":
    return "一定の関連性がありますが、今すぐ読む優先度は高くないため、継続監視候補です。"
  if action == "Ignore":
    return "関連性または優先度が低いため、今回は見送り候補です。"
  return "スコアと変化を踏まえて、補助的に確認する候補です。"


def explain_signal_score(
  signal: dict[str, Any],
  watch_profile: dict[str, Any],
) -> dict[str, Any]:
  migrated_profile = migrate_watch_profile(watch_profile or {})
  profile_keywords = dict(migrated_profile.get("keywords", {}))
  text_blob = build_signal_text_blob(signal)
  score = float(signal.get("score", 0.0) or 0.0)

  matched_keywords = {
    "core_en": find_keyword_hits(text_blob, list(profile_keywords.get("core_en", []))),
    "core_ja": find_keyword_hits(text_blob, list(profile_keywords.get("core_ja", []))),
    "application_en": find_keyword_hits(text_blob, list(profile_keywords.get("application_en", []))),
    "application_ja": find_keyword_hits(text_blob, list(profile_keywords.get("application_ja", []))),
    "material_process_en": find_keyword_hits(text_blob, list(profile_keywords.get("material_process_en", []))),
    "material_process_ja": find_keyword_hits(text_blob, list(profile_keywords.get("material_process_ja", []))),
    "target_companies": find_keyword_hits(text_blob, list(migrated_profile.get("target_companies", []))),
  }
  exclude_hits = {
    "exclude_en": find_keyword_hits(text_blob, list(profile_keywords.get("exclude_en", []))),
    "exclude_ja": find_keyword_hits(text_blob, list(profile_keywords.get("exclude_ja", []))),
  }

  score_reasons: list[str] = []
  negative_reasons: list[str] = []

  if matched_keywords["core_en"] or matched_keywords["core_ja"]:
    score_reasons.append("コアキーワードに一致しました。")
  if matched_keywords["application_en"] or matched_keywords["application_ja"]:
    score_reasons.append("用途キーワードに一致しました。")
  if matched_keywords["material_process_en"] or matched_keywords["material_process_ja"]:
    score_reasons.append("材料・プロセスキーワードに一致しました。")
  if matched_keywords["target_companies"]:
    score_reasons.append("注目企業に一致しました。")

  score_level = _score_level(score)
  if score_level == "high":
    score_reasons.append("高い関連スコアが設定されています。")
  elif score_level == "medium":
    score_reasons.append("中程度の関連スコアが設定されています。")
  else:
    score_reasons.append("関連スコアは低めです。")

  if exclude_hits["exclude_en"] or exclude_hits["exclude_ja"]:
    negative_reasons.append("除外キーワードに一致しています。")

  positive_hit_count = sum(len(values) for values in matched_keywords.values())
  if positive_hit_count == 0:
    negative_reasons.append("Watch Profileとの明確なキーワード一致がありません。")

  return {
    "score": score,
    "score_level": score_level,
    "matched_keywords": matched_keywords,
    "exclude_hits": exclude_hits,
    "score_reasons": score_reasons,
    "negative_reasons": negative_reasons,
    "action_reason": explain_action(signal),
  }


def attach_score_explanations(
  signals: list[dict[str, Any]],
  watch_profile: dict[str, Any],
) -> list[dict[str, Any]]:
  explained_signals: list[dict[str, Any]] = []
  for signal in signals:
    copied_signal = deepcopy(signal)
    copied_signal["score_explanation"] = explain_signal_score(copied_signal, watch_profile)
    explained_signals.append(copied_signal)
  return explained_signals
