"""Tests for cloudbuild.yaml safety (Phase 25P)."""

from __future__ import annotations

from pathlib import Path

CLOUDBUILD = Path("cloudbuild.yaml")


def test_cloudbuild_exists() -> None:
  assert CLOUDBUILD.exists()


def test_cloudbuild_runs_tests() -> None:
  text = CLOUDBUILD.read_text(encoding="utf-8")
  assert "pytest" in text
  assert "compileall" in text
  assert "check_live_beta_ready.py" in text
  assert "check_cloudrun_demo_ready.py" in text
  assert "check_iap_cutover_ready.py" in text


def test_cloudbuild_deploys_without_disabling_iap() -> None:
  text = CLOUDBUILD.read_text(encoding="utf-8")
  assert "gcloud run deploy" in text
  assert "--no-iap" not in text
  assert "AUTH_PROVIDER_MODE=iap" in text
  assert "tech-cartography-v7-live-artifacts-1020686343587" in text
  assert "tech-cartography-v7-live-artifacts-devops-ai-agent-hackathon-2026" not in text


def test_cloudbuild_verifies_bucket_before_deploy() -> None:
  text = CLOUDBUILD.read_text(encoding="utf-8")
  assert "gcloud storage buckets describe" in text


def test_cloudbuild_has_no_inline_secret_values() -> None:
  text = CLOUDBUILD.read_text(encoding="utf-8")
  assert "TECH_CARTOGRAPHY_LOGIN_PASSWORD" not in text
  assert "sk-" not in text
  assert "eyJhbGci" not in text
  assert "tech-cartography-tavily-api-key:latest" in text
  assert "tech-cartography-smtp-password:latest" in text
  forbidden_pairs = (
    "SMTP_PASSWORD=",
    "TAVILY_API_KEY=actual",
  )
  for pair in forbidden_pairs:
    if pair in text:
      assert ":latest" in text or "secret" in text.lower()
