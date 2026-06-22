#!/usr/bin/env python3
"""CI/CD preflight checks — read-only, no deploy (Phase 25P)."""

from __future__ import annotations

import argparse
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

DEFAULT_PROJECT_ID = "devops-ai-agent-hackathon-2026"
DEFAULT_REGION = "us-central1"
DEFAULT_SERVICE = "tech-cartography-v7-live"
WRONG_LIVE_ARTIFACTS_BUCKET = "tech-cartography-v7-live-artifacts-devops-ai-agent-hackathon-2026"
CORRECT_LIVE_ARTIFACTS_BUCKET = "tech-cartography-v7-live-artifacts-1020686343587"

FORBIDDEN_INLINE_MARKERS = (
  "sk-",
  "eyJhbGci",
  "xoxb-",
  "BEGIN PRIVATE KEY",
)


def _read(path: Path) -> str:
  if not path.exists():
    return ""
  return path.read_text(encoding="utf-8")


def _run_gcloud(args: list[str], *, project: str | None = None) -> tuple[int, str, str]:
  cmd = ["gcloud", *args]
  if project and "--project" not in args:
    cmd.extend(["--project", project])
  try:
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, check=False)
    return result.returncode, result.stdout.strip(), result.stderr.strip()
  except OSError as exc:
    return 127, "", str(exc)


def _is_executable(path: Path) -> bool:
  if not path.exists():
    return False
  return bool(path.stat().st_mode & stat.S_IXUSR)


