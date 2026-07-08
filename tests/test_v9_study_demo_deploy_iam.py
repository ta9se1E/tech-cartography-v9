"""Tests for Study Demo deploy IAM preservation and rollback mutation markers."""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_SCRIPT = ROOT / "scripts" / "deploy_v9_study_demo.sh"
DEPLOY_WORKFLOW = ROOT / ".github" / "workflows" / "deploy-study-demo.yml"
STUDY_SERVICE = "tech-cartography-v9-study-demo"
PRODUCTION_SERVICE = "tech-cartography-v9-signal-watch"
BASH_BIN = os.environ.get("BASH", "/bin/bash")


def _deploy_script_text() -> str:
  return DEPLOY_SCRIPT.read_text(encoding="utf-8")


def _write_fake_gcloud(tmp_bin: Path, *, iam_mode: str) -> None:
  gcloud = tmp_bin / "gcloud"
  gcloud.write_text(
    f"""#!/usr/bin/env bash
set -euo pipefail
if [[ "${{1:-}}" == "run" && "${{2:-}}" == "services" && "${{3:-}}" == "get-iam-policy" ]]; then
  case "{iam_mode}" in
    public)
      echo '{{"bindings":[{{"role":"roles/run.invoker","members":["allUsers"]}}]}}'
      ;;
    missing)
      echo '{{"bindings":[]}}'
      ;;
    denied)
      echo "ERROR: PERMISSION_DENIED: run.services.getIamPolicy" >&2
      exit 1
      ;;
  esac
  exit 0
fi
if [[ "${{1:-}}" == "builds" && "${{2:-}}" == "submit" ]]; then
  if [[ -n "${{V9_DEPLOY_STATE_FILE:-}}" ]]; then
    printf '{{"mutation_started": true}}\\n' > "${{V9_DEPLOY_STATE_FILE}}"
  fi
  echo "fake-build-id"
  exit 0
fi
exit 0
""",
    encoding="utf-8",
  )
  gcloud.chmod(gcloud.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _run_check_public_access(tmp_bin: Path, iam_mode: str) -> subprocess.CompletedProcess[str]:
  _write_fake_gcloud(tmp_bin, iam_mode=iam_mode)
  return subprocess.run(
    [BASH_BIN, str(DEPLOY_SCRIPT), "--check-public-access"],
    cwd=ROOT,
    capture_output=True,
    text=True,
    env={
      "PATH": f"{tmp_bin}:/usr/bin:/bin",
      "HOME": str(tmp_bin),
      "SERVICE": STUDY_SERVICE,
      "V9_PYTHON_BIN": sys.executable,
    },
  )


def _parse_deploy_json(stdout: str) -> dict:
  start = stdout.find("{")
  if start == -1:
    raise AssertionError(f"deploy JSON not found in output: {stdout!r}")
  return json.loads(stdout[start:])


def test_deploy_script_has_no_iam_mutation_commands() -> None:
  text = _deploy_script_text()
  forbidden = (
    "--allow-unauthenticated",
    "--no-allow-unauthenticated",
    "add-iam-policy-binding",
    "remove-iam-policy-binding",
    "set-iam-policy",
    "publicize_service",
  )
  for token in forbidden:
    assert token not in text


def test_deploy_script_verifies_public_access_read_only() -> None:
  text = _deploy_script_text()
  assert "verify_public_access_readonly" in text
  assert "get-iam-policy" in text
  assert "Study Demo public access is not configured" in text
  apply_body = text.split("apply_deploy() {", 1)[1].split("case \"${MODE}\"", 1)[0]
  assert apply_body.index("verify_public_access_readonly") < apply_body.index("build_study_demo_image")


def test_deploy_result_documents_iam_preservation() -> None:
  text = _deploy_script_text()
  assert '"iam_policy_mutations": 0' in text
  assert '"public_access_verified": true' in text
  assert '"public_access_changed": false' in text


def test_public_policy_present_passes(tmp_path: Path) -> None:
  fake_bin = tmp_path / "bin"
  fake_bin.mkdir()
  completed = _run_check_public_access(fake_bin, iam_mode="public")
  assert completed.returncode == 0
  payload = _parse_deploy_json(completed.stdout)
  assert payload["status"] == "ok"
  assert payload["public_access_verified"] is True
  assert payload["iam_policy_mutations"] == 0


def test_public_policy_absent_fails_before_build(tmp_path: Path) -> None:
  fake_bin = tmp_path / "bin"
  fake_bin.mkdir()
  completed = _run_check_public_access(fake_bin, iam_mode="missing")
  assert completed.returncode == 1
  assert "Study Demo public access is not configured" in completed.stderr


def test_public_policy_check_permission_denied_fails(tmp_path: Path) -> None:
  fake_bin = tmp_path / "bin"
  fake_bin.mkdir()
  completed = _run_check_public_access(fake_bin, iam_mode="denied")
  assert completed.returncode == 1
  combined = (completed.stdout + completed.stderr).lower()
  assert "permission denied" in combined or "unable to read cloud run iam policy" in combined


def test_deploy_script_does_not_reference_production_service() -> None:
  text = _deploy_script_text()
  assert PRODUCTION_SERVICE not in text


def test_primary_smoke_is_unauthenticated() -> None:
  text = _deploy_script_text()
  apply_body = text.split("apply_deploy() {", 1)[1].split("case \"${MODE}\"", 1)[0]
  assert apply_body.index("verify_public_password_gate") < apply_body.index(
    "smoke_test_authenticated_optional"
  )


def test_authenticated_smoke_is_optional() -> None:
  text = _deploy_script_text()
  assert "smoke_test_authenticated_optional" in text
  assert "continuing with unauthenticated smoke only" in text
  assert "ERROR: authenticated smoke test returned empty body" not in text


def test_mutation_started_recorded_before_cloud_build() -> None:
  text = _deploy_script_text()
  build_body = text.split("build_study_demo_image() {", 1)[1].split("\n}\n", 1)[0]
  assert "record_deploy_mutation_started" in build_body
  assert build_body.index("record_deploy_mutation_started") < build_body.index("gcloud builds submit")


def test_workflow_rollback_uses_mutation_started() -> None:
  text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
  assert "apply_started=true" not in text
  assert "Read deploy mutation state" in text
  assert "steps.deploy_state.outputs.mutation_started == 'true'" in text
  assert "if: always()" in text
  assert "rollback_skipped: \\`true\\`" in text or "rollback_skipped: `true`" in text
  assert "rollback_executed" in text


def test_workflow_public_gate_failure_skips_rollback() -> None:
  text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
  assert re.search(
    r"Report deploy not started[\s\S]*?steps\.deploy_state\.outputs\.mutation_started != 'true'",
    text,
  )


def test_workflow_maintains_production_and_wif_guards() -> None:
  text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
  workflow = yaml.safe_load(text)
  triggers = workflow.get("on") or workflow[True]
  assert list(triggers.keys()) == ["workflow_dispatch"]
  assert PRODUCTION_SERVICE in text
  assert "production service deploy is forbidden" in text
  assert "ref: ${{ needs.preflight.outputs.release_tag }}" in text
  assert "workload_identity_provider" in text
  assert "environment: study-demo" in text
  assert "credentials_json" not in text


def test_deploy_script_does_not_require_run_admin() -> None:
  text = _deploy_script_text()
  assert "roles/run.admin" not in text
  assert "setIamPolicy" not in text


def test_state_file_absence_disables_rollback_in_workflow() -> None:
  reader = (ROOT / "scripts" / "read_v9_deploy_workflow_metadata.py").read_text(encoding="utf-8")
  assert "deploy state file" in reader
  assert "mutation_started" in reader


def test_fake_gcloud_build_marks_mutation_started(tmp_path: Path) -> None:
  fake_bin = tmp_path / "bin"
  fake_bin.mkdir()
  state_file = tmp_path / "v9-deploy-state.json"
  _write_fake_gcloud(fake_bin, iam_mode="public")
  subprocess.run(
    [str(fake_bin / "gcloud"), "builds", "submit"],
    check=True,
    env={"V9_DEPLOY_STATE_FILE": str(state_file), "PATH": f"{fake_bin}:/bin"},
  )
  payload = json.loads(state_file.read_text(encoding="utf-8"))
  assert payload["mutation_started"] is True
