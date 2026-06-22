#!/usr/bin/env python3
"""IAP cutover preflight checks — read-only, never enables/disables IAP (Phase 25O)."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from tech_cartography.runtime.auth_provider_config import (  # noqa: E402
  get_admin_emails,
  get_allowed_email_domains,
  get_auth_provider_mode,
  get_iap_expected_audience,
  get_iap_jwt_verify_mode,
)
from tech_cartography.runtime.cloud_run_config import (  # noqa: E402
  DISABLE_EMAIL_SEND_ENV,
  DISABLE_EXTERNAL_API_ENV,
  DISABLE_SCHEDULER_ENV,
)
from tech_cartography.runtime.live_artifact_paths import (  # noqa: E402
  get_live_run_history_dir,
  using_live_outputs_root_env,
)
from tech_cartography.auth.basic_auth import REQUIRE_LOGIN_ENV, is_login_required  # noqa: E402

DEFAULT_PROJECT_ID = "devops-ai-agent-hackathon-2026"
DEFAULT_REGION = "us-central1"
DEFAULT_SERVICE = "tech-cartography-v7-live"

FORBIDDEN_OUTPUT_PATTERNS = (
  re.compile(r"[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
)

TRACKED_ENV_KEYS = (
  "AUTH_PROVIDER_MODE",
  "IAP_JWT_VERIFY_MODE",
  "IAP_EXPECTED_AUDIENCE",
  "TECH_CARTOGRAPHY_ADMIN_EMAILS",
  "TECH_CARTOGRAPHY_ALLOWED_EMAIL_DOMAINS",
  "REQUIRE_LOGIN",
  "LIVE_OUTPUTS_ROOT",
  DISABLE_EXTERNAL_API_ENV,
  DISABLE_EMAIL_SEND_ENV,
  DISABLE_SCHEDULER_ENV,
)

SECRET_REF_KEYS = ("TAVILY_API_KEY", "SMTP_PASSWORD")


@dataclass
class CheckResult:
  level: str  # PASS | WARN | FAIL
  message: str


@dataclass
class PreflightReport:
  results: list[CheckResult] = field(default_factory=list)
  next_commands: list[str] = field(default_factory=list)
  rollback_commands: list[str] = field(default_factory=list)
  metadata: dict[str, Any] = field(default_factory=dict)

  def add(self, level: str, message: str) -> None:
    self.results.append(CheckResult(level=level, message=message))

  @property
  def exit_code(self) -> int:
    if any(item.level == "FAIL" for item in self.results):
      return 1
    return 0


def _assert_safe_output(text: str) -> None:
  for pattern in FORBIDDEN_OUTPUT_PATTERNS:
    if pattern.search(text):
      raise ValueError("Refusing to print JWT-like token in preflight output")


def _gcloud_unavailable_message(err: str) -> bool:
  lowered = err.lower()
  return any(
    token in lowered
    for token in (
      "unable to create private file",
      "credentials.db",
      "not found",
      "command not found",
      "no such file",
    )
  )


def _run_gcloud(args: list[str], *, project: str | None = None) -> tuple[int, str, str]:
  cmd = ["gcloud", *args]
  if project and "--project" not in args:
    cmd.extend(["--project", project])
  try:
    result = subprocess.run(
      cmd,
      cwd=PROJECT_ROOT,
      capture_output=True,
      text=True,
      check=False,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()
  except OSError as exc:
    return 127, "", str(exc)


def _parse_service_json(raw: str) -> dict[str, Any]:
  if not raw:
    return {}
  try:
    payload = json.loads(raw)
    return payload if isinstance(payload, dict) else {}
  except json.JSONDecodeError:
    return {}


def _container_env(service: dict[str, Any]) -> dict[str, str]:
  containers = (
    service.get("spec", {})
    .get("template", {})
    .get("spec", {})
    .get("containers", [])
  )
  if not containers:
    return {}
  env_map: dict[str, str] = {}
  for item in containers[0].get("env", []) or []:
    name = str(item.get("name") or "")
    if not name:
      continue
    if "value" in item:
      env_map[name] = str(item.get("value") or "")
    elif "valueFrom" in item:
      ref = item.get("valueFrom") or {}
      secret_ref = ref.get("secretKeyRef") or {}
      secret_name = str(secret_ref.get("name") or secret_ref.get("secret") or "")
      version = str(secret_ref.get("key") or secret_ref.get("version") or "latest")
      env_map[name] = f"secret:{secret_name}:{version}" if secret_name else "secret:configured"
  return env_map


def _secret_refs(service: dict[str, Any]) -> dict[str, str]:
  refs: dict[str, str] = {}
  containers = (
    service.get("spec", {})
    .get("template", {})
    .get("spec", {})
    .get("containers", [])
  )
  if not containers:
    return refs
  for item in containers[0].get("env", []) or []:
    name = str(item.get("name") or "")
    if name not in SECRET_REF_KEYS:
      continue
    value_from = item.get("valueFrom") or {}
    secret_ref = value_from.get("secretKeyRef") or {}
    secret_name = str(secret_ref.get("name") or secret_ref.get("secret") or "")
    if secret_name:
      refs[name] = f"secret reference: {secret_name}"
    elif "value" in item:
      refs[name] = "inline value (prefer secret reference)"
    else:
      refs[name] = "not configured"
  return refs


def _has_cloud_storage_mount(service: dict[str, Any]) -> bool:
  template_spec = service.get("spec", {}).get("template", {}).get("spec", {})
  volumes = template_spec.get("volumes") or []
  mounts = (template_spec.get("containers") or [{}])[0].get("volumeMounts") or []
  has_cs_volume = any("cloudStorage" in (vol or {}) for vol in volumes)
  has_mount = any("mountPath" in (mount or {}) for mount in mounts)
  return has_cs_volume and has_mount


def _iap_enabled_from_service(service: dict[str, Any], describe_text: str) -> str:
  metadata = service.get("metadata") or {}
  annotations = metadata.get("annotations") or {}
  for key in ("run.googleapis.com/iap-enabled", "iap.googleapis.com/enabled"):
    if str(annotations.get(key, "")).lower() in {"true", "1", "yes"}:
      return "enabled"
  if re.search(r"iap\s*enabled:\s*true", describe_text, re.IGNORECASE):
    return "enabled"
  if re.search(r"iap\s*enabled:\s*false", describe_text, re.IGNORECASE):
    return "disabled"
  return "unknown"


def _local_env_summary() -> dict[str, str]:
  summary: dict[str, str] = {}
  for key in TRACKED_ENV_KEYS:
    raw = os.environ.get(key)
    if raw is None:
      summary[key] = "(unset)"
    elif key in {"TECH_CARTOGRAPHY_ADMIN_EMAILS", "TECH_CARTOGRAPHY_ALLOWED_EMAIL_DOMAINS"}:
      summary[key] = "configured" if str(raw).strip() else "(unset)"
    elif "PASSWORD" in key or "SECRET" in key or key.endswith("_KEY"):
      summary[key] = "(redacted)"
    else:
      summary[key] = str(raw).strip() or "(empty)"
  return summary


def build_rollback_commands(project: str, region: str, service: str) -> list[str]:
  return [
    f'gcloud run services update "{service}" --region "{region}" --project "{project}" --no-iap',
    (
      f'gcloud run services update "{service}" --region "{region}" --project "{project}" '
      "--update-env-vars AUTH_PROVIDER_MODE=basic,REQUIRE_LOGIN=true,"
      "TECH_CARTOGRAPHY_LOGIN_USERNAME=admin,TECH_CARTOGRAPHY_LOGIN_PASSWORD=\"<set-via-read-s>\","
      "DISABLE_EXTERNAL_API=true,DISABLE_EMAIL_SEND=true,DISABLE_SCHEDULER=true"
    ),
  ]


def build_next_commands(
  *,
  project: str,
  region: str,
  service: str,
  project_number: str | None,
  auth_mode: str,
) -> list[str]:
  iap_sa = (
    f"service-{project_number}@gcp-sa-iap.iam.gserviceaccount.com" if project_number else "<PROJECT_NUMBER>"
  )
  commands = [
    f'gcloud services enable iap.googleapis.com --project="{project}"',
    f'gcloud beta services identity create --service=iap.googleapis.com --project="{project}"',
  ]
  if auth_mode == "basic":
    commands.append(
      f'gcloud run deploy "{service}" --source . --region "{region}" --project "{project}" '
      "--update-env-vars AUTH_PROVIDER_MODE=hybrid,REQUIRE_LOGIN=true "
      "(see docs/phase25o_cloud_run_iap_cutover_runbook.md for full env list)"
    )
  commands.extend(
    [
      f'gcloud run services update "{service}" --region "{region}" --project "{project}" --iap',
      (
        f'gcloud run services add-iam-policy-binding "{service}" --region "{region}" '
        f'--project "{project}" --member="serviceAccount:{iap_sa}" --role=roles/run.invoker'
      ),
      (
        f'gcloud iap web add-iam-policy-binding --member="user:your-email@example.com" '
        f'--role=roles/iap.httpsResourceAccessor --region="{region}" '
        f'--resource-type=cloud-run --service="{service}" --project "{project}"'
      ),
      f'gcloud run services describe "{service}" --region "{region}" --project "{project}"',
    ],
  )
  return commands


def run_preflight(
  *,
  project: str,
  region: str,
  service: str,
  skip_gcloud: bool = False,
) -> PreflightReport:
  report = PreflightReport()
  report.rollback_commands = build_rollback_commands(project, region, service)

  report.add("PASS", f"target project: {project}")
  report.add("PASS", f"target region: {region}")
  report.add("PASS", f"target service: {service}")

  local_mode = get_auth_provider_mode()
  report.metadata["local_auth_provider_mode"] = local_mode
  report.add("PASS", f"local AUTH_PROVIDER_MODE: {local_mode}")

  if local_mode in {"iap", "hybrid"}:
    if not get_admin_emails() and not get_allowed_email_domains():
      report.add(
        "WARN",
        f"local {local_mode} mode: TECH_CARTOGRAPHY_ADMIN_EMAILS / ALLOWED_EMAIL_DOMAINS unset",
      )
  if get_iap_jwt_verify_mode() == "strict" and not get_iap_expected_audience():
    report.add("WARN", "local IAP_JWT_VERIFY_MODE=strict but IAP_EXPECTED_AUDIENCE unset")

  local_env = _local_env_summary()
  report.metadata["local_env"] = local_env
  for key, value in local_env.items():
    report.add("PASS", f"local env {key}: {value}")

  if is_login_required():
    report.add("PASS", "local REQUIRE_LOGIN: enabled")
  else:
    report.add("WARN", "local REQUIRE_LOGIN: not enabled")

  if using_live_outputs_root_env():
    history_dir = get_live_run_history_dir(PROJECT_ROOT)
    count = len(list(history_dir.glob("run_history_*.json"))) if history_dir.exists() else 0
    report.add("PASS", f"local run history dir exists with {count} file(s)")
  else:
    report.add("WARN", "local LIVE_OUTPUTS_ROOT unset — using outputs fallback")

  if skip_gcloud:
    report.add("WARN", "gcloud checks skipped (--skip-gcloud)")
    report.next_commands = build_next_commands(
      project=project,
      region=region,
      service=service,
      project_number=None,
      auth_mode=local_mode,
    )
    return report

  code, project_number, err = _run_gcloud(
    ["projects", "describe", project, "--format=value(projectNumber)"],
    project=project,
  )
  if code != 0 or not project_number:
    if _gcloud_unavailable_message(err):
      report.add("WARN", "project number: gcloud unavailable (auth or SDK issue)")
    else:
      report.add("WARN", f"project number: unavailable ({err or 'gcloud failed'})")
    project_number_value: str | None = None
  else:
    project_number_value = project_number
    report.add("PASS", f"project number: {project_number}")
    iap_sa = f"service-{project_number}@gcp-sa-iap.iam.gserviceaccount.com"
    report.add("PASS", f"expected IAP service agent: {iap_sa}")

  api_code, api_out, api_err = _run_gcloud(
    ["services", "list", "--enabled", "--filter=name:iap.googleapis.com", "--format=value(name)"],
    project=project,
  )
  if api_code != 0:
    report.add("WARN", f"IAP API status: unknown ({api_err or 'gcloud failed'})")
  elif "iap.googleapis.com" in api_out:
    report.add("PASS", "IAP API enabled: yes")
  else:
    report.add("WARN", "IAP API enabled: no — run gcloud services enable iap.googleapis.com")

  svc_code, svc_json_raw, svc_err = _run_gcloud(
    ["run", "services", "describe", service, "--region", region, "--format=json"],
    project=project,
  )
  svc_text_code, svc_text, _ = _run_gcloud(
    ["run", "services", "describe", service, "--region", region, "--format=yaml"],
    project=project,
  )
  if svc_code != 0:
    if _gcloud_unavailable_message(svc_err):
      report.add("WARN", "Cloud Run service check skipped: gcloud unavailable")
    else:
      report.add("FAIL", f"Cloud Run service missing or inaccessible: {svc_err or service}")
    report.next_commands = build_next_commands(
      project=project,
      region=region,
      service=service,
      project_number=project_number_value,
      auth_mode=local_mode,
    )
    return report

  service_payload = _parse_service_json(svc_json_raw)
  url = str(service_payload.get("status", {}).get("url") or "")
  if url:
    report.add("PASS", f"service URL: {url}")
  else:
    report.add("WARN", "service URL: not found in describe output")

  remote_env = _container_env(service_payload)
  for key in TRACKED_ENV_KEYS:
    if key in remote_env:
      value = remote_env[key]
      if key in {"TECH_CARTOGRAPHY_ADMIN_EMAILS", "TECH_CARTOGRAPHY_ALLOWED_EMAIL_DOMAINS"}:
        display = "configured" if value.strip() else "(empty)"
      elif "PASSWORD" in key:
        display = "(redacted)"
      else:
        display = value
      report.add("PASS", f"remote env {key}: {display}")
    else:
      report.add("WARN", f"remote env {key}: not set on service")

  remote_mode = str(remote_env.get("AUTH_PROVIDER_MODE", "") or "").strip().lower() or "basic"
  if remote_mode not in {"basic", "iap", "hybrid"}:
    report.add("WARN", f"remote AUTH_PROVIDER_MODE invalid: {remote_mode}")
  elif remote_mode == "basic":
    report.add("WARN", "remote AUTH_PROVIDER_MODE=basic — cutover前に hybrid への再デプロイを推奨")
  else:
    report.add("PASS", f"remote AUTH_PROVIDER_MODE: {remote_mode}")

  if remote_mode in {"iap", "hybrid"}:
    admin_set = bool(str(remote_env.get("TECH_CARTOGRAPHY_ADMIN_EMAILS", "")).strip())
    domain_set = bool(str(remote_env.get("TECH_CARTOGRAPHY_ALLOWED_EMAIL_DOMAINS", "")).strip())
    if not admin_set and not domain_set:
      report.add("WARN", "remote iap/hybrid mode without ADMIN_EMAILS or ALLOWED_EMAIL_DOMAINS")

  jwt_mode = str(remote_env.get("IAP_JWT_VERIFY_MODE", "") or "off").strip().lower() or "off"
  audience = str(remote_env.get("IAP_EXPECTED_AUDIENCE", "") or "").strip()
  if jwt_mode == "strict" and not audience:
    report.add("WARN", "remote IAP_JWT_VERIFY_MODE=strict but IAP_EXPECTED_AUDIENCE unset")

  secret_refs = _secret_refs(service_payload)
  for key in SECRET_REF_KEYS:
    if key in secret_refs:
      report.add("PASS", f"{key}: {secret_refs[key]}")
    else:
      report.add("WARN", f"{key}: no secret reference found on service")

  if _has_cloud_storage_mount(service_payload):
    report.add("PASS", "Cloud Storage volume mount: present")
  else:
    report.add("WARN", "Cloud Storage volume mount: not detected — LIVE_OUTPUTS_ROOT persistence at risk")

  iap_state = _iap_enabled_from_service(service_payload, svc_text if svc_text_code == 0 else "")
  if iap_state == "enabled":
    report.add("PASS", "Cloud Run IAP: enabled")
  elif iap_state == "disabled":
    report.add("WARN", "Cloud Run IAP: disabled — enable manually when ready")
  else:
    report.add("WARN", "Cloud Run IAP: unknown — inspect gcloud run services describe")

  report.add(
    "PASS",
    "required IAM roles (manual): roles/iap.httpsResourceAccessor, roles/run.invoker for IAP SA",
  )

  report.next_commands = build_next_commands(
    project=project,
    region=region,
    service=service,
    project_number=project_number_value,
    auth_mode=remote_mode if remote_env else local_mode,
  )
  return report


def print_report(report: PreflightReport) -> None:
  for item in report.results:
    _assert_safe_output(item.message)
    print(f"{item.level}: {item.message}")

  print("")
  print("Next commands (manual only — script does not execute these):")
  for command in report.next_commands:
    _assert_safe_output(command)
    print(f"  {command}")

  print("")
  print("Rollback commands (manual only):")
  for command in report.rollback_commands:
    _assert_safe_output(command)
    print(f"  {command}")

  overall = "FAIL" if report.exit_code else "PASS"
  if any(item.level == "WARN" for item in report.results):
    overall = "WARN" if overall == "PASS" else overall
  print("")
  print(f"Overall: {overall}")


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(
    description="IAP cutover preflight checks (read-only). Never enables or disables IAP.",
  )
  parser.add_argument("--project", default=DEFAULT_PROJECT_ID, help="GCP project id")
  parser.add_argument("--region", default=DEFAULT_REGION, help="Cloud Run region")
  parser.add_argument("--service", default=DEFAULT_SERVICE, help="Cloud Run service name")
  parser.add_argument(
    "--skip-gcloud",
    action="store_true",
    help="Skip gcloud calls (local env checks only)",
  )
  return parser


def main(argv: list[str] | None = None) -> int:
  parser = build_parser()
  args = parser.parse_args(argv)
  report = run_preflight(
    project=args.project,
    region=args.region,
    service=args.service,
    skip_gcloud=args.skip_gcloud,
  )
  print_report(report)
  return report.exit_code


if __name__ == "__main__":
  raise SystemExit(main())
