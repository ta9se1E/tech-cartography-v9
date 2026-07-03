"""CSV/JSON signal loaders for staged local data in v9."""

from __future__ import annotations

import csv
import json
from io import StringIO
from typing import Any

from .signal_scoring import classify_action, classify_status
from .signal_upload_schema import (
  REQUIRED_SIGNAL_FIELDS,
  map_signal_record_columns,
  normalize_list_field,
  normalize_signal_action,
  normalize_signal_status,
  normalize_signal_type,
)
from .watch_profile_schema import migrate_watch_profile


def _safe_float(value: Any) -> float | None:
  if value in {None, ""}:
    return None
  try:
    return float(value)
  except (TypeError, ValueError):
    return None


def _clip_score(value: float) -> float:
  return max(0.0, min(1.0, value))


def _build_default_why_read(record: dict[str, Any]) -> str:
  return f"アップロードされた{record.get('type', 'web')}情報で、監視テーマとの関連を確認しやすいためです。"


def _build_default_what_to_check(record: dict[str, Any]) -> str:
  return f"{record.get('title', 'この情報')} に含まれるキーワード、出典、公開日を確認してください。"


def _build_default_next_action(record: dict[str, Any]) -> str:
  return f"{record.get('title', 'この情報')} を読んで、Seed公報や監視テーマとの関係をメモしてください。"


def _build_row_label(row_index: int | None) -> str:
  return f"{row_index}行目" if row_index is not None else "入力行"


def load_signals_from_csv_text(csv_text: str) -> tuple[list[dict[str, Any]], list[str]]:
  reader = csv.DictReader(StringIO(csv_text))
  if not reader.fieldnames:
    return [], ["CSVヘッダーを読み取れませんでした。日本語または英語のカラム名を含むCSVを使用してください。"]
  rows = [dict(row) for row in reader]
  return normalize_signal_records(rows)


def load_signals_from_json_text(json_text: str) -> tuple[list[dict[str, Any]], list[str]]:
  try:
    payload = json.loads(json_text)
  except json.JSONDecodeError:
    return [], ["JSONの解析に失敗しました。list[dict] または {'signals': [...]} の形式を確認してください。"]
  if isinstance(payload, dict):
    records = payload.get("signals", [])
  else:
    records = payload
  if not isinstance(records, list):
    return [], ["JSONの形式が不正です。list[dict] または {'signals': [...]} を使用してください。"]
  filtered = [item for item in records if isinstance(item, dict)]
  warnings = []
  if len(filtered) != len(records):
    warnings.append("JSON内に辞書以外の要素が含まれていたため、一部をスキップしました。")
  normalized, record_warnings = normalize_signal_records(filtered)
  return normalized, warnings + record_warnings


def normalize_signal_record(record: dict[str, Any], row_index: int | None = None) -> tuple[dict[str, Any] | None, list[str]]:
  mapped = map_signal_record_columns(record)
  warnings: list[str] = []
  row_label = _build_row_label(row_index)

  for field in REQUIRED_SIGNAL_FIELDS:
    if not str(mapped.get(field, "")).strip():
      warnings.append(f"{row_label}: 必須項目 `{field}` が不足しているため、この行を読み込みませんでした。")
      return None, warnings

  normalized_type, type_warnings = normalize_signal_type(mapped.get("type"))
  warnings.extend(f"{row_label}: {message}" for message in type_warnings)

  normalized: dict[str, Any] = {
    "id": str(mapped.get("id", "")).strip(),
    "title": str(mapped.get("title", "")).strip(),
    "type": normalized_type,
    "source_url": str(mapped.get("source_url", "") or "").strip(),
    "source_name": str(mapped.get("source_name", "") or "アップロードデータ").strip() or "アップロードデータ",
    "published_date": str(mapped.get("published_date", "") or "").strip(),
    "summary": str(mapped.get("summary", "") or "").strip(),
    "score": _safe_float(mapped.get("score")),
    "previous_score": _safe_float(mapped.get("previous_score")),
    "status": normalize_signal_status(mapped.get("status")),
    "action": normalize_signal_action(mapped.get("action")),
    "why_read": str(mapped.get("why_read", "") or "").strip(),
    "what_to_check": str(mapped.get("what_to_check", "") or "").strip(),
    "next_action": str(mapped.get("next_action", "") or "").strip(),
    "tags": normalize_list_field(mapped.get("tags", [])),
    "companies": normalize_list_field(mapped.get("companies", [])),
    "language": str(mapped.get("language", "") or "").strip(),
    "memo": str(mapped.get("memo", "") or "").strip(),
  }

  if not normalized["why_read"]:
    normalized["why_read"] = _build_default_why_read(normalized)
  if not normalized["what_to_check"]:
    normalized["what_to_check"] = _build_default_what_to_check(normalized)
  if not normalized["next_action"]:
    normalized["next_action"] = _build_default_next_action(normalized)

  if mapped.get("status") not in {None, ""} and normalized["status"] is None:
    warnings.append(f"{row_label}: 変化の値 `{mapped.get('status')}` を解釈できなかったため、後で自動計算します。")
  if mapped.get("action") not in {None, ""} and normalized["action"] is None:
    warnings.append(f"{row_label}: 判断の値 `{mapped.get('action')}` を解釈できなかったため、後で自動計算します。")
  if mapped.get("score") not in {None, ""} and normalized["score"] is None:
    warnings.append(f"{row_label}: スコア `{mapped.get('score')}` を数値として解釈できなかったため、仮スコアを再計算します。")
  if mapped.get("previous_score") not in {None, ""} and normalized["previous_score"] is None:
    warnings.append(f"{row_label}: 前回スコア `{mapped.get('previous_score')}` を数値として解釈できませんでした。")

  return normalized, warnings


