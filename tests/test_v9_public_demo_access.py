"""Tests for read-only public judge demo access mode."""

from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

STUDY_ENV = {
  "V9_STUDY_DEMO_MODE": "true",
  "V9_STUDY_DEMO_BUCKET": "tech-cartography-v9-study-demo-1020686343587",
  "V9_STUDY_DEMO_PASSWORD": "correct-password-123456",
  "V9_STUDY_DEMO_DISABLE_EXTERNAL_EXECUTION": "true",
  "V9_STUDY_DEMO_SHARED_STATE": "true",
  "V9_STUDY_DEMO_EXPIRES_AT": "2099-12-31T23:59:59Z",
}

PUBLIC_DEMO_ENV = {
  **STUDY_ENV,
  "V9_ACCESS_MODE": "public_demo",
}


def test_default_access_mode_is_password() -> None:
  from services_v9.study_demo_access import ACCESS_MODE_PASSWORD, resolve_access_mode

  assert resolve_access_mode(STUDY_ENV) == ACCESS_MODE_PASSWORD
  assert resolve_access_mode({}) == ACCESS_MODE_PASSWORD


@pytest.mark.parametrize("invalid", ["", "  ", "demo", "open", "admin"])
def test_invalid_access_mode_fails_closed_to_password(invalid: str) -> None:
  from services_v9.study_demo_access import ACCESS_MODE_PASSWORD, resolve_access_mode

  env = {**STUDY_ENV, "V9_ACCESS_MODE": invalid}
  assert resolve_access_mode(env) == ACCESS_MODE_PASSWORD


def test_password_mode_shows_login_screen_source() -> None:
  from ui_v9 import study_demo_gate

  source = inspect.getsource(study_demo_gate.render_study_demo_login_screen)
  assert "共通パスワード" in source
  assert "is_public_demo" in source


def test_public_demo_skips_login_gate() -> None:
  from services_v9.study_demo_auth import is_authenticated

  assert is_authenticated({}, environ=PUBLIC_DEMO_ENV) is True


def test_public_demo_forces_simple_ui_mode() -> None:
  from services_v9.study_demo_ui_mode import resolve_ui_mode

  env = {**PUBLIC_DEMO_ENV, "V9_UI_MODE": "advanced"}
  assert resolve_ui_mode(env) == "simple"


def test_public_demo_banner_text_present() -> None:
  from ui_v9.study_demo_gate import render_public_demo_banner

  source = inspect.getsource(render_public_demo_banner)
  assert "PUBLIC_DEMO_BADGE" in source


def test_public_demo_seeded_notice_present() -> None:
  from ui_v9.study_demo_gate import render_public_demo_banner

  assert "PUBLIC_DEMO_SEEDED_NOTICE" in inspect.getsource(render_public_demo_banner)


def test_public_demo_legal_caveat_present() -> None:
  from ui_v9.study_demo_gate import render_public_demo_banner

  assert "PUBLIC_DEMO_LEGAL_CAVEAT" in inspect.getsource(render_public_demo_banner)


def test_public_demo_blocks_theme_lineage_write() -> None:
  from services_v9.study_demo_guard import StudyDemoWriteBlocked
  from services_v9.study_demo_lineage_storage import save_theme_lineage_object

  theme = {"theme_id": "theme_test", "theme_version": 1, "name": "demo"}
  with pytest.raises(StudyDemoWriteBlocked):
    save_theme_lineage_object(theme, environ=PUBLIC_DEMO_ENV, storage_client=MagicMock())


def test_public_demo_blocks_watch_profile_write(monkeypatch: pytest.MonkeyPatch) -> None:
  from services_v9.persistence import save_watch_profile
  from services_v9.study_demo_guard import StudyDemoWriteBlocked

  for key, value in PUBLIC_DEMO_ENV.items():
    monkeypatch.setenv(key, value)
  with pytest.raises(StudyDemoWriteBlocked):
    save_watch_profile({"theme_name": "x"}, base_dir=Path("/tmp/unused"))


def test_public_demo_blocks_snapshot_write(monkeypatch: pytest.MonkeyPatch) -> None:
  from services_v9.persistence import save_snapshot
  from services_v9.study_demo_guard import StudyDemoWriteBlocked

  for key, value in PUBLIC_DEMO_ENV.items():
    monkeypatch.setenv(key, value)
  with pytest.raises(StudyDemoWriteBlocked):
    save_snapshot([], {"theme_name": "x"})


