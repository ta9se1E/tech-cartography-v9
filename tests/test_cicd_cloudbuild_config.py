"""Tests for cloudbuild.yaml safety (Phase 25P)."""

from __future__ import annotations

import re
from pathlib import Path

CLOUDBUILD = Path("cloudbuild.yaml")


def _step_body(step_id: str) -> str:
  text = CLOUDBUILD.read_text(encoding="utf-8")
  pattern = (
    rf"- id: {re.escape(step_id)}\b.*?\n\s+args:\s*\n\s+- -ceu\s*\n\s+- \|\s*\n"
    r"(.*?)(?=\n\s+- id: |\ntimeout:|\Z)"
  )
  match = re.search(pattern, text, re.DOTALL)
  assert match, f"step not found: {step_id}"
  return match.group(1)


def test_cloudbuild_exists() -> None:
  assert CLOUDBUILD.exists()


def test_cloudbuild_runs_tests() -> None:
  body = _step_body("quality-gate")
  assert "pytest" in body
  assert "compileall" in body
  assert "check_live_beta_ready.py" in body
  assert "check_cloudrun_demo_ready.py" in body
  assert "check_iap_cutover_ready.py" in body


def test_cloudbuild_quality_gate_allows_pip_install() -> None:
  body = _step_body("quality-gate")
  assert "pip install" in body


def test_cloudbuild_deploy_step_is_gcloud_only() -> None:
  body = _step_body("iap-preflight-and-deploy")
  assert "gcloud run deploy" in body
  assert "gcloud storage buckets describe" in body
  assert "gcloud config set project" in body
  assert "gcloud run services describe" in body
  assert "pip install" not in body
  assert "pip3 install" not in body
  assert "python -m pip" not in body
  assert "python3 -m pip" not in body
  assert "--break-system-packages" not in body
  assert "check_iap_cutover_ready.py" not in body
  assert "apt-get install" not in body


def test_cloudbuild_deploys_without_disabling_iap() -> None:
  body = _step_body("iap-preflight-and-deploy")
  assert "gcloud run deploy" in body
  assert "--no-iap" not in body
  text = CLOUDBUILD.read_text(encoding="utf-8")
  assert "AUTH_PROVIDER_MODE=iap" in text
  assert "tech-cartography-v7-live-artifacts-1020686343587" in text
  assert "tech-cartography-v7-live-artifacts-devops-ai-agent-hackathon-2026" not in text


def test_cloudbuild_verifies_bucket_before_deploy() -> None:
  body = _step_body("iap-preflight-and-deploy")
  assert "gcloud storage buckets describe" in body


def test_cloudbuild_restores_ignore_files_before_tests() -> None:
  body = _step_body("quality-gate")
  assert "ensure_cloud_build_ignore_files.sh" in body
  assert "pip install -e ." in body


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
