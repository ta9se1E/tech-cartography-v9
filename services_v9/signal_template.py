"""Signal upload templates for v9 staged local operation."""

from __future__ import annotations

import json


def build_csv_template() -> str:
  return """タイトル,種別,出典URL,出典名,公開日,概要,スコア,前回スコア,なぜ読むべきか,確認すべき点,次の行動,タグ,企業,メモ
PAN系前駆体の内部ボイド低減に関するデモ特許,特許,https://example.com/demo-patent-1,Demo Patent Source,2026-07-01,PAN系前駆体の凝固条件と内部ボイドの関係を扱うデモデータです,,,前駆体欠陥と最終物性の関係を見るため,凝固浴条件とボイド評価方法を確認する,Seed公報との関連を確認する,"PAN,内部ボイド,凝固浴",Demo Materials,デモデータ
乾湿式紡糸条件と毛羽発生の関係を扱うデモ論文,論文,https://example.com/demo-paper-1,Demo Paper Source,2026-06-28,乾湿式紡糸のエアギャップ条件と毛羽発生傾向を扱うデモデータです,0.74,0.62,工程条件と品質安定化の関係を見るため,評価法と毛羽定義を確認する,既存の用途キーワードと突き合わせる,"乾湿式紡糸,毛羽,品質安定化",Demo Institute,デモデータ
前駆体品質改善投資に関するデモ企業情報,企業情報,https://example.com/demo-company-1,Demo Company Source,2026-06-25,前駆体品質改善ラインへの投資計画を扱うデモデータです,,,監視企業の動きとして共有価値があるため,投資対象工程と対象欠陥を確認する,次回の週次更新で継続監視する,"品質安定化,設備投資","Demo Corp",デモデータ
"""


def build_json_template() -> str:
  payload = {
    "signals": [
      {
        "title": "PAN系前駆体の内部ボイド低減に関するデモ特許",
        "type": "patent",
        "source_url": "https://example.com/demo-patent-1",
        "source_name": "Demo Patent Source",
        "published_date": "2026-07-01",
        "summary": "PAN系前駆体の凝固条件と内部ボイドの関係を扱うデモデータです。",
        "why_read": "前駆体欠陥と最終物性の関係を見るため",
        "what_to_check": "凝固浴条件とボイド評価方法を確認する",
        "next_action": "Seed公報との関連を確認する",
        "tags": ["PAN", "内部ボイド", "凝固浴"],
        "companies": ["Demo Materials"],
        "memo": "デモデータ"
      },
      {
        "title": "乾湿式紡糸条件と毛羽発生の関係を扱うデモ論文",
        "type": "paper",
        "source_url": "https://example.com/demo-paper-1",
        "source_name": "Demo Paper Source",
        "published_date": "2026-06-28",
        "summary": "乾湿式紡糸のエアギャップ条件と毛羽発生傾向を扱うデモデータです。",
        "score": 0.74,
        "previous_score": 0.62,
        "why_read": "工程条件と品質安定化の関係を見るため",
        "what_to_check": "評価法と毛羽定義を確認する",
        "next_action": "既存の用途キーワードと突き合わせる",
        "tags": ["乾湿式紡糸", "毛羽", "品質安定化"],
        "companies": ["Demo Institute"],
        "memo": "デモデータ"
      },
      {
        "title": "前駆体品質改善投資に関するデモ企業情報",
        "type": "company",
        "source_url": "https://example.com/demo-company-1",
        "source_name": "Demo Company Source",
        "published_date": "2026-06-25",
        "summary": "前駆体品質改善ラインへの投資計画を扱うデモデータです。",
        "why_read": "監視企業の動きとして共有価値があるため",
        "what_to_check": "投資対象工程と対象欠陥を確認する",
        "next_action": "次回の週次更新で継続監視する",
        "tags": ["品質安定化", "設備投資"],
        "companies": ["Demo Corp"],
        "memo": "デモデータ"
      }
    ]
  }
  return json.dumps(payload, ensure_ascii=False, indent=2)