def test_public_demo_blocks_digest_write(monkeypatch: pytest.MonkeyPatch) -> None:
  from services_v9.persistence import save_digest_files
  from services_v9.study_demo_guard import StudyDemoWriteBlocked

  for key, value in PUBLIC_DEMO_ENV.items():
    monkeypatch.setenv(key, value)
  with pytest.raises(StudyDemoWriteBlocked):
    save_digest_files("# md", "a,b", "{}", snapshot_id="snap")


def test_public_demo_blocks_search_plan_write() -> None:
  from services_v9.study_demo_guard import StudyDemoWriteBlocked
  from services_v9.study_demo_lineage_storage import save_search_plan_lineage_object

  plan = {"search_plan_id": "plan_test", "search_plan_version": 1}
  with pytest.raises(StudyDemoWriteBlocked):
    save_search_plan_lineage_object(plan, environ=PUBLIC_DEMO_ENV, storage_client=MagicMock())


def test_public_demo_blocks_active_context_write() -> None:
  from services_v9.study_demo_analysis_context import save_active_context_to_storage
  from services_v9.study_demo_guard import StudyDemoWriteBlocked

  with pytest.raises(StudyDemoWriteBlocked):
    save_active_context_to_storage({"active_search_run_id": "run"}, environ=PUBLIC_DEMO_ENV, storage_client=MagicMock())


def test_public_demo_blocks_weekly_baseline_write() -> None:
  from services_v9.study_demo_downstream import save_baseline_snapshot
  from services_v9.study_demo_guard import StudyDemoWriteBlocked

  with pytest.raises(StudyDemoWriteBlocked):
    save_baseline_snapshot(
      context={"active_search_run_id": "run"},
      integrated={"signals": []},
      profile_signature="sig",
      environ=PUBLIC_DEMO_ENV,
      storage_client=MagicMock(),
    )


def test_public_demo_blocks_email_send(monkeypatch: pytest.MonkeyPatch) -> None:
  from services_v9.study_demo_guard import StudyDemoExternalExecutionBlocked, assert_external_execution_allowed

  for key, value in PUBLIC_DEMO_ENV.items():
    monkeypatch.setenv(key, value)
  with pytest.raises(StudyDemoExternalExecutionBlocked):
    assert_external_execution_allowed("smtp_send")


def test_public_demo_blocks_scheduler_apply() -> None:
  from services_v9.study_demo_guard import StudyDemoExternalExecutionBlocked, assert_external_execution_allowed

  with pytest.raises(StudyDemoExternalExecutionBlocked):
    assert_external_execution_allowed("cloud_scheduler", environ=PUBLIC_DEMO_ENV)


def test_public_demo_blocks_external_api_execution() -> None:
  from services_v9.study_demo_guard import StudyDemoExternalExecutionBlocked, assert_external_execution_allowed

  with pytest.raises(StudyDemoExternalExecutionBlocked):
    assert_external_execution_allowed("bigquery_execute", environ=PUBLIC_DEMO_ENV)


def test_public_demo_gcs_write_guard() -> None:
  from services_v9.study_demo_guard import StudyDemoWriteBlocked
  from services_v9.study_demo_storage import validate_study_demo_write_target

  with pytest.raises(StudyDemoWriteBlocked):
    validate_study_demo_write_target(STUDY_ENV["V9_STUDY_DEMO_BUCKET"], environ=PUBLIC_DEMO_ENV)


def test_public_demo_allows_session_navigation_helpers() -> None:
  from services_v9.study_demo_access import is_public_demo

  assert is_public_demo(PUBLIC_DEMO_ENV) is True


def test_password_mode_still_requires_auth_without_session() -> None:
  from services_v9.study_demo_auth import is_authenticated

  assert is_authenticated({}, environ=STUDY_ENV) is False


def test_deploy_script_access_mode_allowlist() -> None:
  text = (ROOT / "scripts" / "deploy_v9_study_demo.sh").read_text(encoding="utf-8")
  assert "resolve_deploy_access_mode" in text
  assert "password|public_demo" in text
  assert "V9_ACCESS_MODE=${DEPLOY_ACCESS_MODE}" in text


