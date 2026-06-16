"""Japanese labels and explanations for Tech Cartography v7 UI."""

from __future__ import annotations

CLUSTER_LABELS: dict[str, tuple[str, str]] = {
  "core_manufacturing": (
    "PAN前駆体・耐炎化・炭化プロセス",
    "炭素繊維の作り方そのものに近い特許です。製造条件や炉、前駆体、炭化工程を確認します。",
  ),
  "surface_interface": (
    "表面処理・サイジング・界面接着",
    "樹脂との接着、含浸、界面強度に関わる特許です。複合材料用途で重要です。",
  ),
  "bundle_prepreg": (
    "炭素繊維束・tow・プリプレグ",
    "繊維束や中間材料に関する特許です。加工性や用途展開に関わります。",
  ),
  "property_defect_control": (
    "物性・欠陥・品質管理",
    "強度、弾性率、欠陥、ばらつきなど品質管理に関わる特許です。",
  ),
  "application_pressure_aerospace": (
    "耐圧・航空宇宙用途",
    "タンク、航空機部材など用途寄りの特許です。製造プロセス本体より周辺領域の可能性があります。",
  ),
  "company_watch": (
    "企業ウォッチ候補",
    "主要企業の出願動向を追う候補です。技術内容の深掘りは追加確認が必要です。",
  ),
  "other_related": (
    "関連その他",
    "炭素繊維に関連しうる候補ですが、中核度は低めです。",
  ),
}

EVIDENCE_LEVEL_LABELS: dict[str, tuple[str, str]] = {
  "metadata_only": (
    "書誌・要約のみ",
    "まだ請求項や実施例は確認していません。判断には追加確認が必要です。",
  ),
  "claims_available": (
    "請求項あり",
    "請求項テキストを取得済みです。ただし有効性や侵害判断ではありません。",
  ),
  "fulltext_partial": (
    "一部全文あり",
    "明細書の一部を確認できています。不足箇所は追加確認が必要です。",
  ),
  "fulltext_available": (
    "全文候補あり",
    "全文取得または手動確認の候補です。最終判断には専門家レビューが必要です。",
  ),
}

SOURCE_ROUTE_LABELS: dict[str, tuple[str, str]] = {
  "us_bigquery_fulltext_candidate": (
    "米国公報：全文取得候補",
    "BigQueryから請求項・明細書を取得できる可能性がある候補です。",
  ),
  "us_fulltext_candidate": (
    "米国公報：全文取得候補",
    "BigQueryから請求項・明細書を取得できる可能性がある候補です。",
  ),
  "manual_fulltext_required": (
    "PDFまたは手動全文確認が必要",
    "JP/EP/WO/CN/KRなどは全文取得できない場合があるため、PDFやGoogle Patents画面で確認します。",
  ),
  "manual_pdf_required": (
    "PDFまたは手動全文確認が必要",
    "JP/EP/WO/CN/KRなどは全文取得できない場合があるため、PDFやGoogle Patents画面で確認します。",
  ),
  "metadata_only": (
    "書誌・要約のみ",
    "まだ請求項や実施例は確認していません。判断には追加確認が必要です。",
  ),
}

STAGE_LABELS: dict[str, str] = {
  "search_strategy": "検索戦略の作成",
  "bigquery_light_retrieval": "特許候補の軽量検索（BigQuery）",
  "technology_clustering_ranking": "技術分類と優先順位付け",
  "fulltext_collection": "全文テキスト取得",
  "claim_element_extraction": "請求項要素の抽出",
  "openalex_paper_evidence": "論文による裏取り検索",
  "claim_paper_evidence_map": "特許×論文の根拠マップ",
  "technical_view_assessment": "技術の裏取り評価",
  "web_signal_mapping": "企業・Webシグナル整理",
  "business_view_assessment": "事業化・競合の見立て",
  "synthesis_report": "まとめレポート作成",
}

STAGE_STATUS_LABELS: dict[str, tuple[str, str]] = {
  "success": ("成功", "この段階は正常に完了しました。次の段階へ進めます。"),
  "skipped": ("スキップ", "設定または入力不足のため、この段階は実行されませんでした。"),
  "blocked": ("保留", "前段階の成果物がないため、まだ実行できません。推奨コマンドを確認してください。"),
  "failed": ("失敗", "エラーが発生しました。ログと入力を確認してください。"),
  "pending": ("未実行", "まだこの段階は開始されていません。"),
  "running": ("実行中", "現在この段階を処理しています。"),
}

SIGNAL_RELATION_LABELS: dict[str, str] = {
  "supports": "裏付け候補",
  "contradicts": "矛盾の可能性",
  "neutral": "参考情報",
  "unknown": "関係不明",
}

READER_ACTION_LABELS: dict[str, str] = {
  "read_fulltext": "全文を読む",
  "check_claims": "請求項を確認する",
  "compare_assignee": "出願人の動きを比較する",
  "seek_expert_review": "専門家レビューを依頼する",
  "monitor_only": "様子見",
  "likely_noise": "ノイズ候補として注意",
}

