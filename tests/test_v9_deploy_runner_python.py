"""Tests for Study Demo deploy runner Python selection and rollback guards."""

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
BASH_BIN = os.environ.get("BASH", "/bin/bash")


def _parse_selector_json(stdout: str) -> dict:
  for line in reversed(stdout.splitlines()):
    line = line.strip()
    if line.startswith("{"):
      return json.loads(line)
  raise AssertionError(f"selector JSON not found in output: {stdout!r}")


def _run_deploy_selector(
  *,
  env: dict[str, str] | None = None,
  tmp_bin: Path | None = None,
) -> subprocess.CompletedProcess[str]:
  run_env = os.environ.copy()
  if env:
    run_env.update(env)
  if tmp_bin is not None:
    run_env["PATH"] = f"{tmp_bin}:{run_env.get('PATH', '')}"
  return subprocess.run(
    [BASH_BIN, str(DEPLOY_SCRIPT), "--print-python-selector"],
    cwd=ROOT,
    check=True,
    capture_output=True,
    text=True,
    env=run_env,
  )


def _write_fake_conda(tmp_bin: Path, *, env_available: bool) -> None:
  python_exec = sys.executable.replace("\\", "\\\\")
  conda = tmp_bin / "conda"
  conda.write_text(
    f"""#!/usr/bin/env bash
set -euo pipefail
if [[ "${{1:-}}" == "run" && "${{2:-}}" == "-n" ]]; then
  env_name="${{3:-}}"
  if [[ "${{env_name}}" == "2026hack" && "{str(env_available).lower()}" == "true" ]]; then
    shift 3
    if [[ "${{1:-}}" == "python" ]]; then
      shift
    fi
    exec "{python_exec}" "$@"
  fi
  echo "EnvironmentLocationNotFound: Not a conda environment: /usr/share/miniconda/envs/${{env_name}}" >&2
  exit 1
fi
if [[ "${{1:-}}" == "env" && "${{2:-}}" == "list" ]]; then
  if [[ "{str(env_available).lower()}" == "true" ]]; then
    echo '{{"envs":["/opt/miniconda3/envs/2026hack"]}}'
  else
    echo '{{"envs":["/opt/miniconda3"]}}'
  fi
  exit 0
fi
exit 0
""",
    encoding="utf-8",
  )
  conda.chmod(conda.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def test_deploy_script_bash_syntax() -> None:
  subprocess.run([BASH_BIN, "-n", str(DEPLOY_SCRIPT)], check=True)


def test_v9_python_bin_takes_priority(tmp_path: Path) -> None:
  custom = tmp_path / "custom-python"
  custom.write_text(
    f"""#!/usr/bin/env bash
exec {sys.executable} "$@"
""",
    encoding="utf-8",
  )
  custom.chmod(custom.stat().st_mode | stat.S_IXUSR)
  completed = _run_deploy_selector(env={"V9_PYTHON_BIN": str(custom)})
  payload = _parse_selector_json(completed.stdout)
  assert payload["source"] == "V9_PYTHON_BIN"
  assert payload["version"].startswith("3.11")


def test_system_python_used_when_conda_command_exists_without_env(tmp_path: Path) -> None:
  fake_bin = tmp_path / "bin"
  fake_bin.mkdir()
  _write_fake_conda(fake_bin, env_available=False)
  completed = _run_deploy_selector(tmp_bin=fake_bin)
  payload = _parse_selector_json(completed.stdout)
  assert payload["source"] in {"system-python", "system-python3", "V9_PYTHON_BIN"}
  assert payload["version"].startswith("3.11")
  assert "EnvironmentLocationNotFound" not in completed.stderr


def test_conda_env_used_when_probe_succeeds(tmp_path: Path) -> None:
  fake_bin = tmp_path / "bin"
  fake_bin.mkdir()
  _write_fake_conda(fake_bin, env_available=True)
  for name in ("python", "python3"):
    broken = fake_bin / name
    broken.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
    broken.chmod(broken.stat().st_mode | stat.S_IXUSR)
  run_env = os.environ.copy()
  run_env["PATH"] = str(fake_bin)
  run_env.pop("V9_PYTHON_BIN", None)
  run_env["CONDA_ENV"] = "2026hack"
  completed = subprocess.run(
    [BASH_BIN, str(DEPLOY_SCRIPT), "--print-python-selector"],
    cwd=ROOT,
    check=True,
    capture_output=True,
    text=True,
    env=run_env,
  )
  payload = _parse_selector_json(completed.stdout)
  assert payload["source"] in {"conda-run", "conda-env-direct"}
  assert payload["version"].startswith("3.11")


def test_conda_probe_failure_falls_back_to_system_python(tmp_path: Path) -> None:
  fake_bin = tmp_path / "bin"
  fake_bin.mkdir()
  _write_fake_conda(fake_bin, env_available=False)
  completed = _run_deploy_selector(tmp_bin=fake_bin)
  payload = _parse_selector_json(completed.stdout)
  assert payload["source"] in {"system-python", "system-python3"}
  assert "EnvironmentLocationNotFound" not in completed.stderr


def test_no_python_produces_explicit_failure(tmp_path: Path) -> None:
  fake_bin = tmp_path / "bin"
  fake_bin.mkdir()
  _write_fake_conda(fake_bin, env_available=False)
  run_env = {
    "PATH": str(fake_bin),
    "HOME": os.environ.get("HOME", "/tmp"),
    "CONDA_ENV": "missing-env-xyz",
  }
  completed = subprocess.run(
    [BASH_BIN, str(DEPLOY_SCRIPT), "--print-python-selector"],
    cwd=ROOT,
    capture_output=True,
    text=True,
    env=run_env,
  )
  assert completed.returncode == 1
  assert "no usable Python interpreter found" in (completed.stdout + completed.stderr)


def test_python_version_must_be_311(tmp_path: Path) -> None:
  fake_python = tmp_path / "python310"
  fake_python.write_text(
    """#!/usr/bin/env bash
if [[ "${1:-}" == "-c" ]]; then
  if [[ "${2:-}" == *version_info* ]]; then
    echo "3.10.0"
    exit 0
  fi
  if [[ "${2:-}" == *sys.executable* ]]; then
    echo "/tmp/fake-python310"
    exit 0
  fi
  if [[ "${2:-}" == *zoneinfo* ]]; then
    exit 0
  fi
fi
echo "unsupported invocation" >&2
exit 1
""",
    encoding="utf-8",
  )
  fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)
  completed = subprocess.run(
    [BASH_BIN, str(DEPLOY_SCRIPT), "--print-python-selector"],
    cwd=ROOT,
    capture_output=True,
    text=True,
    env={"V9_PYTHON_BIN": str(fake_python), "PATH": os.environ["PATH"]},
  )
  assert completed.returncode == 1
  assert "Python 3.11 required" in (completed.stdout + completed.stderr)


