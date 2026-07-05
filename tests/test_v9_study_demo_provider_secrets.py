"""Tests for study demo provider secret helper (password rotation and API keys)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from google.api_core import exceptions

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from scripts import create_v9_study_demo_provider_secrets as helper
from scripts import create_v9_study_demo_password as password_helper


class _FakeSecretManagerClient:
  def __init__(
    self,
    *,
    exists: bool = True,
    versions: list[dict[str, str]] | None = None,
    add_version_override: str | None = None,
  ) -> None:
    self.exists = exists
    self._versions = list(versions or [])
    self.add_version_override = add_version_override
    self.created_secrets: list[str] = []
    self.added_versions: list[tuple[str, bytes]] = []
    self.access_payload_calls = 0

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
    for item in self._versions:
      state = item["state"]
      state_value = f"State.{state.upper()}"
      yield SimpleNamespace(
        name=f"{parent}/versions/{item['version']}",
        state=state_value,
        create_time=SimpleNamespace(isoformat=lambda: item.get("create_time", "2026-07-05T00:00:00+00:00")),
      )

  def add_secret_version(self, request: dict[str, object]):
    parent = str(request["parent"])
    secret_name = parent.rsplit("/", 1)[-1]
    if secret_name in helper.PRODUCTION_SECRET_DENYLIST:
      raise AssertionError("production secret must not be modified")
    payload = dict(request["payload"])  # type: ignore[arg-type]
    data = bytes(payload["data"])  # type: ignore[index]
    self.added_versions.append((secret_name, data))
    if self.add_version_override is not None:
      version_number = self.add_version_override
    else:
      version_number = str(max(int(item["version"]) for item in self._versions) + 1)
    self._versions.append({"version": version_number, "state": "enabled"})
    return SimpleNamespace(name=f"{parent}/versions/{version_number}")

  def access_secret_version(self, request: dict[str, str]):
    self.access_payload_calls += 1
    raise AssertionError("secret payload must not be read")


ROTATION_ENV = {
  helper.STAGE_C_ENV: "true",
  helper.PASSWORD_ROTATION_ENV: "true",
}

OPENALEX_ENV = {
  helper.STAGE_C_ENV: "true",
  helper.OPENALEX_ENV: "true",
}


def _rotation_client(**kwargs: object) -> _FakeSecretManagerClient:
  return _FakeSecretManagerClient(
    exists=True,
    versions=[{"version": "1", "state": "enabled"}],
    **kwargs,
  )


def test_rotation_allowed_when_version_one_enabled_and_no_version_two() -> None:
  client = _rotation_client()
  prompts: list[str] = []

  def _getpass(_prompt: str) -> str:
    prompts.append(_prompt)
    return "correct-password-123456"

  result = helper.apply_password_rotation(
    client=client,
    getpass_fn=_getpass,
    environ=ROTATION_ENV,
  )
  assert prompts == ["Study demo password: ", "Confirm study demo password: "]
  assert result["status"] == "rotation_version_created"
  assert result["new_version"] == "2"
  assert result["previous_version"] == "1"
  assert result["previous_version_state"] == "enabled"
  assert result["secret_value_displayed"] is False
  assert len(client.added_versions) == 1
  assert client.access_payload_calls == 0
  version_one = next(item for item in client._versions if item["version"] == "1")
  assert version_one["state"] == "enabled"


def test_metadata_checked_before_getpass_when_blocked() -> None:
  client = _FakeSecretManagerClient(exists=True, versions=[{"version": "1", "state": "enabled"}, {"version": "2", "state": "enabled"}])
  prompts: list[str] = []

  def _getpass(_prompt: str) -> str:
    prompts.append(_prompt)
    return "correct-password-123456"

  result = helper.apply_password_rotation(client=client, getpass_fn=_getpass, environ=ROTATION_ENV)
  assert result["status"] == "blocked_rotation_target_exists"
  assert prompts == []
  assert client.added_versions == []


def test_missing_version_one_blocks_before_getpass() -> None:
  client = _FakeSecretManagerClient(exists=True, versions=[])
  prompts: list[str] = []
  result = helper.apply_password_rotation(
    client=client,
    getpass_fn=lambda _prompt: prompts.append(_prompt) or "correct-password-123456",
    environ=ROTATION_ENV,
  )
  assert result["status"] == "blocked_missing_previous_version"
  assert prompts == []


def test_disabled_version_one_blocks_before_getpass() -> None:
  client = _FakeSecretManagerClient(exists=True, versions=[{"version": "1", "state": "disabled"}])
  prompts: list[str] = []
  result = helper.apply_password_rotation(
    client=client,
    getpass_fn=lambda _prompt: prompts.append(_prompt) or "correct-password-123456",
    environ=ROTATION_ENV,
  )
  assert result["status"] == "blocked_previous_version_not_enabled"
  assert prompts == []


@pytest.mark.parametrize("state", ["enabled", "disabled", "destroyed"])
def test_existing_version_two_blocks_rotation(state: str) -> None:
  client = _FakeSecretManagerClient(
    exists=True,
    versions=[
      {"version": "1", "state": "enabled"},
      {"version": "2", "state": state},
    ],
  )
  prompts: list[str] = []
  result = helper.apply_password_rotation(
    client=client,
    getpass_fn=lambda _prompt: prompts.append(_prompt) or "correct-password-123456",
    environ=ROTATION_ENV,
  )
  assert result["status"] == "blocked_rotation_target_exists"
  assert prompts == []
  assert client.added_versions == []


def test_unexpected_version_three_blocks_before_getpass() -> None:
  client = _FakeSecretManagerClient(
    exists=True,
    versions=[
      {"version": "1", "state": "enabled"},
      {"version": "3", "state": "enabled"},
    ],
  )
  prompts: list[str] = []
  result = helper.apply_password_rotation(
    client=client,
    getpass_fn=lambda _prompt: prompts.append(_prompt) or "correct-password-123456",
    environ=ROTATION_ENV,
  )
  assert result["status"] == "blocked_unexpected_versions"
  assert prompts == []


def test_rotation_rejects_short_password() -> None:
  client = _rotation_client()
  with pytest.raises(SystemExit):
    helper.apply_password_rotation(
      client=client,
      getpass_fn=lambda _prompt: "short",
      environ=ROTATION_ENV,
    )
  assert client.added_versions == []


def test_rotation_rejects_password_mismatch() -> None:
  client = _rotation_client()
  responses = iter(["correct-password-123456", "different-password-1234567"])

  def _getpass(_prompt: str) -> str:
    return next(responses)

  with pytest.raises(SystemExit):
    helper.apply_password_rotation(client=client, getpass_fn=_getpass, environ=ROTATION_ENV)
  assert client.added_versions == []


def test_rotation_add_secret_version_called_once() -> None:
  client = _rotation_client()
  helper.apply_password_rotation(
    client=client,
    getpass_fn=lambda _prompt: "correct-password-123456",
    environ=ROTATION_ENV,
  )
  assert len(client.added_versions) == 1


def test_rotation_rejects_unexpected_returned_version() -> None:
  client = _rotation_client(add_version_override="3")
  result = helper.apply_password_rotation(
    client=client,
    getpass_fn=lambda _prompt: "correct-password-123456",
    environ=ROTATION_ENV,
  )
  assert result["status"] == "blocked_unexpected_new_version"
  assert result["new_version"] == "3"


def test_rotation_approval_required_before_getpass() -> None:
  client = _rotation_client()
  prompts: list[str] = []
  with pytest.raises(SystemExit):
    helper.apply_password_rotation(
      client=client,
      getpass_fn=lambda _prompt: prompts.append(_prompt) or "correct-password-123456",
      environ={helper.STAGE_C_ENV: "true"},
    )
  assert prompts == []


def test_openalex_create_blocks_existing_version() -> None:
  client = _FakeSecretManagerClient(
    exists=True,
    versions=[{"version": "1", "state": "enabled"}],
  )
  with patch.dict("os.environ", OPENALEX_ENV, clear=False):
    result = helper.apply_api_key_secret(
      helper.STUDY_DEMO_OPENALEX_SECRET,
      approved_env=helper.OPENALEX_ENV,
      client=client,
      getpass_fn=lambda _prompt: "openalex-key-value",
    )
  assert result["status"] == "blocked_existing_version"
  assert client.added_versions == []


def test_production_secret_denylist_enforced() -> None:
  with pytest.raises(SystemExit):
    helper._assert_secret_allowed("tech-cartography-tavily-api-key")


def test_helper_source_does_not_print_secret_values() -> None:
  source = (ROOT / "scripts/create_v9_study_demo_provider_secrets.py").read_text(encoding="utf-8")
  assert "print(password" not in source
  assert "access_secret_version" not in source


def test_assert_password_rotation_can_proceed_returns_none_when_eligible() -> None:
  metadata = password_helper.SecretMetadataReport(
    project_id=helper.PROJECT_ID,
    secret_name=helper.STUDY_DEMO_PASSWORD_SECRET,
    container_exists=True,
    version_count=1,
    enabled_versions=(password_helper.SecretVersionMetadata(version="1", state="enabled", create_time=""),),
    versions=(password_helper.SecretVersionMetadata(version="1", state="enabled", create_time=""),),
  )
  assert helper._assert_password_rotation_can_proceed(metadata) is None
