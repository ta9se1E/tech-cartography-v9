"""Readiness checks for the v9 global web plan backend."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from services_v9.global_web_plan import (  # noqa: E402
  build_global_web_country_coverage,
  build_global_web_plan_validation_rows,
  build_global_web_search_plan,
  summarize_global_web_search_plan_ja,
  validate_global_web_search_plan,
)
from services_v9.global_web_plan_export import export_global_web_search_plan  # noqa: E402
from services_v9.global_web_plan_schema import (  # noqa: E402
  DEFAULT_GLOBAL_WEB_COUNTRY_CODES,
  load_global_web_country_profiles,
  validate_country_profiles,
)
from services_v9.search_plan import build_unified_search_plan  # noqa: E402


def _profile() -> dict:
  return {
    "schema_version": "v9.2",
    "theme_name": "PAN系炭素繊維前駆体の欠陥制御",
    "theme_description": "前駆体の表面欠陥と内部ボイドを監視する",
    "keywords": {
      "core_en": ["PAN carbon fiber precursor", "surface defect", "internal void"],
      "core_ja": ["PAN系炭素繊維前駆体", "表面欠陥", "内部ボイド"],
      "application_en": ["high strength carbon fiber", "CFRP"],
      "application_ja": ["高強度炭素繊維", "複合材補強"],
      "material_process_en": ["coagulation bath", "dry densification"],
      "material_process_ja": ["凝固浴", "乾燥緻密化"],
      "exclude_en": ["graphene"],
      "exclude_ja": ["汎用ニュース"],
    },
    "seed_publications": ["JP2022090764A"],
    "candidate_publications": ["JP2018141251A"],
    "target_companies": ["東レ", "帝人", "Mitsubishi Chemical", "Hexcel"],
    "source_types": ["patent", "paper", "web", "company"],
  }


def main() -> int:
  errors: list[str] = []

  profiles = load_global_web_country_profiles()
  if [profile["country_region_code"] for profile in profiles] != list(DEFAULT_GLOBAL_WEB_COUNTRY_CODES):
    errors.append("対象10カ国・地域プロファイルを読み込めません")
  if validate_country_profiles(profiles):
    errors.append("国別プロファイル検証が通りません")

  plan = build_global_web_search_plan(_profile(), 100, 100)
  if plan["execution_enabled"] is not False:
    errors.append("execution_enabled が False ではありません")
  if len(plan["queries"]) != 60:
    errors.append("10カ国×6intentのクエリが生成されていません")
  enabled_queries = [query for query in plan["queries"] if query["enabled"]]
  if len(enabled_queries) != 30:
    errors.append("初回 enabled query 数が約30件になっていません")
  if not any(query["country_region_code"] == "JP" and "研究開発" in query["query_local"] for query in plan["queries"]):
    errors.append("JP向け日本語queryを生成できません")
  if not any(query["country_region_code"] == "US" and "research development" in query["query_local"] for query in plan["queries"]):
    errors.append("英語圏queryを生成できません")
  if not any(query["local_query_generation_mode"] == "translation_pending" for query in plan["queries"]):
    errors.append("translation_pending query を生成できません")
  if validate_global_web_search_plan(plan):
    errors.append("global web plan validation が通りません")
  if len(build_global_web_country_coverage(plan)) != 10:
    errors.append("country coverage を生成できません")
  if build_global_web_plan_validation_rows(plan) != [{"status": "ok", "message": "validation passed"}]:
    errors.append("validation rows を生成できません")
  if "Global Web検索計画" not in summarize_global_web_search_plan_ja(plan):
    errors.append("日本語summaryを生成できません")

  unified_plan = build_unified_search_plan(_profile())
  if "global_web_plan" not in unified_plan:
    errors.append("unified search plan に global web plan が統合されていません")

  with tempfile.TemporaryDirectory() as tmp_dir_name:
    paths = export_global_web_search_plan(plan, Path(tmp_dir_name))
    if not all(path.exists() for path in paths.values()):
      errors.append("export関数が必要成果物を生成できません")
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    if len(payload.get("queries", [])) != 60:
      errors.append("exported JSON にクエリが含まれていません")

  source_text = (
    (PROJECT_ROOT / "services_v9" / "global_web_plan.py").read_text(encoding="utf-8")
    + "\n"
    + (PROJECT_ROOT / "services_v9" / "global_web_plan_export.py").read_text(encoding="utf-8")
  )
  banned_tokens = [
    "import requests",
    "import httpx",
    "from openai",
    "google.generativeai",
    "WebSearch(",
    "CallMcpTool(",
    "Tavily",
    "translate(",
  ]
  if any(token in source_text for token in banned_tokens):
    errors.append("外部APIなしで完結していません")

  if errors:
    print("[v9 global web plan readiness] NG:")
    for error in errors:
      print(f"- {error}")
    return 1

  print("[v9 global web plan readiness] OK: global web search plan backend is ready.")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
