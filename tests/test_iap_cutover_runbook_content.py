"""Tests for Phase 25O IAP cutover runbook content."""

from __future__ import annotations

from pathlib import Path

RUNBOOK = Path("docs/phase25o_cloud_run_iap_cutover_runbook.md")


def test_runbook_exists() -> None:
  assert RUNBOOK.exists()


def test_runbook_has_rollback_procedure() -> None:
  text = RUNBOOK.read_text(encoding="utf-8")
  assert "ロールバック手順" in text
  assert "--no-iap" in text
  assert "AUTH_PROVIDER_MODE=basic" in text


def test_runbook_has_iap_iam_roles() -> None:
  text = RUNBOOK.read_text(encoding="utf-8")
  assert "roles/iap.httpsResourceAccessor" in text
  assert "roles/run.invoker" in text


def test_runbook_has_hybrid_cutover_steps() -> None:
  text = RUNBOOK.read_text(encoding="utf-8")
  assert "AUTH_PROVIDER_MODE=hybrid" in text
  assert "google_iap" in text
  assert "Phase 25N" in text


def test_runbook_does_not_store_secrets() -> None:
  text = RUNBOOK.read_text(encoding="utf-8")
  assert "eyJ" not in text
  assert "unset TC_LOGIN_PASSWORD" in text
