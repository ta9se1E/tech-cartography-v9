"""Secure v9 credential rotation helper (plan/apply, no secret logging)."""

from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from getpass import getpass
from pathlib import Path
from typing import Any, Iterable, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))

from scripts.v9_build_security import extract_nonempty_sensitive_env_names  # noqa: E402

DEFAULT_PROJECT_ID = "devops-ai-agent-hackathon-2026"
DEFAULT_DOTENV_PATH = PROJECT_ROOT / ".env"
DEFAULT_DEPLOY_SCRIPT = PROJECT_ROOT / "scripts" / "deploy_v9_cloud_run_weekly.sh"

V9_CREDENTIAL_NAMES = (
  "LANGCHAIN_API_KEY",
  "LANGSMITH_API_KEY",
  "OPENAI_API_KEY",
  "OPENALEX_API_KEY",
  "SMTP_PASSWORD",
  "TAVILY_API_KEY",
  "TECH_CARTOGRAPHY_LOGIN_PASSWORD",
)

SECRET_SPECS: dict[str, dict[str, str]] = {
  "SMTP_PASSWORD": {
    "secret_name": "tech-cartography-smtp-password",
    "cloud_env_name": "SMTP_PASSWORD",
  },
  "TAVILY_API_KEY": {
    "secret_name": "tech-cartography-tavily-api-key",
    "cloud_env_name": "TAVILY_API_KEY",
  },
}

CODE_USAGE: dict[str, dict[str, Any]] = {
  "SMTP_PASSWORD": {
    "services_v9": ["email_delivery.py", "cloud_weekly_job.py"],
    "ui_v9": [],
    "scripts": ["deploy_v9_cloud_run_weekly.sh"],
    "cloud_runtime": "active_cloud_runtime",
    "usage": "Cloud Run Job Secret Manager + local SMTP preview/send",
  },
  "TAVILY_API_KEY": {
    "services_v9": ["web_company_retrieval.py"],
    "ui_v9": [],
    "scripts": ["deploy_v9_cloud_run_weekly.sh"],
    "cloud_runtime": "active_cloud_runtime",
    "usage": "Cloud Run Job Secret Manager + local Tavily retrieval",
  },
  "OPENAI_API_KEY": {
    "services_v9": [],
    "ui_v9": [],
    "scripts": [],
    "cloud_runtime": "unused",
    "usage": "Not referenced by v9 Cloud Runtime code paths",
  },
  "OPENALEX_API_KEY": {
    "services_v9": [],
    "ui_v9": [],
    "scripts": [],
    "cloud_runtime": "unused",
    "usage": "OpenAlex v9 provider uses polite email / public API only",
  },
  "LANGCHAIN_API_KEY": {
    "services_v9": [],
    "ui_v9": [],
    "scripts": [],
    "cloud_runtime": "development_only",
    "usage": "Local LangChain tracing only (not mounted to v9 Cloud Run)",
  },
  "LANGSMITH_API_KEY": {
    "services_v9": [],
    "ui_v9": [],
    "scripts": [],
    "cloud_runtime": "development_only",
    "usage": "Local LangSmith tracing only (not mounted to v9 Cloud Run)",
  },
  "TECH_CARTOGRAPHY_LOGIN_PASSWORD": {
    "services_v9": [],
    "ui_v9": [],
    "scripts": [],
    "cloud_runtime": "unused",
    "usage": "v9 Cloud Service uses IAP; not referenced in v9 app code",
  },
}

ROTATION_CLASS: dict[str, str] = {
  "SMTP_PASSWORD": "ROTATE_CLOUD",
  "TAVILY_API_KEY": "ROTATE_CLOUD",
  "OPENAI_API_KEY": "REVOKE_AND_REMOVE",
  "OPENALEX_API_KEY": "REVOKE_AND_REMOVE",
  "LANGCHAIN_API_KEY": "ROTATE_LOCAL",
  "LANGSMITH_API_KEY": "ROTATE_LOCAL",
  "TECH_CARTOGRAPHY_LOGIN_PASSWORD": "REVOKE_AND_REMOVE",
}


@dataclass(frozen=True)
class LocalCredentialPresence:
  local_present: bool
  non_empty: bool


