"""Basic username/password auth from environment variables (Phase 25A)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

REQUIRE_LOGIN_ENV = "REQUIRE_LOGIN"
USERS_JSON_ENV = "TECH_CARTOGRAPHY_USERS_JSON"

VALID_ROLES = frozenset({"member", "admin"})


@dataclass(frozen=True)
class AuthUser:
  username: str
  role: str
  display_name: str

  def to_session_dict(self) -> dict[str, Any]:
    return {
      "authenticated": True,
      "username": self.username,
      "role": self.role,
      "display_name": self.display_name,
    }


def _truthy(name: str, *, default: bool = False) -> bool:
  value = os.environ.get(name)
  if value is None or not str(value).strip():
    return default
  return str(value).strip().lower() in {"1", "true", "yes", "on"}


def is_login_required() -> bool:
  return _truthy(REQUIRE_LOGIN_ENV, default=False)


def hash_password(password: str) -> str:
  import bcrypt

  if not password:
    raise ValueError("password must not be empty")
  return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
  import bcrypt

  if not password or not password_hash:
    return False
  try:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
  except ValueError:
    return False


def load_user_records() -> list[dict[str, Any]]:
  raw = os.environ.get(USERS_JSON_ENV, "").strip()
  if not raw:
    return []
  try:
    data = json.loads(raw)
  except json.JSONDecodeError:
    return []
  if not isinstance(data, list):
    return []
  records: list[dict[str, Any]] = []
  for item in data:
    if not isinstance(item, dict):
      continue
    username = str(item.get("username") or "").strip()
    password_hash = str(item.get("password_hash") or "").strip()
    if not username or not password_hash:
      continue
    role = str(item.get("role") or "member").strip().lower()
    if role not in VALID_ROLES:
      role = "member"
    display_name = str(item.get("display_name") or username).strip() or username
    records.append(
      {
        "username": username,
        "password_hash": password_hash,
        "role": role,
        "display_name": display_name,
      },
    )
  return records


def authenticate(username: str, password: str) -> AuthUser | None:
  candidate = str(username or "").strip()
  if not candidate or not password:
    return None
  records = load_user_records()
  if not records:
    return None
  lowered = candidate.lower()
  for record in records:
    if str(record["username"]).lower() != lowered:
      continue
    if not verify_password(password, str(record["password_hash"])):
      return None
    return AuthUser(
      username=str(record["username"]),
      role=str(record["role"]),
      display_name=str(record["display_name"]),
    )
  return None


def users_configured() -> bool:
  return bool(load_user_records())


def production_features_allowed(
  *,
  login_required: bool,
  basic_authenticated: bool,
  has_email_user: bool,
) -> bool:
  if login_required:
    return basic_authenticated
  return has_email_user


def admin_features_allowed(
  *,
  login_required: bool,
  basic_authenticated: bool,
  auth_role: str,
  developer_mode_active: bool,
) -> bool:
  if login_required:
    return basic_authenticated and auth_role == "admin"
  return developer_mode_active
