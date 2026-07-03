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
      "source_type": "Patent",
      "mode": "demo",
      "top_n": min(counts.get("patent", 0), 5),
      "last_updated": latest_date,
      "note": "Local demo JSON only. No patent API call is executed.",
    },
    {
      "enabled": True,
      "source_type": "Paper",
      "mode": "demo",
      "top_n": min(counts.get("paper", 0), 5),
      "last_updated": latest_date,
      "note": "Local demo JSON only. OpenAlex is OFF in v9-0.",
    },
    {
      "enabled": True,
      "source_type": "Web",
      "mode": "staged",
      "top_n": min(counts.get("web", 0), 5),
      "last_updated": latest_date,
      "note": "Preview rows only. Web search is OFF in v9-0.",
    },
    {
      "enabled": True,
      "source_type": "Company",
      "mode": "staged",
      "top_n": min(counts.get("company", 0), 5),
      "last_updated": latest_date,
      "note": "Preview rows only. External company APIs are OFF.",
    },
  ]


def build_operation_status_rows() -> list[str]:
  return [
    "Patent: demo mode",
    "Paper: demo mode",
    "Web: staged mode",
    "Company: staged mode",
    "BigQuery: OFF",
    "OpenAlex: OFF",
    "Web Search: OFF",
    "Email Scheduler: OFF",
  ]
