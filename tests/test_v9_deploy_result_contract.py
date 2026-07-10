"""Tests for machine-readable deploy result/state contract and non-fatal reader."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_SCRIPT = ROOT / "scripts" / "deploy_v9_study_demo.sh"
DEPLOY_WORKFLOW = ROOT / ".github" / "workflows" / "deploy-study-demo.yml"
READER_SCRIPT = ROOT / "scripts" / "read_v9_deploy_workflow_metadata.py"
STUDY_SERVICE = "tech-cartography-v9-study-demo"
PRODUCTION_SERVICE = "tech-cartography-v9-signal-watch"
BASH_BIN = os.environ.get("BASH", "/bin/bash")


def _deploy_script_text() -> str:
  return DEPLOY_SCRIPT.read_text(encoding="utf-8")


def _workflow_text() -> str:
  return DEPLOY_WORKFLOW.read_text(encoding="utf-8")


def _workflow_steps() -> list[dict]:
  workflow = yaml.safe_load(_workflow_text())
  return workflow["jobs"]["deploy"]["steps"]


def _step(name: str) -> dict:
  for step in _workflow_steps():
    if step.get("name") == name:
      return step
  raise AssertionError(f"step not found: {name}")


def _run_reader(
  tmp_path: Path,
  *,
  state_payload: dict | None = None,
  result_payload: dict | None = None,
  state_raw: str | None = None,
  result_raw: str | None = None,
) -> subprocess.CompletedProcess[str]:
  state_file = tmp_path / "state.json"
  result_file = tmp_path / "result.json"
  if state_payload is not None:
    state_file.write_text(json.dumps(state_payload) + "\n", encoding="utf-8")
  elif state_raw is not None:
    state_file.write_text(state_raw, encoding="utf-8")
  if result_payload is not None:
    result_file.write_text(json.dumps(result_payload) + "\n", encoding="utf-8")
  elif result_raw is not None:
    result_file.write_text(result_raw, encoding="utf-8")
  env = os.environ.copy()
  env["V9_DEPLOY_STATE_FILE"] = str(state_file)
  env["V9_DEPLOY_RESULT_FILE"] = str(result_file)
  env["GITHUB_OUTPUT"] = str(tmp_path / "github_output.txt")
  return subprocess.run(
    [sys.executable, str(READER_SCRIPT)],
    cwd=ROOT,
    capture_output=True,
    text=True,
    env=env,
  )


def _github_output(tmp_path: Path) -> dict[str, str]:
  output_path = tmp_path / "github_output.txt"
  if not output_path.exists():
    return {}
  values: dict[str, str] = {}
  for line in output_path.read_text(encoding="utf-8").splitlines():
    if "=" in line:
      key, value = line.split("=", 1)
      values[key] = value
  return values


def _extract_bash_functions(*names: str) -> str:
  text = _deploy_script_text()
  chunks: list[str] = []
  for name in names:
    match = re.search(rf"^{re.escape(name)}\(\) \{{", text, flags=re.MULTILINE)
    if not match:
      raise AssertionError(f"function not found: {name}")
    start = match.start()
    depth = 0
    end = start
    for index in range(match.end() - 1, len(text)):
      char = text[index]
      if char == "{":
        depth += 1
      elif char == "}":
        depth -= 1
        if depth == 0:
          end = index + 1
          break
    chunks.append(text[start:end])
  return "\n\n".join(chunks)


def _run_write_deploy_result(tmp_path: Path, *, status: str = "ok") -> Path:
  result_file = tmp_path / "v9-deploy-result.json"
  script = f"""
