#!/usr/bin/env python3
"""Plan/apply helper for study demo provider secrets (Stage C)."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from typing import Any, Callable

from services_v9.study_demo_config import (
  PRODUCTION_SECRET_DENYLIST,
  STUDY_DEMO_OPENALEX_SECRET,
  STUDY_DEMO_PASSWORD_SECRET,
  STUDY_DEMO_PROJECT_DEFAULT,
  STUDY_DEMO_TAVILY_SECRET,
)
from scripts import create_v9_study_demo_password as password_helper

PROJECT_ID = STUDY_DEMO_PROJECT_DEFAULT
STAGE_C_ENV = "V9_STUDY_DEMO_STAGE_C_APPROVED"
PASSWORD_ROTATION_ENV = "V9_STUDY_DEMO_PASSWORD_ROTATION_APPROVED"
OPENALEX_ENV = "V9_STUDY_DEMO_OPENALEX_KEY_APPROVED"
TAVILY_ENV = "V9_STUDY_DEMO_TAVILY_KEY_APPROVED"


def build_plan() -> dict[str, Any]:
  return {
    "status": "plan",
    "project_id": PROJECT_ID,
    "secrets": {
      "password_rotation": {
        "secret": STUDY_DEMO_PASSWORD_SECRET,
        "target_version": 2,
        "approval": [PASSWORD_ROTATION_ENV, STAGE_C_ENV],
      },
      "openalex_key": {
        "secret": STUDY_DEMO_OPENALEX_SECRET,
        "target_version": 1,
        "approval": [OPENALEX_ENV, STAGE_C_ENV],
      },
      "tavily_key": {
        "secret": STUDY_DEMO_TAVILY_SECRET,
        "target_version": 1,
        "approval": [TAVILY_ENV, STAGE_C_ENV],
      },
    },
    "forbidden": sorted(PRODUCTION_SECRET_DENYLIST),
    "notes": ["Stage C1 plan only", "no payload copy from production secrets"],
  }


def _assert_stage_c(environ: dict[str, str]) -> None:
  if str(environ.get(STAGE_C_ENV, "")).lower() != "true":
    raise SystemExit(f"ERROR: requires {STAGE_C_ENV}=true")


def _assert_secret_allowed(name: str) -> None:
  if name in PRODUCTION_SECRET_DENYLIST:
    raise SystemExit("ERROR: production secret names are forbidden")


def _version_map(metadata: password_helper.SecretMetadataReport) -> dict[str, password_helper.SecretVersionMetadata]:
  return {item.version: item for item in metadata.versions}


def _assert_password_rotation_can_proceed(
  metadata: password_helper.SecretMetadataReport,
) -> dict[str, Any] | None:
  if metadata.project_id != PROJECT_ID:
    raise SystemExit(f"ERROR: project_id must be fixed to {PROJECT_ID}")
  if metadata.secret_name != STUDY_DEMO_PASSWORD_SECRET:
    raise SystemExit(f"ERROR: secret_name must be fixed to {STUDY_DEMO_PASSWORD_SECRET}")

  if not metadata.container_exists:
    return {
      "status": "blocked_missing_previous_version",
      "project_id": metadata.project_id,
      "secret_name": metadata.secret_name,
      "message": "password secret container does not exist",
    }

  versions = _version_map(metadata)
  version_one = versions.get("1")
  if version_one is None:
    return {
      "status": "blocked_missing_previous_version",
      "project_id": metadata.project_id,
      "secret_name": metadata.secret_name,
      "message": "version 1 does not exist",
    }
  if version_one.state != "enabled":
    return {
      "status": "blocked_previous_version_not_enabled",
      "project_id": metadata.project_id,
      "secret_name": metadata.secret_name,
      "previous_version": "1",
      "previous_version_state": version_one.state,
      "message": "version 1 must be enabled before rotation",
    }
  if "2" in versions:
    return {
      "status": "blocked_rotation_target_exists",
      "project_id": metadata.project_id,
      "secret_name": metadata.secret_name,
      "existing_version": "2",
      "existing_version_state": versions["2"].state,
      "message": "version 2 already exists; refusing to add another version",
    }

  unexpected = sorted(
    version_id
    for version_id in versions
    if version_id.isdigit() and int(version_id) >= 3
  )
  if unexpected:
    return {
      "status": "blocked_unexpected_versions",
      "project_id": metadata.project_id,
      "secret_name": metadata.secret_name,
      "unexpected_versions": unexpected,
      "message": "unexpected secret versions >= 3 exist",
    }
  return None


def _assert_new_secret_can_be_created(
  client: Any,
  *,
  secret_name: str,
) -> dict[str, Any] | None:
  _assert_secret_allowed(secret_name)
  parent = f"projects/{PROJECT_ID}/secrets/{secret_name}"
  try:
    client.get_secret(request={"name": parent})
    versions = list(client.list_secret_versions(request={"parent": parent}))
    if versions:
      return {
        "status": "blocked_existing_version",
        "secret_name": secret_name,
        "version_count": len(versions),
      }
  except Exception:
    pass
  return None


def apply_password_rotation(
  *,
  client: password_helper.SecretManagerClientProtocol | None = None,
  getpass_fn: Callable[[str], str] | None = None,
  environ: dict[str, str] | None = None,
) -> dict[str, Any]:
  env = environ if environ is not None else dict(os.environ)
  _assert_stage_c(env)
  if env.get(PASSWORD_ROTATION_ENV, "").lower() != "true":
    raise SystemExit(f"ERROR: requires {PASSWORD_ROTATION_ENV}=true")
  _assert_secret_allowed(STUDY_DEMO_PASSWORD_SECRET)

  active_client = client or password_helper.default_secret_manager_client()
  metadata = password_helper.inspect_secret_metadata(active_client)
  blocked = _assert_password_rotation_can_proceed(metadata)
  if blocked is not None:
    return blocked

  password = password_helper.prompt_password_twice(getpass_fn=getpass_fn)
  try:
    refreshed = password_helper.inspect_secret_metadata(active_client)
    blocked = _assert_password_rotation_can_proceed(refreshed)
    if blocked is not None:
      return blocked

    parent = password_helper.secret_parent()
    added = active_client.add_secret_version(
      request={
        "parent": parent,
        "payload": {"data": password.encode("utf-8")},
      }
    )
    new_version = str(getattr(added, "name", "") or "").rsplit("/", 1)[-1]
    if new_version != "2":
      return {
        "status": "blocked_unexpected_new_version",
        "project_id": PROJECT_ID,
        "secret_name": STUDY_DEMO_PASSWORD_SECRET,
        "new_version": new_version,
        "message": "add_secret_version returned an unexpected version number",
      }

    after = password_helper.inspect_secret_metadata(active_client)
    version_one = _version_map(after).get("1")
    if version_one is None or version_one.state != "enabled":
      return {
        "status": "blocked_previous_version_changed",
        "project_id": PROJECT_ID,
        "secret_name": STUDY_DEMO_PASSWORD_SECRET,
        "message": "version 1 must remain enabled after rotation",
      }

    new_state = _version_map(after).get("2")
    return {
      "status": "rotation_version_created",
      "project_id": PROJECT_ID,
      "secret_name": STUDY_DEMO_PASSWORD_SECRET,
      "previous_version": "1",
      "previous_version_state": "enabled",
      "new_version": "2",
      "new_version_state": new_state.state if new_state is not None else "enabled",
      "secret_value_displayed": False,
    }
  finally:
    del password


def _ensure_secret_container(client: Any, *, secret_name: str) -> None:
  _assert_secret_allowed(secret_name)
  parent = f"projects/{PROJECT_ID}/secrets/{secret_name}"
  try:
    client.get_secret(request={"name": parent})
  except Exception:
    client.create_secret(
      request={
        "parent": f"projects/{PROJECT_ID}",
        "secret_id": secret_name,
        "secret": {"replication": {"automatic": {}}, "labels": {"study-demo": "true"}},
      }
    )


def apply_api_key_secret(
  secret_name: str,
  *,
  approved_env: str,
  client: Any | None = None,
  getpass_fn: Callable[[str], str] | None = None,
) -> dict[str, Any]:
  _assert_stage_c(dict(os.environ))
  _assert_secret_allowed(secret_name)
  if os.environ.get(approved_env, "").lower() != "true":
    raise SystemExit(f"ERROR: requires {approved_env}=true")
  reader = getpass.getpass if getpass_fn is None else getpass_fn
  first = reader("API key: ")
  second = reader("Confirm API key: ")
  if first != second:
    raise SystemExit("ERROR: confirmation mismatch")
  if len(first.strip()) < 8:
    raise SystemExit("ERROR: API key too short")
  active_client = client or password_helper.default_secret_manager_client()
  blocked = _assert_new_secret_can_be_created(active_client, secret_name=secret_name)
  if blocked is not None:
    del first, second
    return blocked
  _ensure_secret_container(active_client, secret_name=secret_name)
  added = active_client.add_secret_version(
    request={
      "parent": f"projects/{PROJECT_ID}/secrets/{secret_name}",
      "payload": {"data": first.encode("utf-8")},
    }
  )
  version = str(getattr(added, "name", "")).rsplit("/", 1)[-1]
  del first, second
  return {"status": "created", "secret_name": secret_name, "new_version": version, "secret_value_displayed": False}


def main() -> int:
  parser = argparse.ArgumentParser(description="Study demo provider secret helper")
  parser.add_argument("--plan", action="store_true")
  parser.add_argument("--rotate-password", action="store_true")
  parser.add_argument("--create-openalex-key", action="store_true")
  parser.add_argument("--create-tavily-key", action="store_true")
  args = parser.parse_args()
  if args.plan or not any([args.rotate_password, args.create_openalex_key, args.create_tavily_key]):
    print(json.dumps(build_plan(), ensure_ascii=False, indent=2))
    return 0
  if args.rotate_password:
    print(json.dumps(apply_password_rotation(), indent=2))
    return 0
  if args.create_openalex_key:
    print(json.dumps(apply_api_key_secret(STUDY_DEMO_OPENALEX_SECRET, approved_env=OPENALEX_ENV), indent=2))
    return 0
  if args.create_tavily_key:
    print(json.dumps(apply_api_key_secret(STUDY_DEMO_TAVILY_SECRET, approved_env=TAVILY_ENV), indent=2))
    return 0
  return 1


if __name__ == "__main__":
  raise SystemExit(main())
