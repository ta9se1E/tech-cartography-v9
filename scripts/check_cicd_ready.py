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

DEPLOY_STEP_FORBIDDEN_PATTERNS = (
  re.compile(r"\bpip3?\s+install\b"),
  re.compile(r"python3?\s+-m\s+pip\b"),
  re.compile(r"--break-system-packages\b"),
  re.compile(r"\bapt-get\s+install\b.*python"),
  re.compile(r"check_iap_cutover_ready\.py"),
)


def _cloudbuild_step_body(text: str, step_id: str) -> str:
  pattern = (
    rf"- id: {re.escape(step_id)}\b.*?\n\s+args:\s*\n\s+- -ceu\s*\n\s+- \|\s*\n"
    r"(.*?)(?=\n\s+- id: |\ntimeout:|\Z)"
  )
  match = re.search(pattern, text, re.DOTALL)
  return match.group(1) if match else ""


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
    if re.search(r"gcloud\s+run\s+.*--no-iap", cloudbuild_text):
      failures.append("cloudbuild.yaml must not disable IAP")
    if "AUTH_PROVIDER_MODE=iap" not in cloudbuild_text:
      warnings.append("cloudbuild.yaml should set AUTH_PROVIDER_MODE=iap")
    if "ENABLE_APPROVED_MEMBER_SEND=false" not in cloudbuild_text:
      failures.append("cloudbuild.yaml must default ENABLE_APPROVED_MEMBER_SEND=false")
    if "ENABLE_WATCH_PROFILE_MANAGEMENT=false" not in cloudbuild_text:
      failures.append("cloudbuild.yaml must default ENABLE_WATCH_PROFILE_MANAGEMENT=false")
    if "ENABLE_MANUAL_WEB_SIGNAL_COLLECTION=false" not in cloudbuild_text:
      failures.append("cloudbuild.yaml must default ENABLE_MANUAL_WEB_SIGNAL_COLLECTION=false")
    if "DISABLE_EXTERNAL_API=true" not in cloudbuild_text:
      failures.append("cloudbuild.yaml must default DISABLE_EXTERNAL_API=true")
    if "DISABLE_EMAIL_SEND=true" not in cloudbuild_text:
      failures.append("cloudbuild.yaml must default DISABLE_EMAIL_SEND=true")
    if "TECH_CARTOGRAPHY_APPROVED_MEMBER_EMAILS=" in cloudbuild_text:
      failures.append("cloudbuild.yaml must not inline TECH_CARTOGRAPHY_APPROVED_MEMBER_EMAILS")
    if re.search(r"DISABLE_SCHEDULER\s*=\s*false", cloudbuild_text):
      failures.append("cloudbuild.yaml must not enable scheduler")
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

    quality_gate_body = _cloudbuild_step_body(cloudbuild_text, "quality-gate")
    deploy_step_body = _cloudbuild_step_body(cloudbuild_text, "iap-preflight-and-deploy")
    if not quality_gate_body:
      failures.append("cloudbuild.yaml quality-gate step body not found")
    elif "pip install" not in quality_gate_body:
      failures.append("cloudbuild.yaml quality-gate must install Python dependencies")
    if not deploy_step_body:
      failures.append("cloudbuild.yaml deploy step body not found")
    else:
      if "gcloud run deploy" not in deploy_step_body:
        failures.append("cloudbuild.yaml deploy step must run gcloud run deploy")
      if "gcloud storage buckets describe" not in deploy_step_body:
        failures.append("cloudbuild.yaml deploy step must describe live artifacts bucket")
      for pattern in DEPLOY_STEP_FORBIDDEN_PATTERNS:
        if pattern.search(deploy_step_body):
          failures.append(
            f"cloudbuild.yaml deploy step must be gcloud-only (forbidden: {pattern.pattern})",
          )
      if "gcloud config set project" not in deploy_step_body:
        failures.append("cloudbuild.yaml deploy step must set gcloud project")
      passes.append("cloudbuild deploy step: gcloud-only (no pip install)")

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
    if "ENABLE_APPROVED_MEMBER_SEND=false" not in deploy_text:
      failures.append("deploy_live_safe.sh must default ENABLE_APPROVED_MEMBER_SEND=false")
    if "ENABLE_WATCH_PROFILE_MANAGEMENT=false" not in deploy_text:
      failures.append("deploy_live_safe.sh must default ENABLE_WATCH_PROFILE_MANAGEMENT=false")
    if "TECH_CARTOGRAPHY_APPROVED_MEMBER_EMAILS=" in deploy_text:
      failures.append("deploy_live_safe.sh must not inline TECH_CARTOGRAPHY_APPROVED_MEMBER_EMAILS")

  if rollback_text:
    if "read -rs" not in rollback_text and "read -s" not in rollback_text:
      failures.append("rollback_live_to_basic.sh must read password with read -s")
    if "unset TC_LOGIN_PASSWORD" not in rollback_text:
      warnings.append("rollback_live_to_basic.sh should unset TC_LOGIN_PASSWORD")
    if "DISABLE_EMAIL_SEND=true" not in rollback_text:
      failures.append("rollback_live_to_basic.sh must keep DISABLE_EMAIL_SEND=true")
    if "ENABLE_APPROVED_MEMBER_SEND=false" not in rollback_text:
      failures.append("rollback_live_to_basic.sh must keep ENABLE_APPROVED_MEMBER_SEND=false")
    if "SMTP_PASSWORD" in rollback_text:
      failures.append("rollback_live_to_basic.sh must not contain SMTP_PASSWORD")

  watch_profile_docs = PROJECT_ROOT / "docs/phase25s_watch_profile_management.md"
  watch_profile_manager = PROJECT_ROOT / "src/tech_cartography/services/live_watch_profile_manager.py"
  if not watch_profile_docs.exists():
    failures.append("missing: docs/phase25s_watch_profile_management.md")
  else:
    passes.append("phase25s watch profile docs present")
  if watch_profile_manager.exists():
    mgr_text = _read(watch_profile_manager)
    for forbidden in ("requests.", "smtplib", "send_email"):
      if forbidden in mgr_text:
        failures.append(f"live_watch_profile_manager contains forbidden {forbidden}")
    if "_SENSITIVE_PATTERN" not in mgr_text:
      failures.append("live_watch_profile_manager missing sensitive guard")

  web_signal_collection_docs = PROJECT_ROOT / "docs/phase25t_controlled_web_signal_collection.md"
  web_signal_collector = PROJECT_ROOT / "src/tech_cartography/services/live_web_signal_collector.py"
  if not web_signal_collection_docs.exists():
    failures.append("missing: docs/phase25t_controlled_web_signal_collection.md")
  if web_signal_collector.exists():
    coll = _read(web_signal_collector)
    if "smtplib" in coll or "send_email" in coll:
      failures.append("live_web_signal_collector contains forbidden email/scheduler calls")
    if "legal_judgement" not in coll:
      failures.append("live_web_signal_collector missing legal_judgement safety flag")

  web_signal_digest_docs = PROJECT_ROOT / "docs/phase25u_web_signal_digest_integration.md"
  web_signal_artifact_reader = PROJECT_ROOT / "src/tech_cartography/services/live_web_signal_artifact_reader.py"
  web_signal_review_ui = PROJECT_ROOT / "src/tech_cartography/ui/live_web_signal_review_ui.py"
  web_signal_review = PROJECT_ROOT / "src/tech_cartography/services/live_web_signal_review.py"
  if not web_signal_digest_docs.exists():
    failures.append("missing: docs/phase25u_web_signal_digest_integration.md")
  else:
    passes.append("phase25u web signal digest docs present")
  for path, label in (
    (web_signal_artifact_reader, "live_web_signal_artifact_reader.py"),
    (web_signal_review, "live_web_signal_review.py"),
    (web_signal_review_ui, "live_web_signal_review_ui.py"),
  ):
    if not path.exists():
      failures.append(f"missing: {label}")
    else:
      passes.append(f"artifact exists: {path.relative_to(PROJECT_ROOT)}")
  if web_signal_review.exists():
    review_text = _read(web_signal_review)
    if "collect_live_web_signals" in review_text or "_default_post_tavily" in review_text:
      failures.append("live_web_signal_review must not call external API")
    if "candidate_information_only" not in review_text:
      failures.append("live_web_signal_review missing candidate_information_only flag")

  digest_service = PROJECT_ROOT / "src/tech_cartography/services/live_digest_preview.py"
  if digest_service.exists():
    digest_svc_text = _read(digest_service)
    if "collect_live_web_signals" in digest_svc_text:
      failures.append("live_digest_preview must not auto-call web signal collector")
    if "evaluate_digest_preview_access" not in digest_svc_text and "evaluate_live_admin_access" not in digest_svc_text:
      failures.append("live_digest_preview missing IAP-safe auth guard")
    if "candidate_information_only" not in digest_svc_text:
      failures.append("live_digest_preview missing candidate_information_only metadata")
    if "fto_judgement" not in digest_svc_text:
      failures.append("live_digest_preview missing fto_judgement safety flag")

  phase25v_docs = PROJECT_ROOT / "docs/phase25v_evidence_gap_strategic_watch_brief.md"
  evidence_gap_builder = PROJECT_ROOT / "src/tech_cartography/services/live_evidence_gap_builder.py"
  strategic_brief = PROJECT_ROOT / "src/tech_cartography/services/live_strategic_watch_brief.py"
  if not phase25v_docs.exists():
    failures.append("missing: docs/phase25v_evidence_gap_strategic_watch_brief.md")
  else:
    passes.append("phase25v evidence gap docs present")
  for path, label in (
    (PROJECT_ROOT / "src/tech_cartography/runtime/evidence_gap_schema.py", "evidence_gap_schema.py"),
    (evidence_gap_builder, "live_evidence_gap_builder.py"),
    (strategic_brief, "live_strategic_watch_brief.py"),
    (PROJECT_ROOT / "src/tech_cartography/ui/live_evidence_gap_ui.py", "live_evidence_gap_ui.py"),
    (PROJECT_ROOT / "src/tech_cartography/ui/live_strategic_watch_brief_ui.py", "live_strategic_watch_brief_ui.py"),
  ):
    if not path.exists():
      failures.append(f"missing: {label}")
    else:
      passes.append(f"artifact exists: {path.relative_to(PROJECT_ROOT)}")
  if evidence_gap_builder.exists():
    gap_text = _read(evidence_gap_builder)
    if "deep_research" in gap_text.lower() or "collect_live_web_signals" in gap_text:
      failures.append("live_evidence_gap_builder must not call external API")

  send_safety_docs = PROJECT_ROOT / "docs/phase25q2_send_safety_reset.md"
  if send_safety_docs.exists():
    passes.append(f"artifact exists: {send_safety_docs.relative_to(PROJECT_ROOT)}")
    safety_doc_text = _read(send_safety_docs)
    if "SMTP_PASSWORD" in safety_doc_text and "扱わない" not in safety_doc_text:
      failures.append("phase25q2 docs may inline SMTP_PASSWORD")
    if "ENABLE_APPROVED_MEMBER_SEND=false" not in safety_doc_text:
      failures.append("phase25q2 docs missing reset env guidance")
  else:
    failures.append("missing: docs/phase25q2_send_safety_reset.md")

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
