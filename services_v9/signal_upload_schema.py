"""Schema helpers for CSV/JSON signal upload in v9."""

from __future__ import annotations

from typing import Any

from .watch_profile_schema import normalize_terms, parse_terms

REQUIRED_SIGNAL_FIELDS = [
  "title",
  "type",
]

OPTIONAL_SIGNAL_FIELDS = [
  "id",
  "source_url",
  "source_name",
  "published_date",
  "summary",
  "score",
  "previous_score",
  "status",
  "action",
  "why_read",
  "what_to_check",
  "next_action",
  "tags",
  "companies",
  "language",
  "memo",
]

COLUMN_ALIASES = {
  "id": ["id", "ID", "signal_id", "シグナルID"],
  "title": ["title", "タイトル", "名称", "件名"],
  "type": ["type", "種別", "情報種別", "source_type"],
  "source_url": ["source_url", "url", "URL", "出典URL", "リンク"],
  "source_name": ["source_name", "source", "出典名", "情報源"],
  "published_date": ["published_date", "date", "公開日", "発行日", "掲載日"],
  "summary": ["summary", "概要", "要約"],
  "score": ["score", "スコア", "評価点"],
  "previous_score": ["previous_score", "前回スコア"],
  "status": ["status", "変化", "状態"],
  "action": ["action", "判断", "対応"],
  "why_read": ["why_read", "なぜ読むべきか", "読む理由"],
  "what_to_check": ["what_to_check", "確認すべき点", "見るべき点"],
  "next_action": ["next_action", "次の行動", "次アクション"],
  "tags": ["tags", "タグ", "キーワード"],
  "companies": ["companies", "企業", "会社", "出願人", "著者所属"],
  "language": ["language", "言語"],
  "memo": ["memo", "メモ", "備考"],
}

TYPE_ALIASES = {
  "特許": "patent",
  "patent": "patent",
  "Patent": "patent",
  "PATENT": "patent",
  "論文": "paper",
  "paper": "paper",
  "Paper": "paper",
  "PAPER": "paper",
  "article": "paper",
  "Article": "paper",
  "ARTICLE": "paper",
  "Web情報": "web",
  "web": "web",
  "Web": "web",
  "WEB": "web",
  "news": "web",
  "News": "web",
  "NEWS": "web",
  "企業情報": "company",
  "company": "company",
  "Company": "company",
  "COMPANY": "company",
  "corporate": "company",
  "Corporate": "company",
  "CORPORATE": "company",
}

STATUS_ALIASES = {
  "新規": "New",
  "New": "New",
  "注目度上昇": "Rising",
  "Rising": "Rising",
  "注目度低下": "Dropped",
  "Dropped": "Dropped",
  "継続監視": "Stable",
  "Stable": "Stable",
}

def _normalize_column_name(value: str) -> str:
  return str(value or "").strip().lower().replace(" ", "_")


ACTION_ALIASES = {
  "今すぐ読む": "Read Now",
  "Read Now": "Read Now",
  "監視する": "Watch",
  "Watch": "Watch",
  "今回は見送る": "Ignore",
  "Ignore": "Ignore",
}


def _normalized_alias_map() -> dict[str, str]:
  alias_map: dict[str, str] = {}
  for canonical, aliases in COLUMN_ALIASES.items():
    for alias in aliases:
      alias_map[_normalize_column_name(alias)] = canonical
  return alias_map


ALIAS_LOOKUP = _normalized_alias_map()


def resolve_signal_column(column_name: str) -> str | None:
  return ALIAS_LOOKUP.get(_normalize_column_name(column_name))


def normalize_signal_type(value: Any) -> tuple[str, list[str]]:
  raw = str(value or "").strip()
  if not raw:
    return "web", ["種別が空のため、暫定的に Web情報 として扱いました。"]
  normalized = TYPE_ALIASES.get(raw)
  if normalized:
    return normalized, []
  return "web", [f"不明な種別「{raw}」を検出したため、暫定的に Web情報 として扱いました。"]


def normalize_signal_status(value: Any) -> str | None:
  raw = str(value or "").strip()
  if not raw:
    return None
  return STATUS_ALIASES.get(raw, None)


def normalize_signal_action(value: Any) -> str | None:
  raw = str(value or "").strip()
  if not raw:
    return None
  return ACTION_ALIASES.get(raw, None)


def normalize_list_field(value: Any) -> list[str]:
  if isinstance(value, list):
    return normalize_terms([str(item) for item in value])
  return parse_terms(str(value or ""))


def map_signal_record_columns(record: dict[str, Any]) -> dict[str, Any]:
  mapped: dict[str, Any] = {}
  for key, value in record.items():
    canonical = resolve_signal_column(str(key))
    if canonical is None:
      continue
    if canonical not in mapped or mapped[canonical] in {None, ""}:
      mapped[canonical] = value
  return mapped
