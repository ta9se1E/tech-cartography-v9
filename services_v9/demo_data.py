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


def build_source_rows(signals: list[Signal]) -> list[dict[str, Any]]:
  counts = Counter(signal.type for signal in signals)
  latest_date = max((signal.published_date for signal in signals), default="n/a")
  return [
    {
      "enabled": True,
      "source_type": "patent",
      "mode": "demo",
      "top_n": min(counts.get("patent", 0), 10),
      "last_updated": latest_date,
      "note": "ローカルのデモJSONのみを表示します。特許APIは実行しません。",
    },
    {
      "enabled": True,
      "source_type": "paper",
      "mode": "demo",
      "top_n": min(counts.get("paper", 0), 10),
      "last_updated": latest_date,
      "note": "ローカルのデモJSONのみを表示します。OpenAlexは停止中です。",
    },
    {
      "enabled": True,
      "source_type": "web",
      "mode": "staged",
      "top_n": min(counts.get("web", 0), 10),
      "last_updated": latest_date,
      "note": "準備中のプレビュー表示です。Web検索は停止中です。",
    },
    {
      "enabled": True,
      "source_type": "company",
      "mode": "staged",
      "top_n": min(counts.get("company", 0), 10),
      "last_updated": latest_date,
      "note": "準備中のプレビュー表示です。外部企業APIは停止中です。",
    },
  ]


def build_operation_status_rows() -> list[dict[str, str]]:
  return [
    {"label": "patent", "mode": "demo"},
    {"label": "paper", "mode": "demo"},
    {"label": "web", "mode": "staged"},
    {"label": "company", "mode": "staged"},
    {"label": "BigQuery", "mode": "off"},
    {"label": "OpenAlex", "mode": "off"},
    {"label": "Web検索", "mode": "off"},
    {"label": "メール配信", "mode": "off"},
  ]