def test_deploy_script_uses_py_array_not_hardcoded_conda_run() -> None:
  text = DEPLOY_SCRIPT.read_text(encoding="utf-8")
  assert '"${PY[@]}"' in text
  assert text.count('conda run -n "${CONDA_ENV_NAME}" python') == 2
  assert "command -v conda" in text
  assert "_conda_env_available" in text
  assert "select_deploy_python" in text
  assert 'elif command -v conda >/dev/null 2>&1; then\n  PY=(conda run' not in text


def test_github_runner_simulation_no_environment_location_not_found(tmp_path: Path) -> None:
  fake_bin = tmp_path / "bin"
  fake_bin.mkdir()
  _write_fake_conda(fake_bin, env_available=False)
  completed = _run_deploy_selector(tmp_bin=fake_bin)
  assert completed.returncode == 0
  assert "EnvironmentLocationNotFound" not in completed.stdout
  assert "EnvironmentLocationNotFound" not in completed.stderr
  payload = _parse_selector_json(completed.stdout)
  assert payload["source"] in {"system-python", "system-python3", "V9_PYTHON_BIN"}


def test_deploy_workflow_rollback_requires_apply_started() -> None:
  text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
  assert "apply_started=true" in text
  assert "steps.apply.outputs.apply_started == 'true'" in text
  assert "Report deploy not started" in text
  assert "rollback_skipped: \\`true\\`" in text or "rollback_skipped: `true`" in text
  assert "deploy_not_started: \\`true\\`" in text or "deploy_not_started: `true`" in text


def test_deploy_plan_failure_does_not_match_old_unconditional_rollback() -> None:
  text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
  assert re.search(
    r"Rollback to previous revision[\s\S]*?if:\s*failure\(\)\s*&&\s*steps\.apply\.outputs\.apply_started == 'true'",
    text,
  )
  assert "if: failure() && steps.pre.outputs.previous_revision != ''" not in text


def test_rollback_guard_scenarios_documented_in_workflow() -> None:
  workflow = yaml.safe_load(DEPLOY_WORKFLOW.read_text(encoding="utf-8"))
  deploy_job = workflow["jobs"]["deploy"]
  step_names = [step["name"] for step in deploy_job["steps"]]
  assert step_names.index("Deploy plan") < step_names.index("Deploy apply")
  assert step_names.index("Deploy apply") < step_names.index("Rollback to previous revision")
  assert step_names.index("Report deploy not started") < step_names.index("Rollback to previous revision")
  assert deploy_job["concurrency"]["cancel-in-progress"] is False


def test_deploy_workflow_regression_guards() -> None:
  text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
  workflow = yaml.safe_load(text)
  triggers = workflow.get("on") or workflow[True]
  assert list(triggers.keys()) == ["workflow_dispatch"]
  assert "tech-cartography-v9-signal-watch" in text
  assert "production service deploy is forbidden" in text
  assert "ref: ${{ needs.preflight.outputs.release_tag }}" in text
  assert "--scope live-cloud" in text
  assert "workload_identity_provider" in text
  assert "environment: study-demo" in text
  assert "credentials_json" not in text
  assert "secrets." not in text.lower()
