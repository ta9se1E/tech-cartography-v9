"""Basic username/password auth from environment variables (Phase 25A, 25M)."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from dataclasses import dataclass
from typing import Any

REQUIRE_LOGIN_ENV = "REQUIRE_LOGIN"
USERS_JSON_ENV = "TECH_CARTOGRAPHY_USERS_JSON"
SIMPLE_LOGIN_USERNAME_ENV = "TECH_CARTOGRAPHY_LOGIN_USERNAME"
SIMPLE_LOGIN_PASSWORD_ENV = "TECH_CARTOGRAPHY_LOGIN_PASSWORD"
ENABLE_MULTI_USER_LOGIN_ENV = "ENABLE_MULTI_USER_LOGIN"

VALID_ROLES = frozenset({"member", "admin"})
PBKDF2_PREFIX = "pbkdf2_sha256$"
DEFAULT_PBKDF2_ITERATIONS = 260_000


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


def get_simple_login_username() -> str:
  return str(os.environ.get(SIMPLE_LOGIN_USERNAME_ENV, "") or "").strip()


def get_simple_login_password() -> str:
  return str(os.environ.get(SIMPLE_LOGIN_PASSWORD_ENV, "") or "")


def is_simple_login_configured() -> bool:
  return bool(get_simple_login_username()) and bool(get_simple_login_password())


def authenticate_simple(username: str, password: str) -> AuthUser | None:
  expected_username = get_simple_login_username()
  expected_password = get_simple_login_password()
  if not expected_username or not expected_password:
    return None
  candidate = str(username or "").strip()
  if not candidate or not password:
    return None
  if not secrets.compare_digest(candidate, expected_username):
    return None
  if not secrets.compare_digest(password, expected_password):
    return None
  return AuthUser(
    username=expected_username,
    role="admin",
    display_name=expected_username,
  )


def is_multi_user_login_enabled() -> bool:
  return _truthy(ENABLE_MULTI_USER_LOGIN_ENV, default=False)


def hash_password_pbkdf2(password: str, *, iterations: int = DEFAULT_PBKDF2_ITERATIONS) -> str:
  if not password:
    raise ValueError("password must not be empty")
  salt = secrets.token_bytes(16)
  digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
  salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii").rstrip("=")
  digest_b64 = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
  return f"{PBKDF2_PREFIX}{iterations}${salt_b64}${digest_b64}"


def verify_password_pbkdf2(password: str, password_hash: str) -> bool:
  if not password or not password_hash or not password_hash.startswith(PBKDF2_PREFIX):
    return False
  try:
    _, iterations_raw, salt_b64, digest_b64 = password_hash.split("$", 3)
    iterations = int(iterations_raw)
    salt = base64.urlsafe_b64decode(salt_b64 + "=" * (-len(salt_b64) % 4))
    expected = base64.urlsafe_b64decode(digest_b64 + "=" * (-len(digest_b64) % 4))
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return secrets.compare_digest(actual, expected)
  except (ValueError, TypeError):
    return False


def hash_password(password: str) -> str:
  import bcrypt

  if not password:
    raise ValueError("password must not be empty")
  return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
  if not password or not password_hash:
    return False
  if password_hash.startswith(PBKDF2_PREFIX):
    return verify_password_pbkdf2(password, password_hash)
  import bcrypt

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


def authenticate_json_users(username: str, password: str) -> AuthUser | None:
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


def authenticate_bcrypt_json(username: str, password: str) -> AuthUser | None:
  return authenticate_json_users(username, password)


def authenticate(username: str, password: str) -> AuthUser | None:
  if is_multi_user_login_enabled() and load_user_records():
    return authenticate_json_users(username, password)
  if is_simple_login_configured():
    return authenticate_simple(username, password)
  return authenticate_json_users(username, password)


def users_configured() -> bool:
  if is_multi_user_login_enabled():
    return bool(load_user_records())
  return is_simple_login_configured() or bool(load_user_records())


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
