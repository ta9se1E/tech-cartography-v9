"""Google IAP identity adapter — header parsing and optional JWT verification (Phase 25N)."""

from __future__ import annotations

import re
from typing import Any, Callable

from tech_cartography.runtime.auth_provider_config import (
  get_iap_expected_audience,
  get_iap_jwt_verify_mode,
)
from tech_cartography.runtime.iap_role_mapping import map_email_to_role, normalize_email

HEADER_USER_EMAIL = "X-Goog-Authenticated-User-Email"
HEADER_USER_ID = "X-Goog-Authenticated-User-Id"
HEADER_JWT_ASSERTION = "X-Goog-Iap-Jwt-Assertion"

_EMAIL_PREFIX_PATTERN = re.compile(r"^[^:]+:(.+)$")

_FORBIDDEN_OUTPUT_TOKENS = (
  "password",
  "smtp_password",
  "api_key",
  "jwt_assertion",
)


def _assert_safe_summary(text: str) -> None:
  lowered = text.lower()
  for token in _FORBIDDEN_OUTPUT_TOKENS:
    if token in lowered:
      raise ValueError(f"Refusing to expose sensitive token in IAP summary: {token}")


def parse_iap_user_email_header(raw_value: str | None) -> str | None:
  if not raw_value:
    return None
  value = str(raw_value).strip()
  if not value:
    return None
  match = _EMAIL_PREFIX_PATTERN.match(value)
  email = match.group(1).strip() if match else value
  normalized = normalize_email(email)
  if "@" not in normalized:
    return None
  return normalized


def parse_iap_user_id_header(raw_value: str | None) -> str | None:
  if not raw_value:
    return None
  value = str(raw_value).strip()
  if not value:
    return None
  match = _EMAIL_PREFIX_PATTERN.match(value)
  return (match.group(1).strip() if match else value) or None


def display_name_from_email(email: str) -> str:
  normalized = normalize_email(email)
  if "@" in normalized:
    return normalized
  return normalized or "iap-user"


def verify_iap_jwt_assertion(
  jwt_assertion: str | None,
  *,
  audience: str | None = None,
  verify_fn: Callable[[str, str | None], dict[str, Any]] | None = None,
) -> dict[str, Any]:
  """Verify IAP JWT when google-auth is available. Never returns JWT body."""
  mode = get_iap_jwt_verify_mode()
  if mode == "off":
    return {
      "status": "skipped",
      "verified": False,
      "message": "IAP_JWT_VERIFY_MODE=off",
      "production_caution": "Direct Cloud Run URL must not trust IAP headers without IAP/JWT protection.",
    }

  token = str(jwt_assertion or "").strip()
  if not token:
    if mode == "strict":
      return {"status": "missing", "verified": False, "message": "JWT assertion header is missing"}
    return {"status": "missing", "verified": False, "message": "JWT assertion not provided"}

  expected_audience = audience if audience is not None else get_iap_expected_audience()
  if mode == "strict" and not expected_audience:
    return {
      "status": "config_error",
      "verified": False,
      "message": "IAP_EXPECTED_AUDIENCE is required when IAP_JWT_VERIFY_MODE=strict",
    }

  verifier = verify_fn or _default_verify_iap_jwt
  result = verifier(token, expected_audience or None)
  if result.get("ok"):
    return {
      "status": "verified",
      "verified": True,
      "message": "JWT verification succeeded",
      "claims_summary": result.get("claims_summary") or {},
    }

  error = str(result.get("error") or "invalid")
  message = str(result.get("message") or "JWT verification failed")
  if error == "unavailable":
    if mode == "strict":
      return {"status": "unavailable", "verified": False, "message": message}
    return {"status": "warning", "verified": False, "message": message}

  if mode == "strict":
    return {"status": "invalid", "verified": False, "message": message}
  return {"status": "warning", "verified": False, "message": message}


