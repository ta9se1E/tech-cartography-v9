"""Demo data loaders for the lightweight v9 signal watch app."""

from __future__ import annotations

import json
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

from .signal_models import Signal, WatchProfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = PROJECT_ROOT / "data" / "demo"
DEMO_SIGNALS_PATH = DEMO_DIR / "v9_demo_signals.json"
DEMO_WATCH_PROFILE_PATH = DEMO_DIR / "v9_demo_watch_profile.json"
SAMPLE_UPLOAD_CSV_PATH = DEMO_DIR / "v9_sample_upload_signals.csv"
SAMPLE_UPLOAD_JSON_PATH = DEMO_DIR / "v9_sample_upload_signals.json"


@lru_cache(maxsize=1)
def load_demo_signals_payload() -> list[dict[str, Any]]:
  with DEMO_SIGNALS_PATH.open("r", encoding="utf-8") as handle:
    return json.load(handle)


@lru_cache(maxsize=1)
def load_demo_watch_profile_payload() -> dict[str, Any]:
  with DEMO_WATCH_PROFILE_PATH.open("r", encoding="utf-8") as handle:
    return json.load(handle)


def load_demo_signals() -> list[Signal]:
  return [Signal.from_dict(item) for item in load_demo_signals_payload()]


def load_demo_watch_profile() -> WatchProfile:
  return WatchProfile.from_dict(load_demo_watch_profile_payload())


def build_source_rows(
  signals: list[Signal],
  *,
  data_source_mode: str = "demo",
) -> list[dict[str, Any]]:
  counts = Counter(signal.type for signal in signals)
  latest_date = max((signal.published_date for signal in signals), default="n/a")
  if data_source_mode == "retrieval_saved":
    patent_note = "取得済みartifactから再読込した候補を統合表示します。APIは実行しません。"
    paper_note = "取得済みartifactから再読込した候補を統合表示します。OpenAlexは再実行しません。"
    web_note = "取得済みartifactから再読込した候補を統合表示します。Web検索は再実行しません。"
    company_note = "取得済みartifactから再読込した候補を統合表示します。企業APIは再実行しません。"
    patent_mode = "loaded"
    paper_mode = "loaded"
    web_mode = "loaded"
    company_mode = "loaded"
  elif data_source_mode in {"csv", "json"}:
    patent_note = "アップロードされたデータだけを表示します。retrieval artifact は混在しません。"
    paper_note = patent_note
    web_note = patent_note
    company_note = patent_note
    patent_mode = "off"
    paper_mode = "off"
    web_mode = "off"
    company_mode = "off"
  else:
    patent_note = "ローカルのデモJSONのみを表示します。特許APIは実行しません。"
    paper_note = "ローカルのデモJSONのみを表示します。OpenAlexは停止中です。"
    web_note = "準備中のプレビュー表示です。Web検索は停止中です。"
    company_note = "準備中のプレビュー表示です。外部企業APIは停止中です。"
    patent_mode = "demo"
    paper_mode = "demo"
    web_mode = "staged"
    company_mode = "staged"
  return [
    {
      "enabled": True,
      "source_type": "patent",
      "mode": patent_mode,
      "top_n": min(counts.get("patent", 0), 10),
      "last_updated": latest_date,
      "note": patent_note,
    },
    {
      "enabled": True,
      "source_type": "paper",
      "mode": paper_mode,
      "top_n": min(counts.get("paper", 0), 10),
      "last_updated": latest_date,
      "note": paper_note,
    },
    {
      "enabled": True,
      "source_type": "web",
      "mode": web_mode,
      "top_n": min(counts.get("web", 0), 10),
      "last_updated": latest_date,
      "note": web_note,
    },
    {
      "enabled": True,
      "source_type": "company",
      "mode": company_mode,
      "top_n": min(counts.get("company", 0), 10),
      "last_updated": latest_date,
      "note": company_note,
    },
  ]


def build_operation_status_rows(
  *,
  bigquery_mode: str = "off",
  openalex_mode: str = "off",
  web_search_mode: str = "off",
  email_mode: str = "off",
) -> list[dict[str, str]]:
  return [
    {"label": "patent", "mode": "demo"},
    {"label": "paper", "mode": "demo"},
    {"label": "web", "mode": "staged"},
    {"label": "company", "mode": "staged"},
    {"label": "BigQuery", "mode": bigquery_mode},
    {"label": "OpenAlex", "mode": openalex_mode},
    {"label": "Web検索", "mode": web_search_mode},
    {"label": "メール配信", "mode": email_mode},
  ]
