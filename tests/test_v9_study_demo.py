"""Tests for the isolated v9 study demo mode."""

from __future__ import annotations

import getpass
import importlib
import inspect
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

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


def test_production_mode_unchanged_without_study_env() -> None:
  from services_v9.study_demo_config import is_study_demo_mode

  assert is_study_demo_mode({}) is False


def test_passwords_match_uses_hmac_compare_digest() -> None:
  from services_v9 import study_demo_auth as auth

  source = inspect.getsource(auth.passwords_match)
  assert "hmac.compare_digest" in source
  assert auth.passwords_match("same-value-123456789", "same-value-123456789") is True
  assert auth.passwords_match("wrong-value-1234567890", "same-value-123456789") is False


def test_verify_password_success_and_failure() -> None:
  from services_v9.study_demo_auth import verify_password

  assert verify_password("correct-password-123456", environ=STUDY_ENV) is True
  assert verify_password("wrong-password-1234567890", environ=STUDY_ENV) is False


def test_password_not_logged_in_auth_module() -> None:
  source = Path(ROOT / "services_v9/study_demo_auth.py").read_text(encoding="utf-8")
  assert "print(" not in source
  assert "logging." not in source


def test_session_auth_lifecycle() -> None:
  from services_v9.study_demo_auth import (
    SESSION_AUTHENTICATED_KEY,
    clear_authentication,
    is_authenticated,
    register_failed_attempt,
    register_successful_login,
  )

  session: dict[str, object] = {}
  assert is_authenticated(session, environ=STUDY_ENV) is False
  register_successful_login(session)
  assert session[SESSION_AUTHENTICATED_KEY] is True
  assert is_authenticated(session, environ=STUDY_ENV) is True
  clear_authentication(session)
  assert is_authenticated(session, environ=STUDY_ENV) is False


def test_failed_attempt_increments_cooldown() -> None:
  from services_v9.study_demo_auth import SESSION_FAIL_COUNT_KEY, cooldown_remaining_seconds, register_failed_attempt

  session: dict[str, object] = {}
  register_failed_attempt(session)
  assert int(session[SESSION_FAIL_COUNT_KEY]) == 1
  assert cooldown_remaining_seconds(session) >= 0


def test_expiry_rejects_authenticated_session() -> None:
  from services_v9.study_demo_auth import is_authenticated, register_successful_login

  expired_env = {
    **STUDY_ENV,
    "V9_STUDY_DEMO_EXPIRES_AT": "2020-01-01T00:00:00Z",
  }
  session: dict[str, object] = {}
  register_successful_login(session)
  assert is_authenticated(session, environ=expired_env) is False


def test_expiry_message_constant() -> None:
  from services_v9.study_demo_auth import EXPIRED_MESSAGE

  assert "公開期間は終了" in EXPIRED_MESSAGE


def test_public_demo_expired_still_allows_access() -> None:
  from services_v9.study_demo_auth import ensure_study_demo_access_allowed, is_authenticated

  expired_public_demo_env = {
    "V9_STUDY_DEMO_MODE": "true",
    "V9_ACCESS_MODE": "public_demo",
    "V9_STUDY_DEMO_EXPIRES_AT": "2020-01-01T00:00:00Z",
  }
  ensure_study_demo_access_allowed(environ=expired_public_demo_env)
  assert is_authenticated({}, environ=expired_public_demo_env) is True


def test_password_mode_expired_still_blocks_access() -> None:
  from services_v9.study_demo_auth import (
    StudyDemoExpiredError,
    ensure_study_demo_access_allowed,
    is_authenticated,
    register_successful_login,
  )

  expired_password_env = {
    "V9_STUDY_DEMO_MODE": "true",
    "V9_ACCESS_MODE": "password",
    "V9_STUDY_DEMO_PASSWORD": "x" * 16,
    "V9_STUDY_DEMO_EXPIRES_AT": "2020-01-01T00:00:00Z",
  }
  with pytest.raises(StudyDemoExpiredError):
    ensure_study_demo_access_allowed(environ=expired_password_env)
  session: dict[str, object] = {}
  register_successful_login(session)
  assert is_authenticated(session, environ=expired_password_env) is False


def test_public_demo_read_only_guard_remains_active_when_expired() -> None:
  from services_v9.study_demo_guard import StudyDemoWriteBlocked, assert_write_allowed

  expired_public_demo_env = {
    "V9_STUDY_DEMO_MODE": "true",
    "V9_ACCESS_MODE": "public_demo",
    "V9_STUDY_DEMO_EXPIRES_AT": "2020-01-01T00:00:00Z",
  }
  with pytest.raises(StudyDemoWriteBlocked):
    assert_write_allowed("theme_lineage", environ=expired_public_demo_env)


