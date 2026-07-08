"""Tests for v9 cloud weekly enabled toggle CLI."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from unittest.mock import patch

import pytest

import scripts.set_v9_cloud_weekly_enabled as toggle_script
from services_v9.cloud_weekly_settings import load_weekly_delivery_settings, save_weekly_delivery_settings
from tests.test_v9_cloud_runtime_and_settings import _FakeStorageClient

PROJECT_ROOT = toggle_script.PROJECT_ROOT


def _cloud_env() -> dict[str, str]:
  return toggle_script.build_cloud_environ()


def _seed_settings(storage_client: _FakeStorageClient) -> None:
  save_weekly_delivery_settings(
    {
      "enabled": False,
      "recipient_email": "owner@example.com",
      "weekday": "MON",
      "hour": 9,
      "minute": 0,
      "timezone": "Asia/Tokyo",
      "email_mode": "self_only",
    },
    environ={
      "V9_RUNTIME_MODE": "cloud",
      "V9_PERSIST_BUCKET": toggle_script.DEFAULT_BUCKET,
      "V9_WEEKLY_CONFIG_OBJECT": toggle_script.DEFAULT_CONFIG_OBJECT,
      "V9_ALLOWED_RECIPIENTS": "owner@example.com",
      "SMTP_FROM_EMAIL": "owner@example.com",
    },
    storage_client=storage_client,
    updated_by="test-seed",
  )


def test_plan_does_not_write_enabled_state() -> None:
  storage_client = _FakeStorageClient()
  _seed_settings(storage_client)
  env = _cloud_env()
  payload = toggle_script.plan_enabled_toggle(target_enabled=True, environ=env, storage_client=storage_client)
  loaded = toggle_script.load_weekly_delivery_settings(environ=env, storage_client=storage_client)
  assert payload["status"] == "plan"
  assert payload["would_change"] is True
  assert loaded["enabled"] is False


def test_enable_requires_approval_env() -> None:
  storage_client = _FakeStorageClient()
  _seed_settings(storage_client)
  env = _cloud_env()
  with patch.dict(os.environ, {"V9_CLOUD_CHANGE_APPROVED": "false"}, clear=False):
    with pytest.raises(RuntimeError, match="V9_CLOUD_CHANGE_APPROVED=true"):
      toggle_script.apply_enabled_toggle(
        target_enabled=True,
        updated_by="test",
        environ=env,
        storage_client=storage_client,
      )


def test_enable_disable_use_formal_cloud_save_and_preserve_fields() -> None:
  storage_client = _FakeStorageClient()
  _seed_settings(storage_client)
  env = {
    **_cloud_env(),
    "V9_ALLOWED_RECIPIENTS": "owner@example.com",
    "SMTP_FROM_EMAIL": "owner@example.com",
  }
  with patch.dict(os.environ, {"V9_CLOUD_CHANGE_APPROVED": "true"}, clear=False):
    enabled = toggle_script.apply_enabled_toggle(
      target_enabled=True,
      updated_by="test-enable",
      environ=env,
      storage_client=storage_client,
    )
  assert enabled["enabled"] is True
  assert enabled["after"]["weekday"] == "MON"
  assert enabled["after"]["hour"] == 9
  assert enabled["after"]["minute"] == 0
  assert enabled["after"]["timezone"] == "Asia/Tokyo"
  assert enabled["after"]["email_mode"] == "self_only"
  assert enabled["after"]["recipient_masked"].endswith("@example.com")
  assert enabled["revision"] == 2

  with patch.dict(os.environ, {"V9_CLOUD_CHANGE_APPROVED": "true"}, clear=False):
    disabled = toggle_script.apply_enabled_toggle(
      target_enabled=False,
      updated_by="test-disable",
      environ=env,
      storage_client=storage_client,
    )
  assert disabled["enabled"] is False
  assert disabled["revision"] == 3


def test_apply_writes_expected_gcs_object_without_secrets() -> None:
  storage_client = _FakeStorageClient()
  _seed_settings(storage_client)
  env = {
    **_cloud_env(),
    "V9_ALLOWED_RECIPIENTS": "owner@example.com",
    "SMTP_FROM_EMAIL": "owner@example.com",
  }
  with patch.dict(os.environ, {"V9_CLOUD_CHANGE_APPROVED": "true"}, clear=False):
    toggle_script.apply_enabled_toggle(
      target_enabled=True,
      updated_by="test",
      environ=env,
      storage_client=storage_client,
    )
  blob_payload = storage_client.bucket(toggle_script.DEFAULT_BUCKET).objects[toggle_script.DEFAULT_CONFIG_OBJECT]["payload"]
  assert toggle_script.DEFAULT_CONFIG_OBJECT in storage_client.bucket(toggle_script.DEFAULT_BUCKET).objects
  assert "SMTP_PASSWORD" not in str(blob_payload)
  assert "owner@example.com" in str(blob_payload)


def test_refuses_local_mode_mis_save(tmp_path) -> None:
  env = {
    "V9_RUNTIME_MODE": "local",
    "V9_PERSIST_BUCKET": toggle_script.DEFAULT_BUCKET,
    "V9_WEEKLY_CONFIG_OBJECT": toggle_script.DEFAULT_CONFIG_OBJECT,
  }
  with pytest.raises(RuntimeError, match="V9_RUNTIME_MODE must be cloud"):
    toggle_script.validate_cloud_target(env)


def test_cli_plan_and_apply_exit_codes(capsys) -> None:
  storage_client = _FakeStorageClient()
  _seed_settings(storage_client)
  with patch.object(toggle_script, "load_weekly_delivery_settings", wraps=toggle_script.load_weekly_delivery_settings), patch.object(
    toggle_script,
    "apply_enabled_toggle",
    wraps=toggle_script.apply_enabled_toggle,
  ):
    assert toggle_script.main(["--plan"]) == 0
  captured = capsys.readouterr().out
  assert '"status": "plan"' in captured
  assert "owner@example.com" not in captured


def test_cli_enable_without_approval_exits_non_zero() -> None:
  script_path = PROJECT_ROOT / "scripts" / "set_v9_cloud_weekly_enabled.py"
  completed = subprocess.run(
    [sys.executable, str(script_path), "--enable"],
    cwd=PROJECT_ROOT,
    check=False,
    capture_output=True,
    text=True,
    env={**os.environ, "V9_CLOUD_CHANGE_APPROVED": "false"},
  )
  combined = completed.stdout + completed.stderr
  assert completed.returncode != 0
  assert "V9_CLOUD_CHANGE_APPROVED=true" in combined


def test_output_masks_recipient_and_excludes_secrets(capsys) -> None:
  storage_client = _FakeStorageClient()
  _seed_settings(storage_client)
  env = {
    **_cloud_env(),
    "V9_ALLOWED_RECIPIENTS": "owner@example.com",
    "SMTP_FROM_EMAIL": "owner@example.com",
  }
  with patch.dict(os.environ, {"V9_CLOUD_CHANGE_APPROVED": "true"}, clear=False):
    with patch.object(toggle_script, "build_cloud_environ", return_value=env):
      with patch.object(
        toggle_script,
        "load_weekly_delivery_settings",
        side_effect=lambda **kwargs: load_weekly_delivery_settings(
          environ=env,
          storage_client=storage_client,
        ),
      ):
        with patch.object(
          toggle_script,
          "save_weekly_delivery_settings",
          side_effect=lambda settings, **kwargs: save_weekly_delivery_settings(
            settings,
            environ=env,
            storage_client=storage_client,
            updated_by=kwargs.get("updated_by", "test"),
          ),
        ):
          toggle_script.main(["--enable"])
  captured = capsys.readouterr().out
  payload = json.loads(captured)
  assert "owner@example.com" not in captured
  assert "@" in payload["after"]["recipient_masked"]
  assert "smtp" not in captured.lower()
