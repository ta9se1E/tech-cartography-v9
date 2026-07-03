"""Japanese UI labels for the lightweight Tech Cartography v9 app."""

from __future__ import annotations

TYPE_LABELS_JA = {
  "patent": "特許",
  "paper": "論文",
  "web": "Web情報",
  "company": "企業情報",
}

STATUS_LABELS_JA = {
  "New": "新規",
  "Rising": "注目度上昇",
  "Dropped": "注目度低下",
  "Stable": "継続監視",
}

ACTION_LABELS_JA = {
  "Read Now": "今すぐ読む",
  "Watch": "監視する",
  "Ignore": "今回は見送る",
}

SOURCE_MODE_LABELS_JA = {
  "demo": "デモ",
  "staged": "準備中",
  "off": "停止中",
}

DATA_SOURCE_MODE_LABELS_JA = {
  "demo": "デモデータ",
  "csv": "CSVアップロード",
  "json": "JSONアップロード",
}

SCORE_LEVEL_LABELS_JA = {
  "high": "高",
  "medium": "中",
  "low": "低",
}

REVIEW_DECISION_LABELS_JA = {
  "採用": "採用",
  "保留": "保留",
  "見送り": "見送り",
}

REVIEW_PRIORITY_LABELS_JA = {
  1: "高",
  2: "中",
  3: "低",
}

REVIEW_PRIORITY_VALUES = {
  "高": 1,
  "中": 2,
  "低": 3,
}

REVIEW_COMMENT_LABEL_JA = "レビューコメント"

CADENCE_LABELS_JA = {
  "weekly": "毎週",
  "biweekly": "隔週",
  "monthly": "毎月",
  "Weekly": "毎週",
  "Biweekly": "隔週",
  "Monthly": "毎月",
}

V9_TAB_LABELS = [
  "テーマ設定",
  "情報源",
  "注目シグナル",
  "週次更新",
  "監視プロファイル",
  "ダイジェスト / エクスポート",
]

FORBIDDEN_UI_LABELS = [
  "Theme Setup",
  "Sources",
  "Top Signals",
  "Weekly Updates",
  "Watch Profile",
  "Digest / Export",
  "Claim Map",
  "Evidence Map",
  "Gap",
  "Strategic Brief",
  "PDF",
  "OCR",
  "Pipeline Doctor",
  "Quarantine",
  "Publication Identity Guard",
]


def type_label_ja(value: str) -> str:
  return TYPE_LABELS_JA.get(value, value)


def status_label_ja(value: str) -> str:
  return STATUS_LABELS_JA.get(value, value)


def action_label_ja(value: str) -> str:
  return ACTION_LABELS_JA.get(value, value)


def source_mode_label_ja(value: str) -> str:
  return SOURCE_MODE_LABELS_JA.get(value, value)


def data_source_mode_label_ja(value: str) -> str:
  return DATA_SOURCE_MODE_LABELS_JA.get(value, value)


def score_level_label_ja(value: str | None) -> str:
  normalized = str(value or "").strip()
  return SCORE_LEVEL_LABELS_JA.get(normalized, normalized)


def review_decision_label_ja(value: str | None) -> str:
  normalized = str(value or "").strip()
  return REVIEW_DECISION_LABELS_JA.get(normalized, normalized)


def review_priority_label_ja(value: int | str | None) -> str:
  try:
    normalized = int(value) if value not in {None, ""} else None
  except (TypeError, ValueError):
    normalized = None
  if normalized is None:
    return ""
  return REVIEW_PRIORITY_LABELS_JA.get(normalized, str(normalized))


def review_priority_value_ja(value: str | None) -> int:
  normalized = str(value or "").strip()
  return REVIEW_PRIORITY_VALUES.get(normalized, 2)


def cadence_label_ja(value: str) -> str:
  return CADENCE_LABELS_JA.get(value, value)


def bool_label_ja(value: bool) -> str:
  return "有効" if value else "無効"


def watch_profile_suggestion_label_ja(value: str) -> str:
  if value.startswith("add keyword:"):
    keyword = value.split(":", 1)[1].strip()
    return f"「{keyword}」を含めるキーワードに追加します。"
  if value.startswith("exclude noisy keyword:"):
    keyword = value.split(":", 1)[1].strip()
    return f"ノイズになりやすい「{keyword}」を除外キーワードに追加します。"
  if value.startswith("add company:"):
    company = value.split(":", 1)[1].strip()
    return f"注目企業に「{company}」を追加します。"
  if value.startswith("raise priority of source type:"):
    source_type = type_label_ja(value.split(":", 1)[1].strip())
    return f"情報源タイプ「{source_type}」の優先度を引き上げます。"
  if value.startswith("lower priority of irrelevant source:"):
    source_type = type_label_ja(value.split(":", 1)[1].strip())
    return f"関連度が低い情報源タイプ「{source_type}」の優先度を下げます。"
  if value.startswith("keep current watch profile:"):
    return "現在の監視プロファイルを維持して問題ありません。"
  return value
