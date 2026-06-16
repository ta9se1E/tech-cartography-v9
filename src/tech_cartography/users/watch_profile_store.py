"""Per-user watch profile storage."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_STORE_DIR = "outputs/user_store/watch_profiles"

CARBON_FIBER_THEME = "PAN系炭素繊維の中温域炭化条件最適化"

DEFAULT_KEYWORDS = [
  "PAN",
  "polyacrylonitrile",
  "precursor",
  "stabilization",
  "carbonization",
  "pre-oxidation",
  "surface treatment",
  "sizing",
  "tensile strength",
  "modulus",
]

DEFAULT_COMPANIES = [
  "Toray",
  "Teijin",
  "Mitsubishi Chemical",
  "Zhongfu Shenying",
  "Hyosung",
  "Hexcel",
  "SGL Carbon",
  "Solvay",
]

DEFAULT_COUNTRIES = ["US", "CN", "JP", "EP", "KR", "WO"]


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _profile_path(user_id: str, store_dir: str | None = None) -> Path:
  base = Path(store_dir or DEFAULT_STORE_DIR)
  base.mkdir(parents=True, exist_ok=True)
  return base / f"{user_id}.json"


def load_watch_profiles(user_id: str, store_dir: str | None = None) -> list[dict[str, Any]]:
  path = _profile_path(user_id, store_dir)
  if not path.exists():
    return []
  data = json.loads(path.read_text(encoding="utf-8"))
  if isinstance(data, list):
    return [dict(row) for row in data if isinstance(row, dict)]
  return []


def save_watch_profiles(
  user_id: str,
  profiles: list[dict[str, Any]],
  store_dir: str | None = None,
) -> None:
  path = _profile_path(user_id, store_dir)
  path.write_text(json.dumps(profiles, indent=2, ensure_ascii=False), encoding="utf-8")


def create_default_carbon_fiber_watch_profile(user_id: str) -> dict[str, Any]:
  now = _utc_now_iso()
  return {
    "watch_profile_id": str(uuid.uuid4()),
    "user_id": user_id,
    "theme": CARBON_FIBER_THEME,
    "keywords": list(DEFAULT_KEYWORDS),
    "companies": list(DEFAULT_COMPANIES),
    "countries": list(DEFAULT_COUNTRIES),
    "clusters": [],
    "weekly_email_enabled": False,
    "weekly_email_day": "monday",
    "weekly_email_time": "09:00",
    "last_run_id": None,
    "is_active": True,
    "created_at": now,
    "updated_at": now,
  }


def ensure_default_watch_profile(user_id: str, store_dir: str | None = None) -> list[dict[str, Any]]:
  profiles = load_watch_profiles(user_id, store_dir)
  if profiles:
    return profiles
  default = create_default_carbon_fiber_watch_profile(user_id)
  save_watch_profiles(user_id, [default], store_dir)
  return [default]


def get_active_watch_profile(user_id: str, store_dir: str | None = None) -> dict[str, Any]:
  profiles = ensure_default_watch_profile(user_id, store_dir)
  for row in profiles:
    if row.get("is_active"):
      return dict(row)
  return dict(profiles[0])


def update_watch_profile(
  user_id: str,
  watch_profile_id: str,
  updates: dict[str, Any],
  store_dir: str | None = None,
) -> dict[str, Any]:
  profiles = ensure_default_watch_profile(user_id, store_dir)
  updated_row: dict[str, Any] | None = None
  for index, row in enumerate(profiles):
    if str(row.get("watch_profile_id")) == str(watch_profile_id):
      merged = dict(row)
      merged.update(updates)
      merged["updated_at"] = _utc_now_iso()
      profiles[index] = merged
      updated_row = merged
      break
  if updated_row is None:
    raise KeyError(f"Watch profile not found: {watch_profile_id}")
  save_watch_profiles(user_id, profiles, store_dir)
  return updated_row
