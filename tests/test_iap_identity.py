"""Tests for IAP identity adapter (Phase 25N)."""

from __future__ import annotations

import pytest

from tech_cartography.runtime.iap_identity import (
  parse_iap_user_email_header,
  resolve_iap_identity_from_headers,
  verify_iap_jwt_assertion,
)


def test_parse_iap_user_email_header_normalizes_prefix() -> None:
  assert parse_iap_user_email_header("accounts.google.com:Admin@Example.com") == "admin@example.com"


def test_resolve_missing_headers() -> None:
  identity = resolve_iap_identity_from_headers({})
  assert identity["status"] == "missing"
  assert identity.get("email") is None


def test_resolve_invalid_email_format() -> None:
  identity = resolve_iap_identity_from_headers(
    {"X-Goog-Authenticated-User-Email": "accounts.google.com:not-an-email"},
  )
  assert identity["status"] == "missing"


def test_resolve_ok_with_role_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("TECH_CARTOGRAPHY_ADMIN_EMAILS", "admin@example.com")
  identity = resolve_iap_identity_from_headers(
    {
      "X-Goog-Authenticated-User-Email": "accounts.google.com:admin@example.com",
      "X-Goog-Authenticated-User-Id": "accounts.google.com:12345",
    },
  )
  assert identity["status"] == "ok"
  assert identity["user_id"] == "admin@example.com"
  assert identity["role"] == "admin"
  assert identity["auth_provider"] == "google_iap"


def test_identity_does_not_include_jwt_body(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("TECH_CARTOGRAPHY_ADMIN_EMAILS", "user@example.com")
  identity = resolve_iap_identity_from_headers(
    {
      "X-Goog-Authenticated-User-Email": "accounts.google.com:user@example.com",
      "X-Goog-Iap-Jwt-Assertion": "eyJhbGciOiJSUzI1NiJ9.payload.signature",
    },
  )
  serialized = str(identity)
  assert "eyJhbGciOiJSUzI1NiJ9.payload.signature" not in serialized


def test_jwt_verify_off_has_production_caution(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv("IAP_JWT_VERIFY_MODE", raising=False)
  result = verify_iap_jwt_assertion("token")
  assert result["status"] == "skipped"
  assert result.get("production_caution")


def test_jwt_strict_failure_blocks_identity(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("IAP_JWT_VERIFY_MODE", "strict")
  monkeypatch.setenv("IAP_EXPECTED_AUDIENCE", "/projects/123/apps/abc")
  monkeypatch.setenv("TECH_CARTOGRAPHY_ADMIN_EMAILS", "user@example.com")

  def _fail(_token: str, _audience: str | None) -> dict:
    return {"ok": False, "error": "invalid", "message": "JWT verification failed: ValueError"}

  identity = resolve_iap_identity_from_headers(
    {
      "X-Goog-Authenticated-User-Email": "accounts.google.com:user@example.com",
      "X-Goog-Iap-Jwt-Assertion": "bad-token",
    },
    verify_fn=_fail,
  )
  assert identity["status"] == "invalid"


def test_jwt_strict_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("IAP_JWT_VERIFY_MODE", "strict")
  monkeypatch.setenv("IAP_EXPECTED_AUDIENCE", "/projects/123/apps/abc")
  result = verify_iap_jwt_assertion(None)
  assert result["status"] == "missing"
