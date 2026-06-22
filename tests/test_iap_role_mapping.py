"""Tests for IAP role mapping (Phase 25N)."""

from __future__ import annotations

import pytest

from tech_cartography.runtime.iap_role_mapping import map_email_to_role, role_mapping_status


def test_admin_email_maps_to_admin(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("TECH_CARTOGRAPHY_ADMIN_EMAILS", "admin@example.com")
  result = map_email_to_role("Admin@Example.com")
  assert result["status"] == "ok"
  assert result["role"] == "admin"
  assert result["is_admin"] is True


def test_allowed_domain_maps_to_member(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("TECH_CARTOGRAPHY_ALLOWED_EMAIL_DOMAINS", "example.com")
  result = map_email_to_role("user@example.com")
  assert result["status"] == "ok"
  assert result["role"] == "member"


def test_unlisted_email_is_access_denied(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("TECH_CARTOGRAPHY_ADMIN_EMAILS", "admin@example.com")
  result = map_email_to_role("other@other.com")
  assert result["status"] == "access_denied"


def test_member_email_list(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("TECH_CARTOGRAPHY_MEMBER_EMAILS", "member01@example.com")
  result = map_email_to_role("member01@example.com")
  assert result["status"] == "ok"
  assert result["role"] == "member"


def test_role_mapping_status_counts(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("TECH_CARTOGRAPHY_ADMIN_EMAILS", "a@x.com,b@x.com")
  monkeypatch.setenv("TECH_CARTOGRAPHY_ALLOWED_EMAIL_DOMAINS", "corp.example")
  status = role_mapping_status()
  assert status["admin_email_count"] == 2
  assert status["allowed_domain_count"] == 1