def normalize_signal_records(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
  normalized_records: list[dict[str, Any]] = []
  warnings: list[str] = []

  for index, record in enumerate(records, start=1):
    normalized, row_warnings = normalize_signal_record(record, row_index=index)
    warnings.extend(row_warnings)
    if normalized is None:
      continue
    if not normalized.get("id"):
      normalized["id"] = f"upload_{index:03d}"
    normalized_records.append(normalized)

  return normalized_records, warnings


def score_signal_with_profile(signal: dict[str, Any], watch_profile: dict[str, Any]) -> float:
  existing_score = _safe_float(signal.get("score"))
  if existing_score is not None:
    return _clip_score(existing_score)

  profile = migrate_watch_profile(watch_profile)
  keywords = profile["keywords"]
  tags = normalize_list_field(signal.get("tags", []))
  companies = normalize_list_field(signal.get("companies", []))

  searchable_parts = [
    str(signal.get("title", "")),
    str(signal.get("summary", "")),
    str(signal.get("why_read", "")),
    str(signal.get("what_to_check", "")),
    " ".join(tags),
    " ".join(companies),
    str(signal.get("source_name", "")),
  ]
  searchable = " ".join(searchable_parts).lower()
  companies_text = " ".join(companies).lower()

  score = 0.45

  core_terms = [term.lower() for term in keywords["core_en"] + keywords["core_ja"]]
  if any(term and term in searchable for term in core_terms):
    score += 0.20

  material_terms = [term.lower() for term in keywords["material_process_en"] + keywords["material_process_ja"]]
  if any(term and term in searchable for term in material_terms):
    score += 0.15

  application_terms = [term.lower() for term in keywords["application_en"] + keywords["application_ja"]]
  if any(term and term in searchable for term in application_terms):
    score += 0.10

  target_companies = [company.lower() for company in profile["target_companies"]]
  if any(company and (company in companies_text or company in searchable) for company in target_companies):
    score += 0.10

  if str(signal.get("type", "")).strip().lower() in set(profile["source_types"]):
    score += 0.05

  exclude_terms = [term.lower() for term in keywords["exclude_en"] + keywords["exclude_ja"]]
  if any(term and term in searchable for term in exclude_terms):
    score -= 0.30

  return _clip_score(score)


def enrich_signals_with_profile(signals: list[dict[str, Any]], watch_profile: dict[str, Any]) -> list[dict[str, Any]]:
  enriched: list[dict[str, Any]] = []
  for signal in signals:
    enriched_signal = dict(signal)
    enriched_signal["score"] = score_signal_with_profile(enriched_signal, watch_profile)
    status = enriched_signal.get("status") or classify_status(
      float(enriched_signal["score"]),
      enriched_signal.get("previous_score"),
    )
    enriched_signal["status"] = status
    action = enriched_signal.get("action") or classify_action(float(enriched_signal["score"]), status)
    enriched_signal["action"] = action
    enriched.append(enriched_signal)
  return enriched


def prepare_uploaded_signals(
  records: list[dict[str, Any]],
  watch_profile: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
  normalized_records, warnings = normalize_signal_records(records)
  enriched_records = enrich_signals_with_profile(normalized_records, watch_profile)
  sorted_records = sorted(
    enriched_records,
    key=lambda item: (
      float(item.get("score", 0.0)),
      str(item.get("published_date", "")),
      str(item.get("title", "")),
    ),
    reverse=True,
  )
  return sorted_records, warnings