def _default_verify_iap_jwt(jwt_assertion: str, audience: str | None) -> dict[str, Any]:
  try:
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token
  except ImportError:
    return {
      "ok": False,
      "error": "unavailable",
      "message": "google-auth is not installed for JWT verification",
    }

  try:
    decoded = id_token.verify_token(jwt_assertion, google_requests.Request(), audience=audience)
  except Exception as exc:
    return {"ok": False, "error": "invalid", "message": f"JWT verification failed: {type(exc).__name__}"}

  claims_summary = {
    "email": normalize_email(str(decoded.get("email") or "")) or None,
    "sub": str(decoded.get("sub") or "") or None,
  }
  serialized = str(claims_summary)
  _assert_safe_summary(serialized)
  return {"ok": True, "claims_summary": claims_summary}


def resolve_iap_identity_from_headers(
  headers: dict[str, str] | None,
  *,
  verify_fn: Callable[[str, str | None], dict[str, Any]] | None = None,
) -> dict[str, Any]:
  """Parse IAP headers into identity status. Never includes JWT/password secrets."""
  header_map = {str(k): str(v) for k, v in (headers or {}).items()}
  lowered = {k.lower(): v for k, v in header_map.items()}

  raw_email = lowered.get(HEADER_USER_EMAIL.lower())
  raw_user_id = lowered.get(HEADER_USER_ID.lower())
  raw_jwt = lowered.get(HEADER_JWT_ASSERTION.lower())

  email = parse_iap_user_email_header(raw_email)
  if not email:
    return {
      "status": "missing",
      "email": None,
      "user_id": None,
      "display_name": None,
      "role": None,
      "is_admin": False,
      "auth_provider": "google_iap",
      "message": "IAP user email header is missing or invalid",
      "jwt_verification": verify_iap_jwt_assertion(None, verify_fn=verify_fn),
    }

  user_id = normalize_email(email)
  display_name = display_name_from_email(email)
  role_result = map_email_to_role(email)
  jwt_result = verify_iap_jwt_assertion(raw_jwt, verify_fn=verify_fn)

  if role_result.get("status") == "access_denied":
    return {
      "status": "access_denied",
      "email": email,
      "user_id": user_id,
      "display_name": display_name,
      "role": None,
      "is_admin": False,
      "auth_provider": "google_iap",
      "message": str(role_result.get("message") or "access denied"),
      "role_mapping_status": role_result.get("status"),
      "jwt_verification": jwt_result,
    }

  if jwt_result.get("status") == "invalid" or jwt_result.get("status") == "config_error":
    return {
      "status": "invalid",
      "email": email,
      "user_id": user_id,
      "display_name": display_name,
      "role": None,
      "is_admin": False,
      "auth_provider": "google_iap",
      "message": str(jwt_result.get("message") or "JWT verification failed"),
      "role_mapping_status": role_result.get("status"),
      "jwt_verification": jwt_result,
    }

  if jwt_result.get("status") == "unavailable" and get_iap_jwt_verify_mode() == "strict":
    return {
      "status": "invalid",
      "email": email,
      "user_id": user_id,
      "display_name": display_name,
      "role": None,
      "is_admin": False,
      "auth_provider": "google_iap",
      "message": str(jwt_result.get("message") or "JWT verifier unavailable"),
      "role_mapping_status": role_result.get("status"),
      "jwt_verification": jwt_result,
    }

  warnings: list[str] = []
  if jwt_result.get("status") == "warning":
    warnings.append(str(jwt_result.get("message") or "JWT verification warning"))
  if jwt_result.get("production_caution"):
    warnings.append(str(jwt_result["production_caution"]))

  parsed_user_id = parse_iap_user_id_header(raw_user_id)
  return {
    "status": "ok",
    "email": email,
    "user_id": user_id,
    "iap_subject_id": parsed_user_id,
    "display_name": display_name,
    "role": role_result.get("role"),
    "is_admin": bool(role_result.get("is_admin")),
    "auth_provider": "google_iap",
    "message": str(role_result.get("message") or "IAP identity resolved"),
    "role_mapping_status": role_result.get("status"),
    "jwt_verification": jwt_result,
    "warnings": warnings,
  }


def get_request_headers_safe() -> dict[str, str]:
  """Read HTTP headers from Streamlit context when available."""
  try:
    import streamlit as st

    context = getattr(st, "context", None)
    headers = getattr(context, "headers", None) if context is not None else None
    if headers:
      return {str(k): str(v) for k, v in dict(headers).items()}
  except Exception:
    return {}
  return {}
