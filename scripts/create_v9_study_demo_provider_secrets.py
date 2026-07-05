#!/usr/bin/env python3
"""Plan/apply helper for study demo provider secrets (Stage C)."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from typing import Any

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


def apply_password_rotation() -> dict[str, Any]:
  _assert_stage_c(dict(os.environ))
  if os.environ.get(PASSWORD_ROTATION_ENV, "").lower() != "true":
    raise SystemExit(f"ERROR: requires {PASSWORD_ROTATION_ENV}=true")
  password = password_helper.prompt_password_twice()
  try:
    client = password_helper.default_secret_manager_client()
    return password_helper.apply_study_demo_password_secret(password, client=client)
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


def apply_api_key_secret(secret_name: str, *, approved_env: str) -> dict[str, Any]:
  _assert_stage_c(dict(os.environ))
  _assert_secret_allowed(secret_name)
  if os.environ.get(approved_env, "").lower() != "true":
    raise SystemExit(f"ERROR: requires {approved_env}=true")
  first = getpass.getpass("API key: ")
  second = getpass.getpass("Confirm API key: ")
  if first != second:
    raise SystemExit("ERROR: confirmation mismatch")
  if len(first.strip()) < 8:
    raise SystemExit("ERROR: API key too short")
  client = password_helper.default_secret_manager_client()
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
  _ensure_secret_container(client, secret_name=secret_name)
  added = client.add_secret_version(
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
