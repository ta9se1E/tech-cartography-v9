"""Readiness checks for the v9 search plan UI wiring."""

from __future__ import annotations

import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))

from ui_v9.signal_watch_app import _build_search_plan_view, _default_search_plan_settings  # noqa: E402
from ui_v9.tabs import V9_TAB_LABELS  # noqa: E402


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
    "target_companies": ["東レ", "帝人"],
    "countries": ["JP", "US"],
    "source_types": ["patent", "paper", "web", "company"],
    "cadence": "weekly",
    "priority_rules": [],
    "notes": "",
  }


def main() -> int:
  errors: list[str] = []

  if len(V9_TAB_LABELS) != 6:
    errors.append("既存6タブ構成を維持できていません")

  view = _build_search_plan_view(_profile(), _default_search_plan_settings(_profile()), [])
  if "global_web_plan" not in view["plan"]:
    errors.append("検索計画viewに global_web_plan が含まれていません")
  if int(view["summary"].get("discovery_query_count", 0) or 0) <= 0:
    errors.append("discovery query数を集計できていません")

  tabs_source = (PROJECT_ROOT / "ui_v9" / "tabs.py").read_text(encoding="utf-8")
  app_source = (PROJECT_ROOT / "ui_v9" / "signal_watch_app.py").read_text(encoding="utf-8")
  required_labels = [
    "検索計画を再生成",
    "統合検索計画サマリー",
    "国・地域coverage",
    "Discovery query数",
    "Verification予定件数",
    "翻訳予定件数",
    "Provider routing",
    "validation結果",
    "手動query",
  ]
  if not all(label in tabs_source for label in required_labels):
    errors.append("情報源タブに必要な検索計画UIラベルが不足しています")
  if "STATE_SEARCH_PLAN_DATA" not in app_source or "_refresh_search_plan_state(" not in app_source:
    errors.append("検索計画state管理が signal_watch_app に接続されていません")

  banned_tokens = [
    "import requests",
    "import httpx",
    "from openai",
    "google.generativeai",
    "WebSearch(",
    "CallMcpTool(",
  ]
  if any(token in (tabs_source + "\n" + app_source) for token in banned_tokens):
    errors.append("UI層に外部API呼び出しが混入しています")

  at = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
  at.run()
  button_labels = [button.label for button in at.button]
  if "検索計画を再生成" not in button_labels:
    errors.append("テーマ設定タブに検索計画再生成ボタンがありません")
  if "情報源設定で検索計画を再生成" not in button_labels:
    errors.append("情報源タブに設定反映ボタンがありません")
  if not any(label in {"手動queryを追加", "Global Web手動queryを追加"} for label in button_labels):
    errors.append("手動query追加UIが見つかりません")
  if not any(radio.label == "データ投入モード" for radio in at.radio):
    errors.append("既存のデータ投入モードUIが失われています")
  if not any(uploader.label == "CSVファイル" for uploader in at.file_uploader):
    errors.append("CSV upload UI が失われています")
  if not any(uploader.label == "JSONファイル" for uploader in at.file_uploader):
    errors.append("JSON upload UI が失われています")

  if errors:
    print("[v9 search plan ui readiness] NG:")
    for error in errors:
      print(f"- {error}")
    return 1

  print("[v9 search plan ui readiness] OK: search plan UI wiring is ready.")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
