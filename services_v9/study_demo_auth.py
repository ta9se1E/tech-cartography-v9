"""Shared-password authentication for the isolated v9 study demo service."""

from __future__ import annotations

import hmac
import time
from datetime import datetime
from typing import Mapping
from zoneinfo import ZoneInfo

from .study_demo_access import is_public_demo
from .study_demo_config import (
  get_study_demo_expires_at,
  get_study_demo_password,
  is_study_demo_expired,
  is_study_demo_mode,
  is_study_demo_password_configured,
)

SESSION_AUTHENTICATED_KEY = "v9_study_demo_authenticated"
SESSION_FAIL_COUNT_KEY = "v9_study_demo_fail_count"
SESSION_LAST_FAIL_AT_KEY = "v9_study_demo_last_fail_at"
SESSION_PASSWORD_INPUT_KEY = "v9_study_demo_password_input"

FAILURE_MESSAGE = "パスワードが正しくないか、入力できませんでした。"
EXPIRED_MESSAGE = "勉強会用環境の公開期間は終了しました。"
NOT_CONFIGURED_MESSAGE = "勉強会用環境は現在利用できません。管理者にお問い合わせください。"
COOLDOWN_SECONDS = 2
MAX_COOLDOWN_SECONDS = 30


class StudyDemoAuthError(Exception):
  """Base error for study demo authentication failures."""


class StudyDemoExpiredError(StudyDemoAuthError):
  pass


class StudyDemoNotConfiguredError(StudyDemoAuthError):
  pass


class StudyDemoCooldownError(StudyDemoAuthError):
  pass


def passwords_match(candidate: str, expected: str) -> bool:
  return hmac.compare_digest(
    candidate.encode("utf-8"),
    expected.encode("utf-8"),
  )


def verify_password(candidate: str, *, environ: Mapping[str, str] | None = None) -> bool:
  expected = get_study_demo_password(environ)
  if not expected:
    return False
  return passwords_match(str(candidate or ""), expected)


def validate_password_length(candidate: str, *, minimum: int = 16) -> bool:
  text = str(candidate or "")
  if not text.strip():
    return False
  return len(text) >= minimum


def ensure_study_demo_access_allowed(
  *,
  environ: Mapping[str, str] | None = None,
  now: datetime | None = None,
) -> None:
  if not is_study_demo_mode(environ):
    return
  # Public demo remains browsable after the study window ends (read-only).
  if is_public_demo(environ):
    return
  if is_study_demo_expired(environ=environ, now=now):
    raise StudyDemoExpiredError(EXPIRED_MESSAGE)
  if not is_study_demo_password_configured(environ):
    raise StudyDemoNotConfiguredError(NOT_CONFIGURED_MESSAGE)


def cooldown_remaining_seconds(session_state: Mapping[str, object]) -> float:
  fail_count = int(session_state.get(SESSION_FAIL_COUNT_KEY, 0) or 0)
  if fail_count <= 0:
    return 0.0
  last_fail_at = float(session_state.get(SESSION_LAST_FAIL_AT_KEY, 0.0) or 0.0)
  if last_fail_at <= 0:
    return 0.0
  delay = min(COOLDOWN_SECONDS * fail_count, MAX_COOLDOWN_SECONDS)
  elapsed = time.monotonic() - last_fail_at
  return max(0.0, delay - elapsed)


def register_failed_attempt(session_state: dict[str, object]) -> None:
  session_state[SESSION_AUTHENTICATED_KEY] = False
  session_state[SESSION_FAIL_COUNT_KEY] = int(session_state.get(SESSION_FAIL_COUNT_KEY, 0) or 0) + 1
  session_state[SESSION_LAST_FAIL_AT_KEY] = time.monotonic()
  session_state.pop(SESSION_PASSWORD_INPUT_KEY, None)


def register_successful_login(session_state: dict[str, object]) -> None:
  session_state[SESSION_AUTHENTICATED_KEY] = True
  session_state[SESSION_FAIL_COUNT_KEY] = 0
  session_state.pop(SESSION_LAST_FAIL_AT_KEY, None)
  session_state.pop(SESSION_PASSWORD_INPUT_KEY, None)


def clear_authentication(session_state: dict[str, object]) -> None:
  session_state[SESSION_AUTHENTICATED_KEY] = False
  session_state.pop(SESSION_PASSWORD_INPUT_KEY, None)


def is_authenticated(session_state: Mapping[str, object], *, environ: Mapping[str, str] | None = None) -> bool:
  if not is_study_demo_mode(environ):
    return True
  # Public demo skips login and expiry gate; write guards remain elsewhere.
  if is_public_demo(environ):
    return True
  if is_study_demo_expired(environ=environ):
    clear_authentication(dict(session_state))
    return False
  return bool(session_state.get(SESSION_AUTHENTICATED_KEY, False))


def format_expiry_jst(*, environ: Mapping[str, str] | None = None) -> str:
  expires_at = get_study_demo_expires_at(environ)
  if expires_at is None:
    return "未設定"
  jst = expires_at.astimezone(ZoneInfo("Asia/Tokyo"))
  return jst.strftime("%Y-%m-%d %H:%M JST")


__all__ = [
  "EXPIRED_MESSAGE",
  "FAILURE_MESSAGE",
  "NOT_CONFIGURED_MESSAGE",
  "SESSION_AUTHENTICATED_KEY",
  "SESSION_FAIL_COUNT_KEY",
  "SESSION_LAST_FAIL_AT_KEY",
  "SESSION_PASSWORD_INPUT_KEY",
  "StudyDemoAuthError",
  "StudyDemoCooldownError",
  "StudyDemoExpiredError",
  "StudyDemoNotConfiguredError",
  "clear_authentication",
  "cooldown_remaining_seconds",
  "ensure_study_demo_access_allowed",
  "format_expiry_jst",
  "is_authenticated",
  "passwords_match",
  "register_failed_attempt",
  "register_successful_login",
  "validate_password_length",
  "verify_password",
]
