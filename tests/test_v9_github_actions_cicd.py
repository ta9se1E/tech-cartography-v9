"""Static validation for GitHub Actions CI/CD foundation."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
STUDY_SERVICE = "tech-cartography-v9-study-demo"
PRODUCTION_SERVICE = "tech-cartography-v9-signal-watch"


def _load_workflow(name: str) -> dict:
  return yaml.safe_load((WORKFLOW_DIR / name).read_text(encoding="utf-8"))


def _workflow_triggers(workflow: dict) -> dict:
  return workflow.get("on") or workflow[True]


def test_ci_workflow_triggers_and_checks() -> None:
  workflow = _load_workflow("ci.yml")
  triggers = _workflow_triggers(workflow)
  assert triggers["push"]["branches"] == ["v9-study-demo"]
  assert triggers["pull_request"]["branches"] == ["v9-study-demo"]
  assert "workflow_dispatch" in triggers
  steps = workflow["jobs"]["ci"]["steps"]
  assert any("run_v9_ci_checks.sh" in step.get("run", "") for step in steps)


def test_deploy_workflow_is_manual_and_guarded() -> None:
  workflow = _load_workflow("deploy-study-demo.yml")
  assert list(_workflow_triggers(workflow).keys()) == ["workflow_dispatch"]
  deploy_job = workflow["jobs"]["deploy"]
  assert deploy_job["environment"] == "study-demo"
  assert deploy_job["permissions"]["id-token"] == "write"
  assert deploy_job["concurrency"]["cancel-in-progress"] is False
  text = (WORKFLOW_DIR / "deploy-study-demo.yml").read_text(encoding="utf-8")
  assert PRODUCTION_SERVICE in text
  assert "credentials_json" not in text
  assert "Rollback to previous revision" in text


def test_rollback_workflow_is_manual() -> None:
  workflow = _load_workflow("rollback-study-demo.yml")
  assert list(_workflow_triggers(workflow).keys()) == ["workflow_dispatch"]
  assert workflow["jobs"]["rollback"]["environment"] == "study-demo"
  text = (WORKFLOW_DIR / "rollback-study-demo.yml").read_text(encoding="utf-8")
  assert f"^{STUDY_SERVICE}-" in text or "tech-cartography-v9-study-demo-" in text


def test_shared_ci_script_exists_and_is_valid_bash() -> None:
  script = ROOT / "scripts" / "run_v9_ci_checks.sh"
  assert script.exists()
  subprocess.run(["bash", "-n", str(script)], check=True)


def test_setup_script_exists_and_is_valid_bash() -> None:
  script = ROOT / "scripts" / "setup_v9_github_cicd.sh"
  assert script.exists()
  subprocess.run(["bash", "-n", str(script)], check=True)


def test_deploy_script_bash_syntax() -> None:
  subprocess.run(["bash", "-n", str(ROOT / "scripts" / "deploy_v9_study_demo.sh")], check=True)


def test_setup_plan_is_json_and_forbids_keys() -> None:
  env = os.environ.copy()
  env["GITHUB_REPOSITORY"] = "example-owner/example-repo"
  completed = subprocess.run(
    ["bash", str(ROOT / "scripts" / "setup_v9_github_cicd.sh"), "--plan"],
    cwd=ROOT,
    check=True,
    capture_output=True,
    text=True,
    env=env,
  )
  payload = json.loads(completed.stdout)
  assert payload["status"] == "plan"
  assert payload["service_account_key_json"] == "forbidden"
  assert payload["github_secrets_required"] is False
  assert payload["cloud_changes_in_plan"] is False
  assert payload["study_service"] == STUDY_SERVICE
  assert payload["production_service"] == PRODUCTION_SERVICE


def test_gitignore_blocks_generated_gha_credentials() -> None:
  text = (ROOT / ".gitignore").read_text(encoding="utf-8")
  assert "gha-creds-" in text