set -euo pipefail
export TMPDIR="{tmp_path}"
SERVICE="{STUDY_SERVICE}"
V9_ACCESS_MODE="password"
DEPLOY_ACCESS_MODE="password"
V9_UI_MODE="simple"
RESULT_ACCESS_MODE="password"
RESULT_EXPECTED_ACCESS_MODE="password"
RESULT_REVISION_ACCESS_MODE="password"
RESULT_ACCESS_MODE_MATCH="true"
RESULT_UI_MODE="simple"
RESULT_REVISION_UI_MODE="simple"
DEPLOY_RESULT_FILE="{result_file}"
PY=({sys.executable})
{_extract_bash_functions("log", "write_deploy_result")}
write_deploy_result "{status}" true true true fake-build-123 true rev-00024-tvn
"""
  subprocess.run([BASH_BIN, "-c", script], cwd=ROOT, check=True, env={**os.environ, "TMPDIR": str(tmp_path)})
  return result_file


def test_deploy_script_defines_result_and_state_file_env_vars() -> None:
  text = _deploy_script_text()
  assert 'DEPLOY_RESULT_FILE="${V9_DEPLOY_RESULT_FILE' in text
  assert 'DEPLOY_STATE_FILE="${V9_DEPLOY_STATE_FILE' in text
  assert "write_deploy_result()" in text


def test_result_file_is_pure_json_despite_verbose_stdout(tmp_path: Path) -> None:
  result_file = _run_write_deploy_result(tmp_path)
  noisy = subprocess.run(
    [BASH_BIN, "-c", f'echo "selector log"; echo "pytest output"; cat "{result_file}"'],
    capture_output=True,
    text=True,
    check=True,
  )
  assert noisy.stdout.startswith("selector log")
  payload = json.loads(result_file.read_text(encoding="utf-8"))
  assert payload["status"] == "ok"
  assert payload["service"] == STUDY_SERVICE


def test_result_file_atomic_write_leaves_no_tmp(tmp_path: Path) -> None:
  result_file = _run_write_deploy_result(tmp_path)
  assert result_file.exists()
  assert not result_file.with_suffix(result_file.suffix + ".tmp").exists()
  assert not any(path.name.endswith(".tmp") for path in tmp_path.iterdir())


def test_result_file_not_empty_after_write(tmp_path: Path) -> None:
  result_file = _run_write_deploy_result(tmp_path)
  assert result_file.stat().st_size > 0


def test_reader_success_when_result_file_missing(tmp_path: Path) -> None:
  completed = _run_reader(tmp_path)
  assert completed.returncode == 0
  outputs = _github_output(tmp_path)
  assert outputs["result_parse_status"] == "missing"
  assert outputs["mutation_started"] == "false"


def test_reader_success_when_result_file_empty(tmp_path: Path) -> None:
  (tmp_path / "result.json").write_text("", encoding="utf-8")
  completed = _run_reader(tmp_path)
  assert completed.returncode == 0
  assert _github_output(tmp_path)["result_parse_status"] == "missing"


def test_reader_success_when_result_file_malformed(tmp_path: Path) -> None:
  completed = _run_reader(tmp_path, result_raw="not-json\n")
  assert completed.returncode == 0
  assert _github_output(tmp_path)["result_parse_status"] == "invalid"


def test_reader_success_with_valid_result_file(tmp_path: Path) -> None:
  completed = _run_reader(
    tmp_path,
    result_payload={
      "status": "ok",
      "public_access_verified": True,
      "iam_policy_mutations": 0,
    },
  )
  assert completed.returncode == 0
  outputs = _github_output(tmp_path)
  assert outputs["result_parse_status"] == "ok"
  assert outputs["public_access_verified"] == "true"
  assert outputs["iam_policy_mutations"] == "0"


def test_reader_success_when_state_file_missing(tmp_path: Path) -> None:
  completed = _run_reader(tmp_path)
  assert completed.returncode == 0
  assert _github_output(tmp_path)["mutation_started"] == "false"


def test_reader_success_when_state_file_malformed(tmp_path: Path) -> None:
  completed = _run_reader(tmp_path, state_raw="{broken")
  assert completed.returncode == 0
  outputs = _github_output(tmp_path)
  assert outputs["state_parse_status"] == "invalid"
  assert outputs["mutation_started"] == "false"


def test_reader_mutation_true_when_state_valid(tmp_path: Path) -> None:
  completed = _run_reader(tmp_path, state_payload={"mutation_started": True})
  assert completed.returncode == 0
  assert _github_output(tmp_path)["mutation_started"] == "true"


def test_reader_parse_failure_does_not_trigger_rollback() -> None:
  text = _workflow_text()
  reader = _step("Read deploy mutation state")
  assert reader.get("if") == "always()"
  assert "exit 0" in reader["run"]
  assert "deploy_result.json" not in text
  assert re.search(
    r"Rollback to previous revision[\s\S]*?if:\s*failure\(\)\s*&&\s*steps\.deploy_state\.outputs\.mutation_started == 'true'",
    text,
  )


def test_post_checks_run_after_apply_success_even_if_reader_warns() -> None:
  verify = _step("Verify deployed revision")
  readiness = _step("Post-deploy live-cloud readiness")
  smoke = _step("Unauthenticated smoke test")
  assert verify["if"] == "always() && steps.apply.outcome == 'success'"
  assert readiness["if"] == "always() && steps.apply.outcome == 'success'"
  assert smoke["if"] == "always() && steps.apply.outcome == 'success'"


def test_rollback_on_post_check_failure_with_mutation_started() -> None:
  text = _workflow_text()
  assert "steps.deploy_state.outputs.mutation_started == 'true'" in text
  rollback = _step("Rollback to previous revision")
  assert rollback["if"] == (
    "failure() && steps.deploy_state.outputs.mutation_started == 'true' "
    "&& steps.pre.outputs.previous_revision != ''"
  )


def test_rollback_on_apply_failure_with_mutation_started() -> None:
  text = _workflow_text()
  assert "Deploy apply" in text
  assert "failure() && steps.deploy_state.outputs.mutation_started == 'true'" in text


def test_precheck_failure_skips_rollback_when_mutation_false() -> None:
  text = _workflow_text()
  assert re.search(
    r"Report deploy not started[\s\S]*?steps\.deploy_state\.outputs\.mutation_started != 'true'",
    text,
  )


def test_result_file_excludes_credential_paths(tmp_path: Path) -> None:
  result_file = _run_write_deploy_result(tmp_path)
  payload_text = result_file.read_text(encoding="utf-8")
  forbidden = ("password_secret", "openalex_secret", "tavily_secret", "credentials", "service_account")
  for token in forbidden:
    assert token not in payload_text


def test_production_guard_preserved(tmp_path: Path) -> None:
  text = _workflow_text()
  assert PRODUCTION_SERVICE in text
  assert "production service deploy is forbidden" in text
  result_file = _run_write_deploy_result(tmp_path)
  payload = json.loads(result_file.read_text(encoding="utf-8"))
  assert payload["production_modifications"] is False


def test_iam_mutation_count_zero_in_result_contract(tmp_path: Path) -> None:
  result_file = _run_write_deploy_result(tmp_path)
  payload = json.loads(result_file.read_text(encoding="utf-8"))
  assert payload["iam_policy_mutations"] == 0
  assert payload["public_access_changed"] is False


def test_workflow_dispatch_only_and_validated_tag_checkout() -> None:
  workflow = yaml.safe_load(_workflow_text())
  triggers = workflow.get("on") or workflow[True]
  assert list(triggers.keys()) == ["workflow_dispatch"]
  assert "ref: ${{ needs.preflight.outputs.release_tag }}" in _workflow_text()


def test_workflow_separates_stdout_log_from_result_file() -> None:
  apply = _step("Deploy apply")
  run_text = apply["run"]
  assert "V9_DEPLOY_RESULT_FILE" in run_text
  assert "V9_DEPLOY_STATE_FILE" in run_text
  assert "deploy_result.json" not in run_text
  assert "v9-deploy.log" in run_text
  assert "read_v9_deploy_workflow_metadata.py" in _step("Read deploy mutation state")["run"]
