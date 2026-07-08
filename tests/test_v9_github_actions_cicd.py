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
DEPLOYER_SA_NAME = "tech-cartography-v9-gh-deploy"
DEPLOYER_SA = f"{DEPLOYER_SA_NAME}@devops-ai-agent-hackathon-2026.iam.gserviceaccount.com"
RUNTIME_SA = "tech-cartography-v9-study-demo@devops-ai-agent-hackathon-2026.iam.gserviceaccount.com"
OLD_DEPLOYER_SA_NAME = "tech-cartography-v9-github-deployer"
REQUIRED_GITHUB_VARIABLES = (
  "GCP_PROJECT_ID",
  "GCP_PROJECT_NUMBER",
  "GCP_REGION",
  "CLOUD_RUN_SERVICE",
  "RUNTIME_SERVICE_ACCOUNT",
  "WIF_PROVIDER",
  "DEPLOYER_SERVICE_ACCOUNT",
  "VALIDATED_RELEASE_TAG",
)


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
  assert "Read deploy mutation state" in text
  assert "steps.deploy_state.outputs.mutation_started == 'true'" in text
  assert "Report deploy not started" in text


def test_deploy_script_preserves_cloud_run_iam() -> None:
  text = (ROOT / "scripts" / "deploy_v9_study_demo.sh").read_text(encoding="utf-8")
  assert "verify_public_access_readonly" in text
  assert "add-iam-policy-binding" not in text
  assert "--no-allow-unauthenticated" not in text
  assert "--allow-unauthenticated" not in text
  assert '"iam_policy_mutations": 0' in text


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
  env["VALIDATED_RELEASE_TAG"] = "v9-study-demo-cicd-live-validated"
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
  assert payload["deployer_service_account"] == DEPLOYER_SA
  assert payload["deployer_sa_reuse"] == DEPLOYER_SA_NAME
  assert payload["blockers"] == []


def test_gitignore_blocks_generated_gha_credentials() -> None:
  text = (ROOT / ".gitignore").read_text(encoding="utf-8")
  assert "gha-creds-" in text


def test_deployer_sa_id_within_gcp_limit() -> None:
  assert 6 <= len(DEPLOYER_SA_NAME) <= 30
  assert DEPLOYER_SA_NAME[0].isalpha()
  assert DEPLOYER_SA_NAME[-1].isalnum()
  assert all(ch.islower() or ch.isdigit() or ch == "-" for ch in DEPLOYER_SA_NAME)


def test_old_long_deployer_name_not_referenced() -> None:
  repo_text = "\n".join(
    path.read_text(encoding="utf-8")
    for path in (
      ROOT / "scripts" / "setup_v9_github_cicd.sh",
      WORKFLOW_DIR / "deploy-study-demo.yml",
      WORKFLOW_DIR / "rollback-study-demo.yml",
      ROOT / "docs" / "v9_github_actions_cicd.md",
    )
  )
  assert OLD_DEPLOYER_SA_NAME not in repo_text


def test_github_deployer_variable_name_not_used() -> None:
  repo_text = "\n".join(
    path.read_text(encoding="utf-8")
    for path in (
      ROOT / "scripts" / "setup_v9_github_cicd.sh",
      WORKFLOW_DIR / "deploy-study-demo.yml",
      WORKFLOW_DIR / "rollback-study-demo.yml",
    )
  )
  assert "GITHUB_DEPLOYER_SERVICE_ACCOUNT" not in repo_text


def test_deployer_service_account_variable_referenced() -> None:
  deploy_text = (WORKFLOW_DIR / "deploy-study-demo.yml").read_text(encoding="utf-8")
  rollback_text = (WORKFLOW_DIR / "rollback-study-demo.yml").read_text(encoding="utf-8")
  setup_text = (ROOT / "scripts" / "setup_v9_github_cicd.sh").read_text(encoding="utf-8")
  assert "vars.DEPLOYER_SERVICE_ACCOUNT" in deploy_text
  assert "vars.DEPLOYER_SERVICE_ACCOUNT" in rollback_text
  assert "DEPLOYER_SERVICE_ACCOUNT=${DEPLOYER_SA}" in setup_text


def test_deploy_auth_uses_deployer_service_account() -> None:
  text = (WORKFLOW_DIR / "deploy-study-demo.yml").read_text(encoding="utf-8")
  assert "Validate deployer service account" in text
  assert "service_account: ${{ env.DEPLOYER_SERVICE_ACCOUNT }}" in text
  assert DEPLOYER_SA in text
  assert "vars.RUNTIME_SERVICE_ACCOUNT" in text


def test_rollback_auth_uses_deployer_service_account() -> None:
  text = (WORKFLOW_DIR / "rollback-study-demo.yml").read_text(encoding="utf-8")
  assert "Validate deployer service account" in text
  assert "service_account: ${{ env.DEPLOYER_SERVICE_ACCOUNT }}" in text
  assert DEPLOYER_SA in text


def test_deployer_sa_guard_separates_runtime_and_production() -> None:
  deploy_text = (WORKFLOW_DIR / "deploy-study-demo.yml").read_text(encoding="utf-8")
  rollback_text = (WORKFLOW_DIR / "rollback-study-demo.yml").read_text(encoding="utf-8")
  for text in (deploy_text, rollback_text):
    assert "must not equal runtime service account" in text
    assert "must belong to devops-ai-agent-hackathon-2026" in text
  assert PRODUCTION_SERVICE in deploy_text
  assert "production service deploy is forbidden" in deploy_text


def test_setup_plan_lists_eight_github_variables() -> None:
  env = os.environ.copy()
  env["GITHUB_REPOSITORY"] = "ta9se1E/tech-cartography-v9"
  env["VALIDATED_RELEASE_TAG"] = "v9-study-demo-cicd-live-validated"
  completed = subprocess.run(
    ["bash", str(ROOT / "scripts" / "setup_v9_github_cicd.sh"), "--plan"],
    cwd=ROOT,
    check=True,
    capture_output=True,
    text=True,
    env=env,
  )
  payload = json.loads(completed.stdout)
  variable_names = []
  for item in payload["github_variables"]:
    variable_names.append(item.split("=", 1)[0])
  assert variable_names == list(REQUIRED_GITHUB_VARIABLES)


def test_workflows_have_no_credentials_json_or_github_secrets() -> None:
  for name in ("deploy-study-demo.yml", "rollback-study-demo.yml", "ci.yml"):
    text = (WORKFLOW_DIR / name).read_text(encoding="utf-8")
    assert "credentials_json" not in text
    assert "secrets." not in text.lower() or "github_secrets_required" in text