FULLTEXT_RETRIEVAL_STATUS_LABELS: dict[str, tuple[str, str]] = {
  "dry_run_only": ("ドライランのみ", "BigQuery本実行はしていません。計画と見積もりのみです。"),
  "retrieved": ("全文取得済み", "claims/description等を取得しました。追加確認は専門家レビュー推奨です。"),
  "cache_hit": ("キャッシュ利用", "以前取得した全文キャッシュを利用しました。"),
  "manual_required": ("手動確認が必要", "非米国公報など、PDF/Google Patentsでの確認が必要です。"),
  "not_found": ("全文が見つかりません", "BigQueryで該当全文が見つかりませんでした。手動確認を検討してください。"),
  "cost_guard_failed": ("コスト上限で停止", "maximum_bytes_billedを超える見積もりのため実行を停止しました。"),
  "query_error": ("クエリエラー", "BigQueryクエリでエラーが発生しました。"),
  "unsupported_country": ("非対応国", "米国公報以外はBigQuery全文取得の対象外です。手動ルートを使います。"),
}

EVIDENCE_LEVEL_JAPANESE: dict[str, str] = {
  "high_fulltext_evidence": "高：請求項・明細書・実施例/物性あり",
  "medium_fulltext_evidence": "中：請求項と明細書あり",
  "low_fulltext_evidence": "低：請求項または明細書のみ",
  "metadata_only": "書誌・要約のみ",
}

RECOMMENDED_NEXT_ACTION_LABELS: dict[str, tuple[str, str]] = {
  "manual_pdf_check": (
    "PDFで手動確認",
    "Google PatentsやPDFで請求項・明細書を確認してください。",
  ),
  "monitor_company_activity": (
    "企業動向を監視",
    "出願人の動きを定期的にウォッチしてください。",
  ),
  "compare_with_us_fulltext_candidate": (
    "米国候補と比較",
    "US Top5全文候補と内容を突き合わせてください。",
  ),
  "add_to_monthly_watch": (
    "月次ウォッチに追加",
    "次回更新時に再確認する候補として残します。",
  ),
  "expert_review_required": (
    "専門家レビュー推奨",
    "ノイズの可能性があるため、専門家の確認を推奨します。",
  ),
}


def _lookup(mapping: dict[str, str | tuple[str, str]], key: str, default_label: str) -> str:
  if not key or str(key).lower() in {"nan", "none", "unknown", "null"}:
    return default_label
  value = mapping.get(str(key).strip(), mapping.get(str(key).strip().lower()))
  if value is None:
    return default_label
  if isinstance(value, tuple):
    return value[0]
  return str(value)


def _lookup_explain(mapping: dict[str, str | tuple[str, str]], key: str, default_text: str) -> str:
  if not key or str(key).lower() in {"nan", "none", "unknown", "null"}:
    return default_text
  value = mapping.get(str(key).strip(), mapping.get(str(key).strip().lower()))
  if value is None:
    return default_text
  if isinstance(value, tuple):
    return value[1]
  return default_text


def translate_cluster_id(cluster_id: str) -> str:
  return _lookup(CLUSTER_LABELS, cluster_id, cluster_id or "未分類")


def translate_evidence_level(level: str) -> str:
  return _lookup(EVIDENCE_LEVEL_LABELS, level, level or "不明")


def translate_source_route(route: str) -> str:
  return _lookup(SOURCE_ROUTE_LABELS, route, route or "不明")


def translate_stage_id(stage_id: str) -> str:
  if not stage_id:
    return "不明な段階"
  return STAGE_LABELS.get(stage_id, stage_id)


def translate_stage_status(status: str) -> str:
  return _lookup(STAGE_STATUS_LABELS, status, status or "不明")


def translate_signal_relation(relation: str) -> str:
  if not relation:
    return "関係不明"
  return SIGNAL_RELATION_LABELS.get(relation, relation)


def translate_reader_action(action: str) -> str:
  if not action:
    return "次の確認を検討"
  return READER_ACTION_LABELS.get(action, action)


def explain_source_route(route: str) -> str:
  return _lookup_explain(
    SOURCE_ROUTE_LABELS,
    route,
    "全文確認ルートは追加確認が必要です。",
  )


def explain_evidence_level(level: str) -> str:
  return _lookup_explain(
    EVIDENCE_LEVEL_LABELS,
    level,
    "根拠レベルはまだ十分ではありません。",
  )


def explain_stage_status(status: str) -> str:
  return _lookup_explain(
    STAGE_STATUS_LABELS,
    status,
    "実行状況の詳細はログを確認してください。",
  )


def translate_recommended_next_action(action: str) -> str:
  return _lookup(RECOMMENDED_NEXT_ACTION_LABELS, action, action or "次の確認を検討")


def explain_recommended_next_action(action: str) -> str:
  return _lookup_explain(
    RECOMMENDED_NEXT_ACTION_LABELS,
    action,
    "追加確認の方法はケースごとに異なります。",
  )


def explain_strategic_watch() -> str:
  return (
    "戦略監視候補は、中国・欧州・日本など全文取得ルートが異なる重要特許を追跡するリストです。"
    "Top5全文候補と併せて確認してください。中国候補を除外しているわけではありません。"
  )


def explain_fulltext_priority_top5() -> str:
  return (
    "Top5全文候補は、BigQueryで請求項・明細書を取得しやすい米国公報を優先したリストです。"
    "世界の戦略的重要度ランキングではありません。"
    "中国・EP・JP等は Strategic Watch Candidates で別途確認してください。"
  )


def translate_fulltext_retrieval_status(status: str) -> str:
  return _lookup(FULLTEXT_RETRIEVAL_STATUS_LABELS, status, status or "不明")


def explain_fulltext_retrieval_status(status: str) -> str:
  return _lookup_explain(
    FULLTEXT_RETRIEVAL_STATUS_LABELS,
    status,
    "全文取得状況の詳細はレポートを確認してください。",
  )


def translate_evidence_coverage_level(level: str) -> str:
  return EVIDENCE_LEVEL_JAPANESE.get(level, level or "不明")
