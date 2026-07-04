"""Tests for study demo password secret creation helper."""

from __future__ import annotations

import getpass
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from google.api_core import exceptions

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from scripts import create_v9_study_demo_password as helper


class _FakeSecretManagerClient:
  def __init__(
    self,
    *,
    exists: bool = False,
    versions: list[dict[str, str]] | None = None,
  ) -> None:
    self.exists = exists
    self._versions = list(versions or [])
    self.created_secrets: list[str] = []
    self.added_versions: list[tuple[str, bytes]] = []

  def get_secret(self, request: dict[str, str]):
    secret_name = request["name"].rsplit("/", 1)[-1]
    if secret_name in helper.PRODUCTION_SECRET_DENYLIST:
      raise AssertionError("production secret must not be accessed")
    if not self.exists:
      raise exceptions.NotFound("missing")
    return SimpleNamespace(name=request["name"])

  def create_secret(self, request: dict[str, object]):
    secret_id = str(request["secret_id"])
    if secret_id in helper.PRODUCTION_SECRET_DENYLIST:
      raise AssertionError("production secret must not be created")
    self.exists = True
    self.created_secrets.append(secret_id)
    return SimpleNamespace(name=f"projects/{helper.PROJECT_ID}/secrets/{secret_id}")

  def list_secret_versions(self, request: dict[str, str]):
    parent = request["parent"]
    secret_name = parent.rsplit("/", 1)[-1]
    for item in self._versions:
      state = item["state"]
      state_value = f"State.{state.upper()}"
      yield SimpleNamespace(
        name=f"{parent}/versions/{item['version']}",
        state=state_value,
        create_time=SimpleNamespace(isoformat=lambda: item.get("create_time", "2026-07-05T00:00:00+00:00")),
      )
      _ = secret_name

  def add_secret_version(self, request: dict[str, object]):
    parent = str(request["parent"])
    secret_name = parent.rsplit("/", 1)[-1]
    if secret_name in helper.PRODUCTION_SECRET_DENYLIST:
      raise AssertionError("production secret must not be modified")
    payload = dict(request["payload"])  # type: ignore[arg-type]
    data = bytes(payload["data"])  # type: ignore[index]
    self.added_versions.append((secret_name, data))
    version_number = str(len(self._versions) + 1)
    self._versions.append({"version": version_number, "state": "enabled"})
    return SimpleNamespace(name=f"{parent}/versions/{version_number}")


APPROVED_ENV = {
  **os.environ,
  helper.PASSWORD_APPROVED_ENV: "true",
  helper.STAGE_B_APPROVED_ENV: "true",
}


def test_plan_mode_does_not_call_getpass_or_cloud(monkeypatch: pytest.MonkeyPatch) -> None:
  calls: list[str] = []

  def _blocked(_prompt: str) -> str:
    calls.append("getpass")
    return "never-called-password-123456"

  monkeypatch.setattr(getpass, "getpass", _blocked)
  payload = json.loads(
    subprocess.check_output(
      [sys.executable, str(ROOT / "scripts/create_v9_study_demo_password.py"), "--plan"],
      cwd=ROOT,
      text=True,
    )
  )
  assert payload["status"] == "plan"
  assert calls == []


def test_apply_only_rejects_before_getpass(monkeypatch: pytest.MonkeyPatch) -> None:
  calls: list[str] = []
  monkeypatch.setattr(getpass, "getpass", lambda _prompt: calls.append("getpass") or "x")
  completed = subprocess.run(
    [sys.executable, str(ROOT / "scripts/create_v9_study_demo_password.py"), "--apply"],
    cwd=ROOT,
    capture_output=True,
    text=True,
    env=os.environ.copy(),
  )
  assert completed.returncode == 1
  assert calls == []
  assert helper.PASSWORD_APPROVED_ENV in completed.stderr


def test_password_approved_only_rejects_before_getpass(monkeypatch: pytest.MonkeyPatch) -> None:
  calls: list[str] = []
  monkeypatch.setattr(getpass, "getpass", lambda _prompt: calls.append("getpass") or "x")
  env = os.environ.copy()
  env[helper.PASSWORD_APPROVED_ENV] = "true"
  completed = subprocess.run(
    [sys.executable, str(ROOT / "scripts/create_v9_study_demo_password.py"), "--apply"],
    cwd=ROOT,
    capture_output=True,
    text=True,
    env=env,
  )
  assert completed.returncode == 1
  assert calls == []
  assert helper.STAGE_B_APPROVED_ENV in completed.stderr