def test_deploy_script_forbids_public_demo_on_production() -> None:
  text = (ROOT / "scripts" / "deploy_v9_study_demo.sh").read_text(encoding="utf-8")
  assert "public_demo is forbidden on production service" in text


def test_candidate_smoke_is_access_mode_aware() -> None:
  text = (ROOT / "scripts" / "deploy_v9_study_demo.sh").read_text(encoding="utf-8")
  smoke = text.split("smoke_test_candidate", 1)[1][:1200]
  assert "ACCESS_MODE" in smoke


def test_final_smoke_is_access_mode_aware() -> None:
  text = (ROOT / "scripts" / "deploy_v9_study_demo.sh").read_text(encoding="utf-8")
  assert "password-mode public smoke passed" in text
  assert "public_demo final smoke passed" in text


def test_deploy_workflow_validates_access_mode() -> None:
  text = (ROOT / ".github/workflows/deploy-study-demo.yml").read_text(encoding="utf-8")
  assert "Resolve deploy access mode" in text
  assert "V9_ACCESS_MODE must be password or public_demo" in text


def test_deploy_workflow_smoke_respects_access_mode() -> None:
  text = (ROOT / ".github/workflows/deploy-study-demo.yml").read_text(encoding="utf-8")
  assert 'access_mode == "password"' in text


def test_deploy_result_includes_access_mode() -> None:
  text = (ROOT / "scripts" / "deploy_v9_study_demo.sh").read_text(encoding="utf-8")
  assert '"access_mode"' in text
  assert '"expected_access_mode"' in text
  assert '"revision_access_mode"' in text
  assert '"access_mode_match"' in text


def test_shared_ci_step_forces_password_access_mode() -> None:
  text = (ROOT / ".github/workflows/deploy-study-demo.yml").read_text(encoding="utf-8")
  assert "Run shared CI checks" in text
  shared = text.split("- name: Run shared CI checks", 1)[1].split("- name:", 1)[0]
  assert "V9_ACCESS_MODE: password" in shared
  assert "vars.V9_ACCESS_MODE" not in shared


def test_workflow_job_global_env_does_not_set_access_mode() -> None:
  text = (ROOT / ".github/workflows/deploy-study-demo.yml").read_text(encoding="utf-8")
  header = text.split("jobs:", 1)[0]
  assert "V9_ACCESS_MODE:" not in header
  assert "V9_UI_MODE: simple" in header


def test_deploy_plan_apply_receive_vars_access_mode() -> None:
  text = (ROOT / ".github/workflows/deploy-study-demo.yml").read_text(encoding="utf-8")
  assert "V9_ACCESS_MODE: ${{ vars.V9_ACCESS_MODE }}" in text.split("Resolve deploy access mode", 1)[1].split(
    "Capture pre-deploy state", 1
  )[0]
  plan = text.split("- name: Deploy plan", 1)[1].split("- name: Deploy apply", 1)[0]
  apply = text.split("- name: Deploy apply", 1)[1].split("- name: Read deploy mutation state", 1)[0]
  assert "steps.access.outputs.access_mode" in plan
  assert "steps.access.outputs.access_mode" in apply


def test_deploy_script_local_checks_force_password() -> None:
  text = (ROOT / "scripts" / "deploy_v9_study_demo.sh").read_text(encoding="utf-8")
  body = text.split("run_local_checks() {", 1)[1].split("\n}\n", 1)[0]
  assert "V9_ACCESS_MODE=password" in body


def test_shared_ci_script_forces_password() -> None:
  text = (ROOT / "scripts" / "run_v9_ci_checks.sh").read_text(encoding="utf-8")
  assert "export V9_ACCESS_MODE=password" in text


def test_revision_env_missing_access_mode_fails(tmp_path: Path) -> None:
  from tests.test_v9_deploy_traffic_promotion import _run_functions, _write_json

  rev = _write_json(
    tmp_path / "rev.json",
    {"spec": {"containers": [{"env": [{"name": "V9_UI_MODE", "value": "simple"}]}]}},
  )
  result = _run_functions(
    tmp_path,
    ["verify_revision_access_mode_env", "resolve_deploy_access_mode", "log"],
    'DEPLOY_ACCESS_MODE=public_demo V9_UI_MODE=simple verify_revision_access_mode_env "rev-00032"',
    extra_env={"FAKE_REVISION_JSON": str(rev), "V9_ACCESS_MODE": "public_demo"},
  )
  assert result.returncode != 0
  assert "missing V9_ACCESS_MODE" in (result.stdout + result.stderr)


