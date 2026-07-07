"""Quality gate for deterministic research value synthesis."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from services_v9.research_value_synthesizer import contains_unsupported_assertion

SIMILARITY_THRESHOLD = 0.72


def _token_set(text: str) -> set[str]:
  return set(re.findall(r"[a-z0-9\u3040-\u30ff\u4e00-\u9fff]{2,}", text.lower()))


def text_similarity(left: str, right: str) -> float:
  a = _token_set(left)
  b = _token_set(right)
  if not a or not b:
    return 0.0
  return len(a & b) / len(a | b)


def _is_question(text: str) -> bool:
  stripped = text.strip()
  return stripped.endswith("？") or stripped.endswith("?")


def _is_single_word_question(text: str) -> bool:
  stripped = re.sub(r"[？?]", "", text.strip())
  return " " not in stripped and "、" not in stripped and len(stripped) <= 12


def validate_research_value_output(output: Mapping[str, Any]) -> list[str]:
  errors: list[str] = []
  role = dict(output.get("role", {}) or {})
  if not role.get("code") or not role.get("label_ja"):
    errors.append("missing_role")
  if not str(output.get("short_title_ja", "")).strip():
    errors.append("missing_short_title")
  research_value = str(output.get("research_value", "") or "")
  if len(research_value) < 120:
    errors.append("research_value_too_short")
  if len(research_value) > 320:
    errors.append("research_value_too_long")
  questions = list(output.get("verification_questions", []) or [])
  if not (3 <= len(questions) <= 5):
    errors.append("question_count_out_of_range")
  for question in questions:
    if not _is_question(str(question)):
      errors.append("question_not_interrogative")
    if _is_single_word_question(str(question)):
      errors.append("question_too_short")
  readout = str(output.get("readout_artifact", "") or "")
  if len(readout) < 20 or readout.strip() in {"本文を読む", "原典を読む"}:
    errors.append("readout_not_specific")
  if contains_unsupported_assertion(research_value):
    errors.append("unsupported_assertion")
  ranking = dict(output.get("ranking_basis", {}) or {})
  if research_value == str(ranking.get("summary", "")):
    errors.append("ranking_basis_not_separated")
  return errors


def validate_top3_bundle(bundle: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
  errors: list[str] = []
  role_codes: list[str] = []
  research_values: list[str] = []
  question_sets: list[str] = []
  unsupported_count = 0
  for item in bundle:
    output = dict(item.get("output", {}) or {})
    errors.extend(validate_research_value_output(output))
    role_codes.append(str(dict(output.get("role", {}) or {}).get("code", "")))
    research_values.append(str(output.get("research_value", "") or ""))
    question_sets.append("\n".join(list(output.get("verification_questions", []) or [])))
    if contains_unsupported_assertion(str(output.get("research_value", "") or "")):
      unsupported_count += 1
  role_diversity = len(set(code for code in role_codes if code))
  if role_diversity < 2 and len(bundle) >= 3:
    errors.append("insufficient_role_diversity")
  for i in range(len(research_values)):
    for j in range(i + 1, len(research_values)):
      if text_similarity(research_values[i], research_values[j]) > SIMILARITY_THRESHOLD:
        errors.append("research_value_too_similar")
      if text_similarity(question_sets[i], question_sets[j]) > SIMILARITY_THRESHOLD:
        errors.append("questions_too_similar")
  return {
    "status": "ok" if not errors else "blocked",
    "errors": sorted(set(errors)),
    "role_diversity_count": role_diversity,
    "unsupported_assertion_count": unsupported_count,
    "duplicate_text_similarity_ok": "research_value_too_similar" not in errors and "questions_too_similar" not in errors,
  }


__all__ = [
  "text_similarity",
  "validate_research_value_output",
  "validate_top3_bundle",
]
