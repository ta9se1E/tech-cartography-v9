"""Tests for Phase 25P CI/CD documentation."""

from __future__ import annotations

from pathlib import Path

DOCS = Path("docs/phase25p_cicd_cloud_build_deploy.md")


def test_cicd_docs_exist() -> None:
  assert DOCS.exists()


def test_cicd_docs_cover_rollback() -> None:
  text = DOCS.read_text(encoding="utf-8")
  assert "rollback_live_to_basic.sh" in text
  assert "--no-iap" in text
  assert "AUTH_PROVIDER_MODE=basic" in text


def test_cicd_docs_cover_iap_policy() -> None:
  text = DOCS.read_text(encoding="utf-8")
  assert "IAP" in text
  assert "--no-iap" in text
  assert "AUTH_PROVIDER_MODE=iap" in text


def test_cicd_docs_cover_cloud_build_trigger() -> None:
  text = DOCS.read_text(encoding="utf-8")
  assert "Cloud Build trigger" in text or "builds triggers create" in text
  assert "cloudbuild.yaml" in text


def test_cicd_docs_reference_phase25o() -> None:
  text = DOCS.read_text(encoding="utf-8")
  assert "Phase 25O" in text or "25O" in text