def test_revision_env_password_when_public_demo_expected_fails(tmp_path: Path) -> None:
  from tests.test_v9_deploy_traffic_promotion import _run_functions, _write_json

  rev = _write_json(
    tmp_path / "rev.json",
    {
      "spec": {
        "containers": [
          {
            "env": [
              {"name": "V9_ACCESS_MODE", "value": "password"},
              {"name": "V9_UI_MODE", "value": "simple"},
            ]
          }
        ]
      }
    },
  )
  result = _run_functions(
    tmp_path,
    ["verify_revision_access_mode_env", "resolve_deploy_access_mode", "log"],
    'DEPLOY_ACCESS_MODE=public_demo V9_UI_MODE=simple verify_revision_access_mode_env "rev-00032"',
    extra_env={"FAKE_REVISION_JSON": str(rev), "V9_ACCESS_MODE": "public_demo"},
  )
  assert result.returncode != 0
  assert "expected public_demo" in (result.stdout + result.stderr)


def test_revision_env_public_demo_match_passes(tmp_path: Path) -> None:
  from tests.test_v9_deploy_traffic_promotion import _run_functions, _write_json

  rev = _write_json(
    tmp_path / "rev.json",
    {
      "spec": {
        "containers": [
          {
            "env": [
              {"name": "V9_ACCESS_MODE", "value": "public_demo"},
              {"name": "V9_UI_MODE", "value": "simple"},
            ]
          }
        ]
      }
    },
  )
  result = _run_functions(
    tmp_path,
    ["verify_revision_access_mode_env", "resolve_deploy_access_mode", "log"],
    'DEPLOY_ACCESS_MODE=public_demo V9_UI_MODE=simple verify_revision_access_mode_env "rev-00032"',
    extra_env={"FAKE_REVISION_JSON": str(rev), "V9_ACCESS_MODE": "public_demo"},
  )
  assert result.returncode == 0, result.stderr + result.stdout
  assert "confirmed" in result.stdout

def test_public_demo_does_not_read_password_secret() -> None:
  from services_v9.study_demo_config import get_study_demo_password

  env = {**PUBLIC_DEMO_ENV, "V9_STUDY_DEMO_PASSWORD": "should-not-be-read"}
  assert get_study_demo_password(env) == ""


def test_password_secret_binding_not_removed_from_deploy() -> None:
  text = (ROOT / "scripts" / "deploy_v9_study_demo.sh").read_text(encoding="utf-8")
  assert "V9_STUDY_DEMO_PASSWORD=${PASSWORD_SECRET}" in text


def test_browser_acceptance_doc_lists_public_demo_checks() -> None:
  text = (ROOT / "docs/v9_github_actions_cicd.md").read_text(encoding="utf-8")
  assert "Public Demo — read-only" in text
  assert "永続保存されない" in text or "not persist" in text.lower()


def test_final_acceptance_plan_includes_public_demo_browser_items() -> None:
  from scripts.check_v9_study_demo_final_acceptance import run_plan

  payload = run_plan(search_run_id="study_demo_search_20260705_145711_c06e0a1b")
  assert payload["status"] == "ok"
  browser = list(payload.get("browser_acceptance", []) or [])
  assert any("Public Demo" in item for item in browser)


def test_setup_plan_lists_v9_access_mode_variable() -> None:
  env = os.environ.copy()
  env["GITHUB_REPOSITORY"] = "example-owner/example-repo"
  env["VALIDATED_RELEASE_TAG"] = "v9-study-demo-cicd-r7-validated"
  completed = subprocess.run(
    ["bash", str(ROOT / "scripts/setup_v9_github_cicd.sh"), "--plan"],
    cwd=ROOT,
    check=True,
    capture_output=True,
    text=True,
    env=env,
  )
  payload = json.loads(completed.stdout)
  assert "V9_ACCESS_MODE=public_demo" in payload["github_variables"]
