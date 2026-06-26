"""Quality tests for Phase27N Cloud Run readiness guidance."""

from __future__ import annotations

import json
import re
from pathlib import Path

from tech_cartography.services.v8_cloud_run_readiness import build_cloud_run_readiness_report
from tech_cartography.services.v8_cloud_run_readiness_export import export_cloud_run_readiness

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_no_secrets_in_export() -> None:
  report = build_cloud_run_readiness_report(project_root=PROJECT_ROOT)
  result = export_cloud_run_readiness(report, project_root=PROJECT_ROOT)
  secret_pattern = re.compile(
    r"(smtp_password\s*[:=]\s*\S+|api_key\s*[:=]\s*\S{12,})",
    re.IGNORECASE,
  )
  for path in Path(result.output_dir).glob("*"):
    if path.suffix in {".json", ".md"}:
      assert not secret_pattern.search(path.read_text(encoding="utf-8"))


def test_dockerignore_excludes_env_and_outputs() -> None:
  text = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8")
  assert ".env" in text
  assert "outputs" in text


def test_docs_no_fto_legal_judgement_only_disclaimer() -> None:
  docs = (PROJECT_ROOT / "docs" / "cloud_run_v8_prepare.md").read_text(encoding="utf-8")
  assert "FTO" in docs or "侵害" in docs or "有効性" in docs or "legal" in docs.lower()


def test_report_flags_no_build_deploy() -> None:
  report = build_cloud_run_readiness_report(project_root=PROJECT_ROOT)
  d = report.to_dict()
  assert d["no_cloud_build_executed"] is True
  assert d["no_cloud_run_deploy_executed"] is True
  assert d["no_email_send"] is True
  assert d["no_scheduler_start"] is True
  json.dumps(d)


def test_deep_dive_not_all_1000_in_docs() -> None:
  docs = (PROJECT_ROOT / "docs" / "cloud_run_v8_prepare.md").read_text(encoding="utf-8")
  assert "ephemeral" in docs.lower() or "/tmp" in docs