def parse_dotenv_lines(text: str) -> list[tuple[str, str]]:
  rows: list[tuple[str, str]] = []
  for raw_line in text.splitlines():
    line = raw_line.rstrip("\n")
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
      continue
    key, value = stripped.split("=", 1)
    rows.append((key.strip(), value))
  return rows


def summarize_local_credentials(dotenv_path: Path | str = DEFAULT_DOTENV_PATH) -> dict[str, LocalCredentialPresence]:
  path = Path(dotenv_path)
  nonempty_names = set(extract_nonempty_sensitive_env_names(path))
  rows = parse_dotenv_lines(path.read_text(encoding="utf-8")) if path.exists() else []
  present_names = {key for key, _value in rows}
  return {
    name: LocalCredentialPresence(
      local_present=name in present_names,
      non_empty=name in nonempty_names,
    )
    for name in V9_CREDENTIAL_NAMES
  }


def compare_langchain_langsmith_alias(dotenv_path: Path | str = DEFAULT_DOTENV_PATH) -> bool | None:
  path = Path(dotenv_path)
  if not path.exists():
    return None
  values: dict[str, str] = {}
  for key, value in parse_dotenv_lines(path.read_text(encoding="utf-8")):
    if key in {"LANGCHAIN_API_KEY", "LANGSMITH_API_KEY"}:
      values[key] = value.strip().strip('"').strip("'")
  if not values.get("LANGCHAIN_API_KEY") or not values.get("LANGSMITH_API_KEY"):
    return None
  return values["LANGCHAIN_API_KEY"] == values["LANGSMITH_API_KEY"]


def detect_latest_secret_references(deploy_script_text: str) -> list[str]:
  hits: list[str] = []
  for line in deploy_script_text.splitlines():
    if ":latest" in line and ("SMTP_PASSWORD" in line or "TAVILY_API_KEY" in line):
      hits.append(line.strip())
  return hits


def summarize_secret_versions(
  *,
  project_id: str,
  secret_names: Iterable[str],
  secret_manager_client: Any | None = None,
) -> dict[str, Any]:
  if secret_manager_client is not None:
    return _summarize_secret_versions_with_client(
      project_id=project_id,
      secret_names=secret_names,
      client=secret_manager_client,
    )
  try:
    client = _build_secret_manager_client()
    return _summarize_secret_versions_with_client(
      project_id=project_id,
      secret_names=secret_names,
      client=client,
    )
  except Exception:
    return _summarize_secret_versions_with_gcloud(project_id=project_id, secret_names=secret_names)


def _summarize_secret_versions_with_client(
  *,
  project_id: str,
  secret_names: Iterable[str],
  client: Any,
) -> dict[str, Any]:
  parent = f"projects/{project_id}"
  summaries: dict[str, Any] = {}
  for secret_name in secret_names:
    versions: list[dict[str, str]] = []
    for version in client.list_secret_versions(request={"parent": f"{parent}/secrets/{secret_name}"}):
      version_number = str(version.name).rsplit("/", 1)[-1]
      state = str(getattr(version, "state", "") or "").replace("State.", "").lower()
      create_time = ""
      if getattr(version, "create_time", None) is not None:
        create_time = version.create_time.isoformat()
      versions.append({
        "version": version_number,
        "state": state,
        "create_time": create_time,
      })
    versions.sort(key=lambda item: int(item["version"]), reverse=True)
    enabled_versions = [item["version"] for item in versions if item["state"] == "enabled"]
    summaries[secret_name] = {
      "versions": versions,
      "enabled_versions": enabled_versions,
      "latest_enabled_version": enabled_versions[0] if enabled_versions else None,
    }
  return summaries


def _summarize_secret_versions_with_gcloud(
  *,
  project_id: str,
  secret_names: Iterable[str],
) -> dict[str, Any]:
  summaries: dict[str, Any] = {}
  for secret_name in secret_names:
    completed = subprocess.run(
      [
        "gcloud",
        "secrets",
        "versions",
        "list",
        secret_name,
        "--project",
        project_id,
        "--format=json(name,state,createTime)",
      ],
      check=False,
      capture_output=True,
      text=True,
    )
    if completed.returncode != 0:
      summaries[secret_name] = {
        "versions": [],
        "enabled_versions": [],
        "latest_enabled_version": None,
        "lookup_status": "failed",
      }
      continue
    raw_versions = json.loads(completed.stdout or "[]")
    versions: list[dict[str, str]] = []
    for item in raw_versions:
      name = str(item.get("name", "") or "")
      version_number = name.rsplit("/", 1)[-1]
      state = str(item.get("state", "") or "").lower()
      versions.append({
        "version": version_number,
        "state": state,
        "create_time": str(item.get("createTime", "") or ""),
      })
    versions.sort(key=lambda item: int(item["version"]), reverse=True)
    enabled_versions = [item["version"] for item in versions if item["state"] == "enabled"]
    summaries[secret_name] = {
      "versions": versions,
      "enabled_versions": enabled_versions,
      "latest_enabled_version": enabled_versions[0] if enabled_versions else None,
      "lookup_status": "ok",
    }
  return summaries