def test_stage_b_only_rejects_before_getpass(monkeypatch: pytest.MonkeyPatch) -> None:
  calls: list[str] = []
  monkeypatch.setattr(getpass, "getpass", lambda _prompt: calls.append("getpass") or "x")
  env = os.environ.copy()
  env[helper.STAGE_B_APPROVED_ENV] = "true"
  completed = subprocess.run(
    [sys.executable, str(ROOT / "scripts/create_v9_study_demo_password.py"), "--apply"],
    cwd=ROOT,
    capture_output=True,
    text=True,
    env=env,
  )
  assert completed.returncode == 1
  assert calls == []


def test_full_apply_creates_first_version_with_fake_client() -> None:
  client = _FakeSecretManagerClient(exists=False)
  prompts: list[str] = []

  def _getpass(prompt: str) -> str:
    prompts.append(prompt)
    return "correct-password-123456"

  with patch.dict("os.environ", {k: v for k, v in APPROVED_ENV.items() if k in {helper.PASSWORD_APPROVED_ENV, helper.STAGE_B_APPROVED_ENV}}, clear=False):
    result = helper.run_apply(client=client, getpass_fn=_getpass, environ={
      helper.PASSWORD_APPROVED_ENV: "true",
      helper.STAGE_B_APPROVED_ENV: "true",
    })

  assert prompts == ["Study demo password: ", "Confirm study demo password: "]
  assert result["status"] == "created"
  assert result["new_version"] == "1"
  assert result["version_state"] == "enabled"
  assert result["secret_value_displayed"] is False
  assert client.created_secrets == [helper.SECRET_NAME]
  assert len(client.added_versions) == 1


def test_prompt_password_twice_rejects_short_password(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setattr(getpass, "getpass", lambda _prompt: "short")
  with pytest.raises(SystemExit):
    helper.prompt_password_twice()


def test_prompt_password_twice_rejects_mismatch() -> None:
  responses = iter(["correct-password-123456", "different-password-1234567"])

  def _getpass(_prompt: str) -> str:
    return next(responses)

  with pytest.raises(SystemExit):
    helper.prompt_password_twice(getpass_fn=_getpass)


def test_helper_has_no_password_or_project_cli_arguments() -> None:
  source = (ROOT / "scripts/create_v9_study_demo_password.py").read_text(encoding="utf-8")
  assert 'add_argument("--password' not in source
  assert 'add_argument("--project' not in source
  assert "SECRET_NAME = STUDY_DEMO_PASSWORD_SECRET" in source
  assert helper.SECRET_NAME == "tech-cartography-v9-study-demo-password"


def test_fixed_project_and_secret_enforced() -> None:
  with pytest.raises(ValueError):
    helper.secret_parent(project_id="other-project", secret_name=helper.SECRET_NAME)
  with pytest.raises(ValueError):
    helper.secret_parent(project_id=helper.PROJECT_ID, secret_name="tech-cartography-smtp-password")


def test_existing_enabled_version_blocks_creation() -> None:
  client = _FakeSecretManagerClient(
    exists=True,
    versions=[{"version": "1", "state": "enabled"}],
  )
  result = helper.apply_study_demo_password_secret(
    "correct-password-123456",
    client=client,
  )
  assert result["status"] == "blocked_existing_enabled_version"
  assert client.added_versions == []


def test_existing_nonzero_versions_block_even_without_enabled() -> None:
  client = _FakeSecretManagerClient(
    exists=True,
    versions=[{"version": "1", "state": "disabled"}],
  )
  result = helper.apply_study_demo_password_secret(
    "correct-password-123456",
    client=client,
  )
  assert result["status"] == "blocked_existing_versions"
  assert client.added_versions == []


def test_helper_source_does_not_print_secret_values() -> None:
  source = (ROOT / "scripts/create_v9_study_demo_password.py").read_text(encoding="utf-8")
  assert "print(password" not in source


def test_production_secrets_are_denylisted() -> None:
  assert "tech-cartography-smtp-password" in helper.PRODUCTION_SECRET_DENYLIST
  assert "tech-cartography-tavily-api-key" in helper.PRODUCTION_SECRET_DENYLIST
