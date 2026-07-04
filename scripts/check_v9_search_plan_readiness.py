"""Readiness checks for the v9 unified search plan core."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from services_v9.search_plan import (  # noqa: E402
  DEFAULT_SOURCE_LIMITS,
  DEFAULT_TOTAL_LIMIT,
  batch_terms,
  build_company_search_plan,
  build_paper_search_plan,
  build_patent_search_plan,
  build_unified_search_plan,
  build_web_search_plan,
  normalize_source_limits,
  summarize_search_plan_ja,
  validate_search_plan,
)


def _profile() -> dict:
  return {
    "schema_version": "v9.2",
    "theme_name": "PAN系炭素繊維前駆体の欠陥制御",
    "theme_description": "前駆体の表面欠陥と内部ボイドを監視する",
    "keywords": {
      "core_en": ["PAN carbon fiber precursor", "surface defect"],
      "core_ja": ["PAN系炭素繊維前駆体", "内部ボイド"],
      "application_en": ["high strength carbon fiber"],
      "application_ja": ["高強度炭素繊維"],
      "material_process_en": ["coagulation bath"],
      "material_process_ja": ["凝固浴"],
      "exclude_en": ["graphene"],
      "exclude_ja": ["汎用ニュース"],
    },
    "seed_publications": ["JP2022090764A"],
    "candidate_publications": ["JP2018141251A"],
    "target_companies": ["東レ", "Mitsubishi Chemical"],
    "source_types": ["patent", "paper", "web", "company"],
  }


def main() -> int:
  errors: list[str] = []

  if DEFAULT_TOTAL_LIMIT != 1000:
    errors.append("default total limit が1000ではありません")
  if DEFAULT_SOURCE_LIMITS != {"patent": 500, "paper": 300, "web": 100, "company": 100}:
    errors.append("default source limits が500/300/100/100ではありません")
  if sum(normalize_source_limits(1000).values()) != 1000:
    errors.append("source limits 合計が1000になりません")
  if normalize_source_limits(1000, {"patent": 70, "paper": 20, "web": 5, "company": 5}) != {
    "patent": 700,
    "paper": 200,
    "web": 50,
    "company": 50,
  }:
    errors.append("比率指定を件数へ変換できません")
  if batch_terms([" A ", "B", "A", "", "C"]) != [["A", "B", "C"]]:
    errors.append("batch_terms が重複除去・整形できません")

  profile = _profile()
  patent_plan = build_patent_search_plan(profile, 500)
  paper_plan = build_paper_search_plan(profile, 300)
  web_plan = build_web_search_plan(profile, 100)
  company_plan = build_company_search_plan(profile, 100)
  unified_plan = build_unified_search_plan(profile)

  if not any("PAN carbon fiber precursor" in query["query_text"] for query in patent_plan["queries"]):
    errors.append("英語キーワードからqueryを生成できません")
  if not any("PAN系炭素繊維前駆体" in query["query_text"] for query in patent_plan["queries"]):
    errors.append("日本語キーワードからqueryを生成できません")
  if "JP2022090764A" not in patent_plan["seed_publications"]:
    errors.append("Seed公報を保持できません")
  if "graphene" not in patent_plan["exclude_terms"] or "汎用ニュース" not in patent_plan["exclude_terms"]:
    errors.append("除外語を保持できません")
  if not patent_plan["queries"]:
    errors.append("特許検索計画を生成できません")
  if not paper_plan["queries"]:
    errors.append("論文検索計画を生成できません")
  if not web_plan["queries"]:
    errors.append("Web検索計画を生成できません")
  if not company_plan["queries"]:
    errors.append("企業検索計画を生成できません")
  if set(unified_plan["plans"].keys()) != {"patent", "paper", "web", "company"}:
    errors.append("unified plan を生成できません")
  if validate_search_plan(unified_plan):
    errors.append("validation が通りません")
  summary = summarize_search_plan_ja(unified_plan)
  if "統合検索計画" not in summary or "最大取得件数" not in summary:
    errors.append("日本語summaryを生成できません")
  if unified_plan["execution_enabled"] is not False:
    errors.append("execution_enabled が False ではありません")

  source_text = (PROJECT_ROOT / "services_v9" / "search_plan.py").read_text(encoding="utf-8")
  banned_tokens = [
    "import requests",
    "import httpx",
    "from openai",
    "google.generativeai",
    "WebSearch(",
    "CallMcpTool(",
  ]
  if any(token in source_text for token in banned_tokens):
    errors.append("外部APIなしで完結していません")

  if errors:
    print("[v9 search plan readiness] NG:")
    for error in errors:
      print(f"- {error}")
    return 1

  print("[v9 search plan readiness] OK: unified search plan core is ready.")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
