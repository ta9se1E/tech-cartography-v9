"""JSON-backed local user store (replaceable with SQLite/Cloud SQL later)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tech_cartography.users.user_profile import (
  UserProfile,
  build_user_id,
  create_user_profile,
  normalize_email,
  user_profile_from_dict,
  user_profile_to_dict,
)

DEFAULT_STORE_DIR = "outputs/user_store"
USERS_FILENAME = "users.json"


def _store_path(store_dir: str | None = None) -> Path:
  base = Path(store_dir or DEFAULT_STORE_DIR)
  base.mkdir(parents=True, exist_ok=True)
  return base / USERS_FILENAME


def load_users(store_dir: str | None = None) -> dict[str, dict[str, Any]]:
  path = _store_path(store_dir)
  if not path.exists():
    return {}
  data = json.loads(path.read_text(encoding="utf-8"))
  if not isinstance(data, dict):
    return {}
  return {str(k): v for k, v in data.items() if isinstance(v, dict)}


def save_users(users: dict[str, dict[str, Any]], store_dir: str | None = None) -> None:
  path = _store_path(store_dir)
  path.write_text(json.dumps(users, indent=2, ensure_ascii=False), encoding="utf-8")


def get_user_by_id(user_id: str, store_dir: str | None = None) -> dict[str, Any] | None:
  users = load_users(store_dir)
  row = users.get(user_id)
  return dict(row) if row else None


def get_user_by_email(email: str, store_dir: str | None = None) -> dict[str, Any] | None:
  user_id = build_user_id(email)
  return get_user_by_id(user_id, store_dir)


def get_or_create_user(
  email: str,
  display_name: str | None = None,
  company_name: str | None = None,
  store_dir: str | None = None,
) -> dict[str, Any]:
  users = load_users(store_dir)
  profile = create_user_profile(email, display_name=display_name, company_name=company_name)
  existing = users.get(profile.user_id)
  if existing:
    updated = dict(existing)
    if display_name and not updated.get("display_name"):
      updated["display_name"] = display_name.strip()
    if company_name and not updated.get("company_name"):
      updated["company_name"] = company_name.strip()
    users[profile.user_id] = updated
    save_users(users, store_dir)
    return updated
  row = user_profile_to_dict(profile)
  users[profile.user_id] = row
  save_users(users, store_dir)
  return row


def update_user_profile(user_id: str, updates: dict[str, Any], store_dir: str | None = None) -> dict[str, Any]:
  users = load_users(store_dir)
  if user_id not in users:
    raise KeyError(f"User not found: {user_id}")
  row = dict(users[user_id])
  row.update({k: v for k, v in updates.items() if v is not None or k in updates})
  from tech_cartography.users.user_profile import _utc_now_iso

  row["updated_at"] = _utc_now_iso()
  users[user_id] = row
  save_users(users, store_dir)
  return row


def set_last_run_id(user_id: str, run_id: str, store_dir: str | None = None) -> dict[str, Any]:
  return update_user_profile(user_id, {"last_run_id": run_id}, store_dir=store_dir)


def set_weekly_email_enabled(user_id: str, enabled: bool, store_dir: str | None = None) -> dict[str, Any]:
  return update_user_profile(user_id, {"weekly_email_enabled": bool(enabled)}, store_dir=store_dir)
