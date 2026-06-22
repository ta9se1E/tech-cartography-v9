"""Tests for AUTH_PROVIDER_MODE behavior (Phase 25N)."""

from __future__ import annotations

import json

import pytest

from tech_cartography.runtime.auth_provider_config import get_auth_provider_mode
from tech_cartography.runtime.iap_identity import resolve_iap_identity_from_headers
from tech_cartography.runtime.live_artifact_paths import get_live_run_history_dir
from tech_cartography.runtime.user_context import (
  AUTH_PROVIDER_GOOGLE_IAP,
  AUTH_PROVIDER_STREAMLIT_BASIC,
  build_user_context_from_basic_auth,
  build_user_context_from_iap_identity,
)
from tech_cartography.services.live_run_history import record_live_run


def test_auth_provider_mode_defaults_to_basic(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv("AUTH_PROVIDER_MODE", raising=False)
  assert get_auth_provider_mode() == "basic"


def test_basic_user_context_has_no_password() -> None:
  ctx = build_user_context_from_basic_auth(
    {"username": "admin", "role": "admin", "display_name": "admin"},
  )
  assert ctx["auth_provider"] == AUTH_PROVIDER_STREAMLIT_BASIC
  assert "password" not in json.dumps(ctx)


def test_iap_user_context_has_no_jwt() -> None:
  ctx = build_user_context_from_iap_identity(
    {
      "email": "user@example.com",
      "user_id": "user@example.com",
      "display_name": "user@example.com",
      "role": "member",
      "is_admin": False,
    },
  )
  assert ctx["auth_provider"] == AUTH_PROVIDER_GOOGLE_IAP
  assert ctx["user_id"] == "user@example.com"
  assert "jwt" not in json.dumps(ctx).lower()


def test_hybrid_prefers_iap_when_headers_present(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("AUTH_PROVIDER_MODE", "hybrid")
  monkeypatch.setenv("TECH_CARTOGRAPHY_ALLOWED_EMAIL_DOMAINS", "example.com")
  identity = resolve_iap_identity_from_headers(
    {"X-Goog-Authenticated-User-Email": "accounts.google.com:user@example.com"},
  )
  assert identity["status"] == "ok"
  assert identity["auth_provider"] == "google_iap"


def test_hybrid_iap_present_but_denied_no_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("AUTH_PROVIDER_MODE", "hybrid")
  monkeypatch.setenv("TECH_CARTOGRAPHY_ADMIN_EMAILS", "admin@example.com")
  identity = resolve_iap_identity_from_headers(
    {"X-Goog-Authenticated-User-Email": "accounts.google.com:other@other.com"},
  )
  assert identity["status"] == "access_denied"


def test_iap_mode_missing_headers(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("AUTH_PROVIDER_MODE", "iap")
  identity = resolve_iap_identity_from_headers({})
  assert identity["status"] == "missing"


def test_run_history_records_google_iap_provider(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv("TECH_CARTOGRAPHY_LOGIN_PASSWORD", raising=False)
  user = {
    "user_id": "user@example.com",
    "display_name": "user@example.com",
    "role": "member",
    "auth_provider": AUTH_PROVIDER_GOOGLE_IAP,
    "is_admin": False,
  }
  entry, saved, error = record_live_run(
    action_type="live_digest_preview",
    status="success",
    run_id="run-testiap01",
    user_context=user,
    project_root=tmp_path,
  )
  assert error is None
  assert entry is not None
  assert entry["auth_provider"] == AUTH_PROVIDER_GOOGLE_IAP
  assert saved is not None
  history_files = list(get_live_run_history_dir(tmp_path).glob("run_history_*.json"))
  blob = history_files[0].read_text(encoding="utf-8")
  assert "jwt" not in blob.lower()
  assert "password" not in blob.lower()
