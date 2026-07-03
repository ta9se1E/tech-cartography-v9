"""Readiness checks for the v9 score explanation core."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))

from services_v9.score_explainer import (  # noqa: E402
  attach_score_explanations,
  explain_action,
  explain_signal_score,
  find_keyword_hits,
)


def main() -> int:
  errors: list[str] = []

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
  signal = {
    "title": "PAN precursor update",
    "summary": "前駆体と炭素繊維の凝固浴条件を扱う。grapheneではない。",
    "tags": ["carbon fiber", "void"],
    "why_read": "Demo Corp の計画確認に使える。",
    "what_to_check": "汎用ニュースではなく工程情報かを確認する。",
    "next_action": "凝固浴とvoidの関係を整理する。",
    "companies": ["Demo Corp"],
    "source_name": "Demo Source",
    "score": 0.82,
    "action": "Read Now",
  }

  english_hits = find_keyword_hits("PAN precursor", ["pan"])
  if english_hits != ["pan"]:
    errors.append("英語キーワード一致に失敗しました")

  japanese_hits = find_keyword_hits("前駆体の凝固浴評価", ["前駆体", "凝固浴"])
  if japanese_hits != ["前駆体", "凝固浴"]:
    errors.append("日本語キーワード一致に失敗しました")

  explanation = explain_signal_score(signal, profile)
  if explanation["exclude_hits"]["exclude_en"] != ["graphene"]:
    errors.append("除外キーワード一致に失敗しました")
  if explanation["score_level"] != "high":
    errors.append("score level 判定に失敗しました")
  if "今週優先して読む候補" not in explanation["action_reason"]:
    errors.append("action理由生成に失敗しました")

  multiple = attach_score_explanations([signal, {**signal, "score": 0.58, "action": "Watch"}], profile)
  if len(multiple) != 2 or any("score_explanation" not in item for item in multiple):
    errors.append("複数Signalへの説明付与に失敗しました")

  if "継続監視候補" not in explain_action({"action": "Watch"}):
    errors.append("Watch理由生成に失敗しました")

  if errors:
    print("[v9 score explainer readiness] NG:")
    for error in errors:
      print(f"- {error}")
    return 1

  print("[v9 score explainer readiness] OK: score explanation core is ready.")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
