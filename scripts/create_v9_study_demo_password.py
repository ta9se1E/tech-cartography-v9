#!/usr/bin/env python3
"""Plan/apply helper for the isolated v9 study demo shared password secret."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Protocol

from services_v9.study_demo_auth import validate_password_length
from services_v9.study_demo_config import STUDY_DEMO_PASSWORD_SECRET, STUDY_DEMO_PROJECT_DEFAULT

PROJECT_ID = STUDY_DEMO_PROJECT_DEFAULT
SECRET_NAME = STUDY_DEMO_PASSWORD_SECRET

PRODUCTION_SECRET_DENYLIST = frozenset(
  {
    "tech-cartography-smtp-password",
    "tech-cartography-tavily-api-key",
  }
)

PASSWORD_APPROVED_ENV = "V9_STUDY_DEMO_PASSWORD_APPROVED"
STAGE_B_APPROVED_ENV = "V9_STUDY_DEMO_STAGE_B_APPROVED"


class SecretManagerClientProtocol(Protocol):
  def get_secret(self, request: dict[str, str]) -> Any: ...

  def create_secret(self, request: dict[str, Any]) -> Any: ...

  def list_secret_versions(self, request: dict[str, str]) -> Iterable[Any]: ...

  def add_secret_version(self, request: dict[str, Any]) -> Any: ...


@dataclass(frozen=True)
class SecretVersionMetadata:
  version: str
  state: str
  create_time: str


@dataclass(frozen=True)
class SecretMetadataReport:
  project_id: str
  secret_name: str
  container_exists: bool
  version_count: int
  enabled_versions: tuple[SecretVersionMetadata, ...]
  versions: tuple[SecretVersionMetadata, ...]


def secret_parent(project_id: str = PROJECT_ID, secret_name: str = SECRET_NAME) -> str:
  _assert_fixed_secret_target(project_id, secret_name)
  return f"projects/{project_id}/secrets/{secret_name}"


def _assert_fixed_secret_target(project_id: str, secret_name: str) -> None:
  if project_id != PROJECT_ID:
    raise ValueError(f"project_id must be fixed to {PROJECT_ID}")
  if secret_name != SECRET_NAME:
    raise ValueError(f"secret_name must be fixed to {SECRET_NAME}")
  if secret_name in PRODUCTION_SECRET_DENYLIST:
    raise ValueError("production secret names are forbidden")


def normalize_secret_version_state(state: Any) -> str:
  if state is None:
    return ""
  if hasattr(state, "name"):
    name = str(getattr(state, "name", "") or "").strip().upper()
    if name in {"ENABLED", "DISABLED", "DESTROYED", "STATE_UNSPECIFIED"}:
      return name.lower()
    try:
      numeric = int(getattr(state, "value", state))
    except (TypeError, ValueError):
      numeric = None
    if numeric == 1:
      return "enabled"
    if numeric == 2:
      return "disabled"
    if numeric == 3:
      return "destroyed"
    if numeric == 0:
      return "state_unspecified"
  text = str(state).strip()
  if not text:
    return ""
  normalized = text.replace("SecretVersion.State.", "").replace("State.", "").strip().upper()
  if normalized in {"ENABLED", "DISABLED", "DESTROYED", "STATE_UNSPECIFIED"}:
    return normalized.lower()
  if normalized.isdigit():
    mapping = {"1": "enabled", "2": "disabled", "3": "destroyed", "0": "state_unspecified"}
    return mapping.get(normalized, text.lower())
  return text.lower()


def build_plan() -> dict[str, Any]:
  return {
    "status": "plan",
    "project_id": PROJECT_ID,
    "secret_name": SECRET_NAME,
    "actions": [
      "verify secret container metadata",
      "create secret container if missing",
      "add first secret version only when version_count=0 and no enabled versions",
    ],
    "apply_guards": {
      "mode_flag": "--apply",
      PASSWORD_APPROVED_ENV: "true",
      STAGE_B_APPROVED_ENV: "true",
    },
    "password_rules": {
      "minimum_length": 16,
      "no_whitespace_only": True,
      "no_cli_args": True,
      "no_stdout": True,
      "no_file_write": True,
      "getpass_before_cloud_write": True,
    },
    "forbidden_targets": sorted(PRODUCTION_SECRET_DENYLIST),
  }


def is_apply_fully_approved(environ: dict[str, str] | None = None) -> bool:
  env = environ if environ is not None else dict(os.environ)
  return (
    str(env.get(PASSWORD_APPROVED_ENV, "") or "").strip().lower() == "true"
    and str(env.get(STAGE_B_APPROVED_ENV, "") or "").strip().lower() == "true"
  )


def assert_apply_guards_before_getpass(*, apply: bool, environ: dict[str, str] | None = None) -> None:
  if not apply:
    return
  env = environ if environ is not None else dict(os.environ)
  missing: list[str] = []
  if str(env.get(PASSWORD_APPROVED_ENV, "") or "").strip().lower() != "true":
    missing.append(f"{PASSWORD_APPROVED_ENV}=true")
  if str(env.get(STAGE_B_APPROVED_ENV, "") or "").strip().lower() != "true":
    missing.append(f"{STAGE_B_APPROVED_ENV}=true")
  if missing:
    raise SystemExit(
      "ERROR: --apply requires "
      + ", ".join(missing)
      + " before password input"
    )


def prompt_password_twice(*, getpass_fn: Callable[[str], str] | None = None) -> str:
  reader = getpass.getpass if getpass_fn is None else getpass_fn
  first = reader("Study demo password: ")
  second = reader("Confirm study demo password: ")
  if first != second:
    raise SystemExit("ERROR: password confirmation did not match")
  if not validate_password_length(first):
    raise SystemExit("ERROR: password must be at least 16 non-whitespace characters")
  return first


def _version_metadata_from_api(version: Any) -> SecretVersionMetadata:
  version_id = str(getattr(version, "name", "") or "").rsplit("/", 1)[-1]
  create_time = ""
  raw_create_time = getattr(version, "create_time", None)
  if raw_create_time is not None and hasattr(raw_create_time, "isoformat"):
    create_time = str(raw_create_time.isoformat())
  return SecretVersionMetadata(
    version=version_id,
    state=normalize_secret_version_state(getattr(version, "state", None)),
    create_time=create_time,
  )


def inspect_secret_metadata(
  client: SecretManagerClientProtocol,
  *,
  project_id: str = PROJECT_ID,
  secret_name: str = SECRET_NAME,
) -> SecretMetadataReport:
  from google.api_core import exceptions

  _assert_fixed_secret_target(project_id, secret_name)
  parent = secret_parent(project_id, secret_name)
  try:
    client.get_secret(request={"name": parent})
  except exceptions.NotFound:
    return SecretMetadataReport(
      project_id=project_id,
      secret_name=secret_name,
      container_exists=False,
      version_count=0,
      enabled_versions=(),
      versions=(),
    )

  versions = tuple(_version_metadata_from_api(item) for item in client.list_secret_versions(request={"parent": parent}))
  enabled = tuple(item for item in versions if item.state == "enabled")
  return SecretMetadataReport(
    project_id=project_id,
    secret_name=secret_name,
    container_exists=True,
    version_count=len(versions),
    enabled_versions=enabled,
    versions=versions,
  )


def ensure_secret_container(
  client: SecretManagerClientProtocol,
  *,
  project_id: str = PROJECT_ID,
  secret_name: str = SECRET_NAME,
) -> bool:
  _assert_fixed_secret_target(project_id, secret_name)
  report = inspect_secret_metadata(client, project_id=project_id, secret_name=secret_name)
  if report.container_exists:
    return False
  client.create_secret(
    request={
      "parent": f"projects/{project_id}",
      "secret_id": secret_name,
      "secret": {
        "replication": {"automatic": {}},
        "labels": {"study-demo": "true"},
      },
    }
  )
  return True


def apply_study_demo_password_secret(
  password: str,
  *,
  client: SecretManagerClientProtocol,
  project_id: str = PROJECT_ID,
  secret_name: str = SECRET_NAME,
) -> dict[str, Any]:
  _assert_fixed_secret_target(project_id, secret_name)
  metadata = inspect_secret_metadata(client, project_id=project_id, secret_name=secret_name)
  if metadata.enabled_versions:
    return {
      "status": "blocked_existing_enabled_version",
      "project_id": project_id,
      "secret_name": secret_name,
      "container_exists": metadata.container_exists,
      "version_count": metadata.version_count,
      "enabled_versions": [item.version for item in metadata.enabled_versions],
      "message": "enabled secret version already exists; refusing to add another version",
    }
  if metadata.version_count > 0:
    return {
      "status": "blocked_existing_versions",
      "project_id": project_id,
      "secret_name": secret_name,
      "container_exists": metadata.container_exists,
      "version_count": metadata.version_count,
      "message": "secret already has versions; only version_count=0 is eligible for first-version creation",
    }

  created_container = ensure_secret_container(client, project_id=project_id, secret_name=secret_name)
  parent = secret_parent(project_id, secret_name)
  added = client.add_secret_version(
    request={
      "parent": parent,
      "payload": {"data": password.encode("utf-8")},
    }
  )
  new_version = str(getattr(added, "name", "") or "").rsplit("/", 1)[-1]
  refreshed = inspect_secret_metadata(client, project_id=project_id, secret_name=secret_name)
  matched = next((item for item in refreshed.versions if item.version == new_version), None)
  return {
    "status": "created",
    "project_id": project_id,
    "secret_name": secret_name,
    "container_created": created_container,
    "new_version": new_version,
    "version_state": matched.state if matched is not None else "enabled",
    "version_count": refreshed.version_count,
    "secret_value_displayed": False,
  }


def default_secret_manager_client() -> SecretManagerClientProtocol:
  from google.cloud import secretmanager

  return secretmanager.SecretManagerServiceClient()


def run_apply(
  *,
  environ: dict[str, str] | None = None,
  client: SecretManagerClientProtocol | None = None,
  getpass_fn: Callable[[str], str] | None = None,
) -> dict[str, Any]:
  assert_apply_guards_before_getpass(apply=True, environ=environ)
  password = prompt_password_twice(getpass_fn=getpass_fn)
  try:
    active_client = client or default_secret_manager_client()
    return apply_study_demo_password_secret(password, client=active_client)
  finally:
    del password


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description="Create study demo password secret version")
  mode_group = parser.add_mutually_exclusive_group()
  mode_group.add_argument("--plan", action="store_true", help="Show plan only")
  mode_group.add_argument("--apply", action="store_true", help="Create secret version when fully approved")
  args = parser.parse_args(argv)
  apply = bool(args.apply)

  if not apply:
    print(json.dumps(build_plan(), ensure_ascii=False, indent=2))
    return 0

  try:
    assert_apply_guards_before_getpass(apply=True)
    result = run_apply()
  except SystemExit as exc:
    print(str(exc), file=sys.stderr)
    return 1

  print(json.dumps(result, ensure_ascii=False, indent=2))
  if result.get("status") != "created":
    return 1
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
