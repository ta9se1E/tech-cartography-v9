"""Readiness checks for v9 score explanation UI display."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))

from services_v9.score_explainer import attach_score_explanations  # noqa: E402
from ui_v9.labels import score_level_label_ja  # noqa: E402
from ui_v9.tabs import _merge_keyword_hits  # noqa: E402


def main() -> int:
  errors: list[str] = []

  if score_level_label_ja("high") != "高":
    errors.append("high を 高 に変換できません")
  if score_level_label_ja("medium") != "中":
    errors.append("medium を 中 に変換できません")
  if score_level_label_ja("low") != "低":
    errors.append("low を 低 に変換できません")

  signal = {
    "id": "signal_001",
    "title": "PAN precursor update",
    "summary": "前駆体と炭素繊維の凝固浴条件を扱う。",
    "tags": ["PAN", "carbon fiber", "void"],
    "why_read": "Demo Corp の比較に使える。",
    "what_to_check": "内部ボイドを確認する。",
    "next_action": "凝固浴条件を整理する。",
    "companies": ["Demo Corp"],
    "source_name": "Demo Source",
    "score": 0.82,
    "action": "Read Now",
  }
  profile = {
    "schema_version": "v9.2",
    "keywords": {
      "core_en": ["PAN"],
      "core_ja": ["前駆体"],
      "application_en": ["carbon fiber"],
      "application_ja": ["炭素繊維"],
      "material_process_en": ["void"],
      "material_process_ja": ["凝固浴"],
      "exclude_en": ["graphene"],
      "exclude_ja": ["汎用ニュース"],
    },
    "target_companies": ["Demo Corp"],
  }

  explained = attach_score_explanations([signal], profile)
  if "score_explanation" not in explained[0]:
    errors.append("score explanationをSignalへ付与できません")

  explanation = explained[0].get("score_explanation", {})
  core_hits = _merge_keyword_hits(explanation.get("matched_keywords"), ["core_en", "core_ja"])
  application_hits = _merge_keyword_hits(explanation.get("matched_keywords"), ["application_en", "application_ja"])
  material_hits = _merge_keyword_hits(explanation.get("matched_keywords"), ["material_process_en", "material_process_ja"])
  exclude_hits = _merge_keyword_hits(explanation.get("exclude_hits"), ["exclude_en", "exclude_ja"])
  if core_hits != ["PAN", "前駆体"]:
    errors.append("core_en / core_ja の統合に失敗しました")
  if application_hits != ["carbon fiber", "炭素繊維"]:
    errors.append("application_en / application_ja の統合に失敗しました")
  if material_hits != ["void", "凝固浴"]:
    errors.append("material_process_en / material_process_ja の統合に失敗しました")
  if exclude_hits != []:
    errors.append("exclude_en / exclude_ja の統合結果が不正です")

  if _merge_keyword_hits({}, ["core_en", "core_ja"]) != []:
    errors.append("空の説明dictでも表示整形が空listを返しません")

  if errors:
    print("[v9 score explanation ui readiness] NG:")
    for error in errors:
      print(f"- {error}")
    return 1

  print("[v9 score explanation ui readiness] OK: score explanation UI display is ready.")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
