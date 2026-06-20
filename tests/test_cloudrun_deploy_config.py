"""Tests for Cloud Run deploy configuration files (Phase 24.6)."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_procfile_exists_and_uses_port_env() -> None:
  procfile = PROJECT_ROOT / "Procfile"
  assert procfile.exists()
  text = procfile.read_text(encoding="utf-8")
  assert "streamlit run app.py" in text
  assert "0.0.0.0" in text
  assert "${PORT" in text or "$PORT" in text
  assert "server.headless=true" in text
  assert "server.fileWatcherType=none" in text
  assert "browser.gatherUsageStats=false" in text


def test_gcloudignore_includes_demo_bundle() -> None:
  text = (PROJECT_ROOT / ".gcloudignore").read_text(encoding="utf-8")
  assert "outputs/**" in text
  assert "US-12565719-B2" in text
  assert ".env" in text
  assert "tavily_pan_carbon_fiber" in text


def test_dockerignore_exists() -> None:
  text = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8")
  assert "outputs/**" in text
  assert "US-12565719-B2" in text


def test_env_example_cloud_run_values_without_port() -> None:
  text = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
  assert "SHOW_DEVELOPER_MODE=false" in text
  assert "APP_DEFAULT_MODE=demo" in text
  assert "DISABLE_EXTERNAL_API=true" in text
  assert "DISABLE_EMAIL_SEND=true" in text
  assert "DISABLE_SCHEDULER=true" in text
  assert "PORT=" not in text


def test_runtime_txt_present() -> None:
  assert (PROJECT_ROOT / "runtime.txt").exists()


def test_check_script_exists() -> None:
  script = PROJECT_ROOT / "scripts" / "check_cloudrun_demo_ready.py"
  assert script.exists()
  text = script.read_text(encoding="utf-8")
  assert "missing_demo_output_paths" in text
  assert "SHOW_DEVELOPER_MODE=false" in text