def build_rotation_plan(
  *,
  dotenv_path: Path | str = DEFAULT_DOTENV_PATH,
  deploy_script_path: Path | str = DEFAULT_DEPLOY_SCRIPT,
  project_id: str = DEFAULT_PROJECT_ID,
  secret_manager_client: Any | None = None,
) -> dict[str, Any]:
  local = summarize_local_credentials(dotenv_path)
  deploy_text = Path(deploy_script_path).read_text(encoding="utf-8")
  latest_refs = detect_latest_secret_references(deploy_text)
  secret_versions = summarize_secret_versions(
    project_id=project_id,
    secret_names=[spec["secret_name"] for spec in SECRET_SPECS.values()],
    secret_manager_client=secret_manager_client,
  )
  credentials: list[dict[str, Any]] = []
  for name in V9_CREDENTIAL_NAMES:
    usage = dict(CODE_USAGE.get(name, {}))
    credentials.append({
      "name": name,
      "classification": ROTATION_CLASS.get(name, "NEEDS_USER_DECISION"),
      "local_present": local[name].local_present,
      "local_non_empty": local[name].non_empty,
      "code_usage": usage,
      "secret_name": SECRET_SPECS.get(name, {}).get("secret_name", ""),
      "cloud_runtime": usage.get("cloud_runtime", "unknown"),
    })
  return {
    "status": "plan",
    "project_id": project_id,
    "job_secret_reference_mode": "latest" if latest_refs else "unknown",
    "latest_secret_reference_lines": latest_refs,
    "job_secret_pin_plan": {
      "SMTP_PASSWORD": "tech-cartography-smtp-password:<NEW_NUMERIC_VERSION>",
      "TAVILY_API_KEY": "tech-cartography-tavily-api-key:<NEW_NUMERIC_VERSION>",
    },
    "langchain_langsmith_same_credential": compare_langchain_langsmith_alias(dotenv_path),
    "secret_versions": secret_versions,
    "credentials": credentials,
    "stage_b_required_manual_issuance": [
      name for name in V9_CREDENTIAL_NAMES
      if ROTATION_CLASS.get(name) in {"ROTATE_CLOUD", "ROTATE_LOCAL"}
    ],
    "revoke_and_remove_candidates": [
      name for name in V9_CREDENTIAL_NAMES
      if ROTATION_CLASS.get(name) == "REVOKE_AND_REMOVE"
    ],
  }


def require_apply_guard() -> None:
  if os.environ.get("V9_CREDENTIAL_ROTATION_APPROVED", "").strip().lower() != "true":
    raise RuntimeError("--apply requires V9_CREDENTIAL_ROTATION_APPROVED=true")


def prompt_secret(name: str) -> str:
  value = getpass(f"Enter new value for {name} (input hidden): ")
  if not value.strip():
    raise RuntimeError(f"{name} input was empty; rotation aborted.")
  return value.strip()


def add_secret_version(
  *,
  project_id: str,
  secret_name: str,
  secret_value: str,
  secret_manager_client: Any | None = None,
) -> str:
  client = secret_manager_client if secret_manager_client is not None else _build_secret_manager_client()
  parent = f"projects/{project_id}/secrets/{secret_name}"
  response = client.add_secret_version(
    request={"parent": parent, "payload": {"data": secret_value.encode("utf-8")}},
  )
  version_number = str(response.name).rsplit("/", 1)[-1]
  return version_number


