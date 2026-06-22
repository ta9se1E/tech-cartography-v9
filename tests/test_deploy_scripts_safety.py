"""Tests for deploy/rollback shell script safety (Phase 25P)."""

from __future__ import annotations

from pathlib import Path

DEPLOY = Path("scripts/deploy_live_safe.sh")
ROLLBACK = Path("scripts/rollback_live_to_basic.sh")


def test_deploy_script_exists() -> None:
  assert DEPLOY.exists()


def test_deploy_script_does_not_echo_secrets() -> None:
  text = DEPLOY.read_text(encoding="utf-8")
  assert "set -euo pipefail" in text
  assert "TC_LOGIN_PASSWORD" not in text
  assert "TECH_CARTOGRAPHY_LOGIN_PASSWORD" not in text
  assert "gcloud run services update" not in text
  assert "AUTH_PROVIDER_MODE=iap" in text
  assert "check_iap_cutover_ready.py" in text


def test_rollback_script_uses_read_s() -> None:
  text = ROLLBACK.read_text(encoding="utf-8")
  assert "read -rs" in text or "read -s" in text
  assert "unset TC_LOGIN_PASSWORD" in text
  assert "--no-iap" in text
  assert "AUTH_PROVIDER_MODE=basic" in text
  assert "LIVE_OUTPUTS_ROOT=/mnt/live_artifacts/outputs" in text


def test_rollback_script_does_not_echo_password() -> None:
  text = ROLLBACK.read_text(encoding="utf-8")
  assert 'echo "$TC_LOGIN_PASSWORD"' not in text
  assert 'echo "${TC_LOGIN_PASSWORD}"' not in text