def run_checks(*, project: str, region: str, service: str, skip_gcloud: bool) -> tuple[list[str], list[str], list[str]]:
  passes: list[str] = []
  warnings: list[str] = []
  failures: list[str] = []

  cloudbuild = PROJECT_ROOT / "cloudbuild.yaml"
  deploy_script = PROJECT_ROOT / "scripts/deploy_live_safe.sh"
  rollback_script = PROJECT_ROOT / "scripts/rollback_live_to_basic.sh"
  cicd_docs = PROJECT_ROOT / "docs/phase25p_cicd_cloud_build_deploy.md"
  ensure_ignore_script = PROJECT_ROOT / "scripts/ensure_cloud_build_ignore_files.sh"
  canonical_gcloudignore = PROJECT_ROOT / "config/cloudrun.gcloudignore"
  canonical_dockerignore = PROJECT_ROOT / "config/cloudrun.dockerignore"
  required_checks = (
    PROJECT_ROOT / "scripts/check_cloudrun_demo_ready.py",
    PROJECT_ROOT / "scripts/check_live_beta_ready.py",
    PROJECT_ROOT / "scripts/check_iap_cutover_ready.py",
  )

  for path in (
    cloudbuild,
    deploy_script,
    rollback_script,
    cicd_docs,
    ensure_ignore_script,
    canonical_gcloudignore,
    canonical_dockerignore,
    *required_checks,
  ):
    if path.exists():
      passes.append(f"artifact exists: {path.relative_to(PROJECT_ROOT)}")
    else:
      failures.append(f"missing: {path.relative_to(PROJECT_ROOT)}")

  if deploy_script.exists() and not _is_executable(deploy_script):
    warnings.append("deploy_live_safe.sh is not executable (chmod +x recommended)")
  if rollback_script.exists() and not _is_executable(rollback_script):
    warnings.append("rollback_live_to_basic.sh is not executable (chmod +x recommended)")

  cloudbuild_text = _read(cloudbuild)
  deploy_text = _read(deploy_script)
  rollback_text = _read(rollback_script)

  if cloudbuild_text:
    if "pytest" not in cloudbuild_text:
      failures.append("cloudbuild.yaml does not run pytest")
    if "gcloud run deploy" not in cloudbuild_text:
      failures.append("cloudbuild.yaml does not deploy Cloud Run")
    if "--no-iap" in cloudbuild_text:
      failures.append("cloudbuild.yaml must not disable IAP")
    if "AUTH_PROVIDER_MODE=iap" not in cloudbuild_text:
      warnings.append("cloudbuild.yaml should set AUTH_PROVIDER_MODE=iap")
    for marker in FORBIDDEN_INLINE_MARKERS:
      if marker in cloudbuild_text:
        failures.append(f"cloudbuild.yaml contains forbidden inline secret marker: {marker}")
    if WRONG_LIVE_ARTIFACTS_BUCKET in cloudbuild_text:
      failures.append("cloudbuild.yaml contains project-id based live artifacts bucket name")
    if CORRECT_LIVE_ARTIFACTS_BUCKET not in cloudbuild_text:
      failures.append("cloudbuild.yaml missing project-number based live artifacts bucket default")
    if "ensure_cloud_build_ignore_files.sh" not in cloudbuild_text:
      failures.append("cloudbuild.yaml must restore ignore files before quality-gate tests")
    if "__pycache__" not in _read(canonical_gcloudignore):
      failures.append("config/cloudrun.gcloudignore must exclude __pycache__")
    if WRONG_LIVE_ARTIFACTS_BUCKET in _read(canonical_gcloudignore):
      failures.append("canonical gcloudignore contains wrong live artifacts bucket name")

  if deploy_text:
    if WRONG_LIVE_ARTIFACTS_BUCKET in deploy_text:
      failures.append("deploy_live_safe.sh contains project-id based live artifacts bucket name")
    if "PROJECT_NUMBER" not in deploy_text and "projectNumber" not in deploy_text:
      failures.append("deploy_live_safe.sh must resolve bucket from PROJECT_NUMBER")
    if "gcloud storage buckets describe" not in deploy_text:
      failures.append("deploy_live_safe.sh must verify bucket exists before deploy")
    if re.search(r"gcloud\s+run\s+.*--no-iap", deploy_text):
      failures.append("deploy_live_safe.sh must not disable IAP")
    if "AUTH_PROVIDER_MODE=basic" in deploy_text:
      failures.append("deploy_live_safe.sh must not set AUTH_PROVIDER_MODE=basic")

  if rollback_text:
    if "read -rs" not in rollback_text and "read -s" not in rollback_text:
      failures.append("rollback_live_to_basic.sh must read password with read -s")
    if "unset TC_LOGIN_PASSWORD" not in rollback_text:
      warnings.append("rollback_live_to_basic.sh should unset TC_LOGIN_PASSWORD")

  passes.append(f"target project: {project}")
  passes.append(f"target region: {region}")
  passes.append(f"target service: {service}")
  passes.append("build strategy: Cloud Build + gcloud run deploy --source (buildpacks)")

  if skip_gcloud:
    warnings.append("gcloud checks skipped (--skip-gcloud)")
    return passes, warnings, failures

  auth_code, auth_out, auth_err = _run_gcloud(["auth", "list", "--filter=status:ACTIVE", "--format=value(account)"])
  if auth_code == 0 and auth_out:
    passes.append(f"gcloud active account: {auth_out.splitlines()[0]}")
  else:
    warnings.append(f"gcloud auth unavailable: {auth_err or 'no active account'}")

  build_code, build_out, _ = _run_gcloud(
    ["services", "list", "--enabled", "--filter=name:cloudbuild.googleapis.com", "--format=value(name)"],
    project=project,
  )
  if build_code == 0 and "cloudbuild.googleapis.com" in build_out:
    passes.append("Cloud Build API enabled: yes")
  elif build_code == 0:
    warnings.append("Cloud Build API enabled: no")
  else:
    warnings.append("Cloud Build API status: unknown")

  run_code, _, run_err = _run_gcloud(
    ["run", "services", "describe", service, "--region", region, "--format=value(metadata.name)"],
    project=project,
  )
  if run_code == 0:
    passes.append(f"Cloud Run service reachable: {service}")
  else:
    warnings.append(f"Cloud Run service describe failed: {run_err or service}")

  warnings.append(
    "IAM reminder: Cloud Build SA needs roles/run.admin, roles/iam.serviceAccountUser, "
    "roles/secretmanager.secretAccessor"
  )
  warnings.append("Artifact Registry not required when using gcloud run deploy --source (buildpacks)")

  return passes, warnings, failures


def print_report(passes: list[str], warnings: list[str], failures: list[str]) -> int:
  for item in passes:
    print(f"PASS: {item}")
  for item in warnings:
    print(f"WARN: {item}")
  for item in failures:
    print(f"FAIL: {item}")

  if failures:
    print("CI/CD readiness: FAILED")
    return 1
  if warnings:
    print("CI/CD readiness: WARN")
    return 0
  print("CI/CD readiness: OK")
  return 0


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(description="CI/CD preflight checks (read-only).")
  parser.add_argument("--project", default=DEFAULT_PROJECT_ID)
  parser.add_argument("--region", default=DEFAULT_REGION)
  parser.add_argument("--service", default=DEFAULT_SERVICE)
  parser.add_argument("--skip-gcloud", action="store_true")
  return parser


def main(argv: list[str] | None = None) -> int:
  args = build_parser().parse_args(argv)
  passes, warnings, failures = run_checks(
    project=args.project,
    region=args.region,
    service=args.service,
    skip_gcloud=args.skip_gcloud,
  )
  return print_report(passes, warnings, failures)


if __name__ == "__main__":
  raise SystemExit(main())
