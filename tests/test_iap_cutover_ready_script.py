"""Tests for check_iap_cutover_ready.py (Phase 25O)."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts/check_iap_cutover_ready.py"


def test_script_exists() -> None:
  assert SCRIPT.exists()


def test_script_help() -> None:
  result = subprocess.run(
    [sys.executable, str(SCRIPT), "--help"],
    cwd=PROJECT_ROOT,
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0
  assert "--project" in result.stdout
  assert "--skip-gcloud" in result.stdout


def test_script_source_does_not_auto_enable_iap() -> None:
  text = SCRIPT.read_text(encoding="utf-8")
  assert "never enables" in text.lower()
  assert "_run_gcloud" in text
  assert "subprocess.run" in text
  # gcloud subprocess calls are read-only describe/list paths only
  assert '["run", "services", "update"' not in text


def _load_cutover_script_module():
  import importlib.util

  spec = importlib.util.spec_from_file_location("check_iap_cutover_ready_mod", SCRIPT)
  assert spec and spec.loader
  module = importlib.util.module_from_spec(spec)
  sys.modules[spec.name] = module
  spec.loader.exec_module(module)
  return module


def test_script_source_has_no_hardcoded_secrets() -> None:
  text = SCRIPT.read_text(encoding="utf-8")
  assert "sk-" not in text
  assert "test-password" not in text
  assert "eyJhbGci" not in text


def test_skip_gcloud_emits_warn_not_fail(capsys: pytest.CaptureFixture[str]) -> None:
  module = _load_cutover_script_module()

  code = module.main(["--skip-gcloud"])
  captured = capsys.readouterr().out
  assert code == 0
  assert "WARN: gcloud checks skipped" in captured
  assert "Rollback commands" in captured
  assert "Overall: WARN" in captured or "Overall: PASS" in captured
  for forbidden in ("test-password", "smtp-pass", "eyJhbG"):
    assert forbidden not in captured.lower()


def test_missing_remote_config_warns_with_mock_gcloud(capsys: pytest.CaptureFixture[str]) -> None:
  service_payload = {
    "status": {"url": "https://example.run.app"},
    "spec": {
      "template": {
        "spec": {
          "containers": [
            {
              "env": [
                {"name": "AUTH_PROVIDER_MODE", "value": "basic"},
              ],
            },
          ],
        },
      },
    },
  }

  def fake_gcloud(args: list[str], *, project: str | None = None) -> tuple[int, str, str]:
    del project
    joined = " ".join(args)
    if "projectNumber" in joined:
      return 0, "1020686343587", ""
    if "iap.googleapis.com" in joined and "list" in joined:
      return 0, "", ""
    if "describe" in joined and "json" in joined:
      return 0, json.dumps(service_payload), ""
    if "describe" in joined and "yaml" in joined:
      return 0, "iapEnabled: false", ""
    return 0, "", ""

  sys.path.insert(0, str(PROJECT_ROOT))
  module = _load_cutover_script_module()

  with patch.object(module, "_run_gcloud", side_effect=fake_gcloud):
    code = module.main(["--project", "test-project", "--region", "us-central1", "--service", "svc"])
  captured = capsys.readouterr().out
  assert code == 0
  assert "WARN: remote AUTH_PROVIDER_MODE=basic" in captured
  assert "WARN: IAP API enabled: no" in captured
  assert "1020686343587" in captured
  assert "gcp-sa-iap.iam.gserviceaccount.com" in captured
  assert "Overall: WARN" in captured


def test_print_report_rejects_jwt_like_output() -> None:
  module = _load_cutover_script_module()

  report = module.PreflightReport()
  report.add("PASS", "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U")
  with pytest.raises(ValueError):
    module.print_report(report)