def atomic_update_dotenv(
  *,
  dotenv_path: Path | str,
  updates: Mapping[str, str],
) -> None:
  path = Path(dotenv_path)
  original_mode = path.stat().st_mode if path.exists() else (stat.S_IRUSR | stat.S_IWUSR)
  existing_lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
  updated_keys = set(updates)
  output_lines: list[str] = []
  seen: set[str] = set()
  for raw_line in existing_lines:
    stripped = raw_line.strip()
    if stripped and not stripped.startswith("#") and "=" in stripped:
      key = stripped.split("=", 1)[0].strip()
      if key in updated_keys:
        if key not in seen:
          output_lines.append(f"{key}={updates[key]}")
          seen.add(key)
        continue
    output_lines.append(raw_line.rstrip("\n"))
  for key, value in updates.items():
    if key not in seen:
      output_lines.append(f"{key}={value}")
  payload = "\n".join(output_lines).rstrip() + "\n"
  directory = path.parent if path.parent != Path() else Path(".")
  directory.mkdir(parents=True, exist_ok=True)
  with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=directory, delete=False) as handle:
    handle.write(payload)
    temp_name = handle.name
  temp_path = Path(temp_name)
  os.chmod(temp_path, stat.S_IRUSR | stat.S_IWUSR)
  os.replace(temp_path, path)
  os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def apply_rotation(
  *,
  dotenv_path: Path | str = DEFAULT_DOTENV_PATH,
  project_id: str = DEFAULT_PROJECT_ID,
  targets: Iterable[str] | None = None,
  secret_manager_client: Any | None = None,
  prompt_fn: Any = prompt_secret,
) -> dict[str, Any]:
  require_apply_guard()
  selected = list(targets or [])
  if not selected:
    selected = [
      name for name, action in ROTATION_CLASS.items()
      if action in {"ROTATE_CLOUD", "ROTATE_LOCAL"}
    ]
  results: list[dict[str, Any]] = []
  dotenv_updates: dict[str, str] = {}
  for name in selected:
    action = ROTATION_CLASS.get(name, "NEEDS_USER_DECISION")
    if action == "REVOKE_AND_REMOVE":
      results.append({"name": name, "status": "skipped", "reason": "revoke_and_remove"})
      continue
    if action not in {"ROTATE_CLOUD", "ROTATE_LOCAL"}:
      results.append({"name": name, "status": "skipped", "reason": "needs_user_decision"})
      continue
    secret_value = prompt_fn(name)
    secret_name = SECRET_SPECS.get(name, {}).get("secret_name", "")
    new_version = ""
    if action == "ROTATE_CLOUD":
      if not secret_name:
        raise RuntimeError(f"{name} is marked ROTATE_CLOUD but has no Secret Manager mapping.")
      new_version = add_secret_version(
        project_id=project_id,
        secret_name=secret_name,
        secret_value=secret_value,
        secret_manager_client=secret_manager_client,
      )
    dotenv_updates[name] = secret_value
    results.append({
      "name": name,
      "status": "updated",
      "action": action,
      "secret_name": secret_name,
      "new_secret_version": new_version or None,
    })
  if dotenv_updates:
    atomic_update_dotenv(dotenv_path=dotenv_path, updates=dotenv_updates)
  return {
    "status": "applied",
    "project_id": project_id,
    "results": results,
    "job_secret_pin_next": {
      item["name"]: (
        f"{item['secret_name']}:{item['new_secret_version']}"
        if item.get("secret_name") and item.get("new_secret_version")
        else None
      )
      for item in results
      if item.get("status") == "updated"
    },
  }


def _build_secret_manager_client():
  from google.cloud import secretmanager

  return secretmanager.SecretManagerServiceClient()


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(description="Secure v9 credential rotation helper.")
  parser.add_argument("--plan", action="store_true", help="Print rotation plan only (default).")
  parser.add_argument("--apply", action="store_true", help="Apply rotation after hidden prompts.")
  parser.add_argument("--dotenv-path", default=str(DEFAULT_DOTENV_PATH))
  parser.add_argument("--project-id", default=DEFAULT_PROJECT_ID)
  return parser


def main(argv: list[str] | None = None) -> int:
  args = build_parser().parse_args(argv)
  mode = "--apply" if args.apply else "--plan"
  if mode == "--plan":
    payload = build_rotation_plan(
      dotenv_path=Path(args.dotenv_path),
      project_id=str(args.project_id),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0
  payload = apply_rotation(
    dotenv_path=Path(args.dotenv_path),
    project_id=str(args.project_id),
  )
  print(json.dumps(payload, ensure_ascii=False, indent=2))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