def test_secret_missing_fail_closed() -> None:
  from services_v9.study_demo_auth import StudyDemoNotConfiguredError, ensure_study_demo_access_allowed

  env = {**STUDY_ENV, "V9_STUDY_DEMO_PASSWORD": ""}
  with pytest.raises(StudyDemoNotConfiguredError):
    ensure_study_demo_access_allowed(environ=env)


def test_external_execution_blocked_for_bigquery() -> None:
  from services_v9.patent_bigquery_query import run_patent_bigquery_dry_run
  from services_v9.study_demo_guard import StudyDemoExternalExecutionBlocked

  preview = {"request": {}, "validation_rows": [{"status": "error", "message": "x"}]}
  with patch.dict("os.environ", STUDY_ENV, clear=False):
    with pytest.raises(StudyDemoExternalExecutionBlocked):
      run_patent_bigquery_dry_run(preview)


def test_external_execution_blocked_for_openalex() -> None:
  from services_v9.paper_openalex_retrieval import execute_openalex_paper_retrieval
  from services_v9.study_demo_guard import StudyDemoExternalExecutionBlocked

  preview = {"request": {"query_id": "paper_q08"}, "validation_rows": [{"status": "error", "message": "x"}]}
  with patch.dict("os.environ", STUDY_ENV, clear=False):
    with pytest.raises(StudyDemoExternalExecutionBlocked):
      execute_openalex_paper_retrieval(preview)


def test_external_execution_blocked_for_tavily() -> None:
  from services_v9.web_company_retrieval import execute_global_web_retrieval
  from services_v9.study_demo_guard import StudyDemoExternalExecutionBlocked

  preview = {"request": {}, "validation_rows": [{"status": "error", "message": "x"}]}
  with patch.dict("os.environ", STUDY_ENV, clear=False):
    with pytest.raises(StudyDemoExternalExecutionBlocked):
      execute_global_web_retrieval(preview)


def test_external_execution_blocked_for_smtp() -> None:
  from services_v9.email_delivery import EmailDeliveryConfig, send_digest_email_self_only
  from services_v9.study_demo_guard import StudyDemoExternalExecutionBlocked

  preview = {"subject": "x", "plain_text_body": "y", "html_body": "<p>y</p>"}
  config = EmailDeliveryConfig(
    send_mode="self_only",
    disabled=False,
    self_recipient="masked@example.com",
    sender="masked@example.com",
    recipient_allowlist=("masked@example.com",),
    smtp_host="smtp.example.com",
    smtp_port=587,
    smtp_username="masked@example.com",
    smtp_password="secret",
    use_starttls=True,
    timeout_seconds=30,
  )
  with patch.dict("os.environ", STUDY_ENV, clear=False):
    with pytest.raises(StudyDemoExternalExecutionBlocked):
      send_digest_email_self_only(preview, config)


def test_external_execution_blocked_for_scheduler() -> None:
  from services_v9.cloud_scheduler_admin import apply_scheduler_settings
  from services_v9.study_demo_guard import StudyDemoExternalExecutionBlocked

  with patch.dict("os.environ", {**STUDY_ENV, "V9_ENABLE_CLOUD_SCHEDULER_ADMIN": "true"}, clear=False):
    with pytest.raises(StudyDemoExternalExecutionBlocked):
      apply_scheduler_settings({"enabled": True, "cron_expression": "0 9 * * 1", "timezone": "Asia/Tokyo"})


def test_external_execution_blocked_for_cloud_job() -> None:
  from services_v9.cloud_weekly_job import run_cloud_weekly_job
  from services_v9.study_demo_guard import StudyDemoExternalExecutionBlocked

  with patch.dict("os.environ", STUDY_ENV, clear=False):
    with pytest.raises(StudyDemoExternalExecutionBlocked):
      run_cloud_weekly_job(environ=STUDY_ENV)


def test_production_bucket_write_rejected() -> None:
  from services_v9.study_demo_config import PRODUCTION_PERSIST_BUCKET
  from services_v9.study_demo_storage import validate_study_demo_write_target

  with patch.dict("os.environ", STUDY_ENV, clear=False):
    with pytest.raises(ValueError):
      validate_study_demo_write_target(PRODUCTION_PERSIST_BUCKET)


