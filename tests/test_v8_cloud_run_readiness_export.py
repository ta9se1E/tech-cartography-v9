"""Tests for v8 Cloud Run readiness export (Phase 27N)."""

from __future__ import annotations

import re
from pathlib import Path

from tech_cartography.services.v8_cloud_run_readiness import build_cloud_run_readiness_report
from tech_cartography.services.v8_cloud_run_readiness_export import export_cloud_run_readiness

PROJECT_ROOT = Path(__file__).resolve().parents[1]

_SECRET_RE = re.compile(r"smtp_password\s*[:=]\s*\S+|tavily_api_key\s*[:=]\s*\S{8,}", re.IGNORECASE)


def test_export_generates_all_files(tmp_path: Path, monkeypatch) -> None:
  monkeypatch.chdir(tmp_path)
  (tmp_path / "app.py").write_text('DEFAULT_UI_VERSION = "v8"\n', encoding="utf-8")
  (tmp_path / "requirements.txt").write_text("streamlit\nopenpyxl\nPyYAML\n", encoding="utf-8")
  (tmp_path / "Procfile").write_text(
    "web: streamlit run app.py --server.port=${PORT:-8080} --server.address=0.0.0.0\n",
    encoding="utf-8",
  )
  (tmp_path / "docs").mkdir()
  (tmp_path / "docs" / "cloud_run_v8_prepare.md").write_text(
    "LIVE_OUTPUTS_ROOT /tmp Phase27N Cloud Build 実行しません Cloud Run deploy 実行しません",
    encoding="utf-8",
  )
  (tmp_path / "outputs").mkdir()
  (tmp_path / "src").mkdir()
  (tmp_path / "src" / "tech_cartography").mkdir(parents=True)
  (tmp_path / "src" / "tech_cartography" / "ui").mkdir()
  (tmp_path / "src" / "tech_cartography" / "ui" / "v8_user_flow_app.py").write_text("", encoding="utf-8")

  report = build_cloud_run_readiness_report(project_root=tmp_path)
  result = export_cloud_run_readiness(report, project_root=tmp_path)

  out = Path(result.output_dir)
  for fname in (
    "cloud_run_readiness_report.json",
    "cloud_run_readiness_report.md",
    "cloud_run_readiness_manifest.json",
    "deploy_preparation_checklist.md",
    "demo_data_checklist.md",
    "operator_checklist.md",
    "env_var_template.md",
    "artifact_policy.md",
  ):
    assert (out / fname).is_file(), fname

  env_md = (out / "env_var_template.md").read_text(encoding="utf-8")
  assert not _SECRET_RE.search(env_md)
  assert "Secret Manager" in env_md or "secret" in env_md.lower()


def test_export_no_secrets_in_markdown() -> None:
  report = build_cloud_run_readiness_report(project_root=PROJECT_ROOT)
  result = export_cloud_run_readiness(report, project_root=PROJECT_ROOT)
  md = Path(result.md_path).read_text(encoding="utf-8")
  assert not _SECRET_RE.search(md)
  assert "no_cloud_build_executed" in md or "Cloud Build" in md
