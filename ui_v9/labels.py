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

CADENCE_LABELS_JA = {
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