def test_demo_bucket_write_allowed() -> None:
  from services_v9.study_demo_storage import validate_study_demo_write_target

  with patch.dict("os.environ", STUDY_ENV, clear=False):
    validate_study_demo_write_target("tech-cartography-v9-study-demo-1020686343587")


def test_sanitize_weekly_run_status_removes_email() -> None:
  from services_v9.study_demo_storage import sanitize_weekly_run_status

  cleaned = sanitize_weekly_run_status(
    {
      "overall_status": "success",
      "email_preview": {"recipient": "secret@example.com", "send_succeeded": True},
    }
  )
  assert "email_preview" not in cleaned
  assert "recipient" not in json.dumps(cleaned)


def test_sanitize_weekly_delivery_settings() -> None:
  from services_v9.study_demo_storage import sanitize_weekly_delivery_settings

  cleaned = sanitize_weekly_delivery_settings(
    {"enabled": True, "email_mode": "self_only", "recipient": "secret@example.com"}
  )
  assert cleaned["enabled"] is False
  assert cleaned["email_mode"] == "preview"
  assert cleaned["recipient"] == ""


def test_seed_allowlist_excludes_delivery_logs() -> None:
  from services_v9.study_demo_storage import EXCLUDED_COPY_NAMES

  assert "email_preview.json" in EXCLUDED_COPY_NAMES


def test_run_app_defers_tabs_until_auth_in_study_mode() -> None:
  source = Path(ROOT / "ui_v9/signal_watch_app.py").read_text(encoding="utf-8")
  run_idx = source.index("def run_app")
  tabs_idx = source.index("tabs = st.tabs", run_idx)
  gate_idx = source.index("render_study_demo_login_screen", run_idx)
  assert gate_idx < tabs_idx


def test_study_demo_gate_uses_password_input_type() -> None:
  source = Path(ROOT / "ui_v9/study_demo_gate.py").read_text(encoding="utf-8")
  assert 'type="password"' in source
  assert "勉強会用デモ環境" in source


def test_password_helper_uses_getpass_and_rejects_short_password(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setattr(getpass, "getpass", lambda _prompt: "short")
  from scripts import create_v9_study_demo_password as helper

  with pytest.raises(SystemExit):
    helper.prompt_password_twice()


def test_password_helper_plan_mode() -> None:
  completed = subprocess.run(
    [sys.executable, str(ROOT / "scripts/create_v9_study_demo_password.py"), "--plan"],
    cwd=ROOT,
    check=True,
    capture_output=True,
    text=True,
  )
  payload = json.loads(completed.stdout)
  assert payload["status"] == "plan"
  assert payload["password_rules"]["no_cli_args"] is True


def test_prepare_seed_plan_lists_copy_targets() -> None:
  completed = subprocess.run(
    [sys.executable, str(ROOT / "scripts/prepare_v9_study_demo_seed.py"), "--plan"],
    cwd=ROOT,
    check=True,
    capture_output=True,
    text=True,
  )
  payload = json.loads(completed.stdout)
  assert payload["status"] == "plan"
  assert "weekly_digest.md" in payload["copy_allowlist"]
  assert "email_delivery_runs/**" in payload["excluded"]


def test_reset_plan_targets_active_only() -> None:
  completed = subprocess.run(
    [sys.executable, str(ROOT / "scripts/reset_v9_study_demo_data.py"), "--plan"],
    cwd=ROOT,
    check=True,
    capture_output=True,
    text=True,
  )
  payload = json.loads(completed.stdout)
  assert payload["target_prefix"] == "active/"


def test_deploy_script_service_allowlist() -> None:
  text = Path(ROOT / "scripts/deploy_v9_study_demo.sh").read_text(encoding="utf-8")
  assert "tech-cartography-v9-study-demo" in text
  allowlist_section = text.split("ALLOWED_SERVICES=(", 1)[1].split(")", 1)[0]
  assert "tech-cartography-v9-signal-watch" not in allowlist_section


def test_cleanup_script_production_denylist() -> None:
  text = Path(ROOT / "scripts/cleanup_v9_study_demo.sh").read_text(encoding="utf-8")
  assert "tech-cartography-v9-signal-watch" in text
  assert "tech-cartography-v9-weekly-watch" in text


def test_format_expiry_jst() -> None:
  from services_v9.study_demo_auth import format_expiry_jst

  assert "JST" in format_expiry_jst(environ=STUDY_ENV)


def test_validate_password_length_minimum() -> None:
  from services_v9.study_demo_auth import validate_password_length

  assert validate_password_length("1234567890123456") is True
  assert validate_password_length("short") is False
  assert validate_password_length("                ") is False
