#!/usr/bin/env python3
"""Pre-deploy checks for Cloud Run minimal demo (Phase 24.6 / 24.6A)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from tech_cartography.runtime.cloud_run_config import (  # noqa: E402
  APP_DEFAULT_MODE_ENV,
  DISABLE_EMAIL_SEND_ENV,
  DISABLE_EXTERNAL_API_ENV,
  DISABLE_SCHEDULER_ENV,
  missing_demo_output_paths,
)
from tech_cartography.runtime.demo_output_paths import (  # noqa: E402
  DEMO_OUTPUTS_ROOT_ENV,
  REQUIRED_BUNDLE_FILES,
  demo_bundle_dir,
  missing_bundle_files,
  relative_upload_path,
  resolve_bundle_or_legacy,
)
from tech_cartography.ui.developer_mode_visibility import (  # noqa: E402
  SHOW_DEVELOPER_MODE_ENV,
  is_show_developer_mode_enabled,
)


def _read(path: Path) -> str:
  if not path.exists():
    return ""
  return path.read_text(encoding="utf-8")


def _ignore_text(dot_name: str) -> str:
  dot_path = PROJECT_ROOT / dot_name
  if dot_path.exists():
    return _read(dot_path)
  kind = dot_name.lstrip(".")
  canonical = PROJECT_ROOT / "config" / f"cloudrun.{kind}"
  return _read(canonical)


def _git_tracks_env() -> bool:
  try:
    result = subprocess.run(
      ["git", "ls-files", "--error-unmatch", ".env"],
      cwd=PROJECT_ROOT,
      capture_output=True,
      text=True,
      check=False,
    )
    return result.returncode == 0
  except OSError:
    return False


def _gcloud_upload_files() -> list[str] | None:
  try:
    result = subprocess.run(
      ["gcloud", "meta", "list-files-for-upload", "."],
      cwd=PROJECT_ROOT,
      capture_output=True,
      text=True,
      check=False,
    )
  except OSError:
    return None
  if result.returncode != 0:
    return None
  return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _upload_includes(required_relative: str, upload_files: list[str]) -> bool:
  normalized = required_relative.replace("\\", "/")
  return any(
    path == normalized or path.endswith(f"/{normalized}") or normalized in path
    for path in upload_files
  )


def main() -> int:
  failures: list[str] = []
  warnings: list[str] = []

  procfile = PROJECT_ROOT / "Procfile"
  dockerfile = PROJECT_ROOT / "Dockerfile"
  if not procfile.exists() and not dockerfile.exists():
    failures.append("Procfile または Dockerfile が必要です")

  gcloudignore = PROJECT_ROOT / ".gcloudignore"
  dockerignore = PROJECT_ROOT / ".dockerignore"
  if not gcloudignore.exists() and not (PROJECT_ROOT / "config/cloudrun.gcloudignore").exists():
    failures.append(".gcloudignore または config/cloudrun.gcloudignore が必要です")
  if not dockerignore.exists() and not (PROJECT_ROOT / "config/cloudrun.dockerignore").exists():
    failures.append(".dockerignore または config/cloudrun.dockerignore が必要です")

  if _git_tracks_env():
    failures.append(".env が git 追跡対象です")

  env_example = _read(PROJECT_ROOT / ".env.example")
  for token in (
    "SHOW_DEVELOPER_MODE=false",
    "APP_DEFAULT_MODE=demo",
    "DEMO_OUTPUTS_ROOT=demo_outputs",
    "DISABLE_EXTERNAL_API=true",
    "DISABLE_EMAIL_SEND=true",
    "DISABLE_SCHEDULER=true",
    "STREAMLIT_SERVER_HEADLESS=true",
  ):
    if token not in env_example:
      failures.append(f".env.example に {token} がありません")

  if "PORT=" in env_example:
    failures.append(".env.example に PORT 固定値を書かないでください")

  gcloudignore_text = _ignore_text(".gcloudignore")
  if "demo_outputs/" in gcloudignore_text or "demo_outputs\n" in gcloudignore_text:
    failures.append(".gcloudignore が demo_outputs を除外しています")
  if "outputs/" not in gcloudignore_text:
    warnings.append(".gcloudignore に outputs/ 除外が見つかりません")

  procfile_text = _read(procfile)
  if procfile.exists():
    if "0.0.0.0" not in procfile_text:
      failures.append("Procfile に --server.address=0.0.0.0 が必要です")
    if "${PORT" not in procfile_text and "$PORT" not in procfile_text:
      failures.append("Procfile は Cloud Run 注入 PORT を参照する必要があります")
    if "server.headless=true" not in procfile_text:
      failures.append("Procfile に --server.headless=true が必要です")

  bundle_dir = demo_bundle_dir(PROJECT_ROOT)
  if not bundle_dir.exists():
    failures.append(f"demo_outputs bundle dir missing: {bundle_dir}")

  missing_bundle = missing_bundle_files(PROJECT_ROOT)
  if missing_bundle:
    failures.append(f"demo_outputs bundle 不足 ({len(missing_bundle)}): {missing_bundle[0]}")

  missing_outputs = missing_demo_output_paths(PROJECT_ROOT)
  upload_files = _gcloud_upload_files()
  upload_ok_count = 0
  if upload_files is None:
    warnings.append("gcloud meta list-files-for-upload を実行できませんでした（gcloud 未インストール等）")
  else:
    missing_upload = [
      relative_upload_path(name)
      for name in REQUIRED_BUNDLE_FILES
      if not _upload_includes(relative_upload_path(name), upload_files)
    ]
    upload_ok_count = len(REQUIRED_BUNDLE_FILES) - len(missing_upload)
    if missing_upload:
      failures.append(
        f"Cloud Run upload bundle 不足 ({len(missing_upload)}): {missing_upload[0]}",
      )
    else:
      print("Cloud Run upload bundle: OK")
    print(f"Demo output files included for upload: {upload_ok_count}/{len(REQUIRED_BUNDLE_FILES)}")

  if is_show_developer_mode_enabled():
    failures.append(f"{SHOW_DEVELOPER_MODE_ENV} 未設定時は開発者向けを非表示にしてください")

  import os

  saved = {key: os.environ.get(key) for key in (
    DISABLE_EXTERNAL_API_ENV,
    DISABLE_EMAIL_SEND_ENV,
    DISABLE_SCHEDULER_ENV,
    APP_DEFAULT_MODE_ENV,
    SHOW_DEVELOPER_MODE_ENV,
    DEMO_OUTPUTS_ROOT_ENV,
  )}
  try:
    os.environ[DISABLE_EXTERNAL_API_ENV] = "true"
    os.environ[DISABLE_EMAIL_SEND_ENV] = "true"
    os.environ[DISABLE_SCHEDULER_ENV] = "true"
    os.environ[APP_DEFAULT_MODE_ENV] = "demo"
    os.environ[DEMO_OUTPUTS_ROOT_ENV] = "demo_outputs"
    os.environ.pop(SHOW_DEVELOPER_MODE_ENV, None)

    from tech_cartography.runtime.cloud_run_config import (  # noqa: WPS433
      default_app_mode,
      is_email_send_disabled,
      is_external_api_disabled,
      is_scheduler_disabled,
    )

    if default_app_mode() != "demo":
      failures.append("APP_DEFAULT_MODE=demo が demo を返しません")
    if not is_external_api_disabled():
      failures.append("DISABLE_EXTERNAL_API=true が有効になりません")
    if not is_email_send_disabled():
      failures.append("DISABLE_EMAIL_SEND=true が有効になりません")
    if not is_scheduler_disabled():
      failures.append("DISABLE_SCHEDULER=true が有効になりません")
    if is_show_developer_mode_enabled():
      failures.append("SHOW_DEVELOPER_MODE 未設定で開発者向けが表示状態です")

    evidence_path = resolve_bundle_or_legacy(
      PROJECT_ROOT,
      "evidence_map_synthesis.md",
      "outputs/evidence_map_synthesis/US-12565719-B2/evidence_map_synthesis.md",
    )
    if not evidence_path.exists():
      failures.append("DEMO_OUTPUTS_ROOT=demo_outputs で evidence_map_synthesis.md を解決できません")

    from tech_cartography.delivery.email_sender import can_send_email  # noqa: WPS433

    ready, reason = can_send_email()
    if ready:
      failures.append("DISABLE_EMAIL_SEND=true でも can_send_email() が True です")
    elif "DISABLE_EMAIL_SEND" not in reason:
      warnings.append(f"can_send_email() reason: {reason}")

    delivery_ui = _read(PROJECT_ROOT / "src/tech_cartography/ui/delivery_ui.py")
    if "is_scheduler_disabled" not in delivery_ui:
      failures.append("delivery_ui に scheduler disable ガードがありません")

    report_ui = _read(PROJECT_ROOT / "src/tech_cartography/ui/report_tab_ui.py")
    sidebar_ui = _read(PROJECT_ROOT / "src/tech_cartography/ui/demo_safe_ui.py")
    sidebar_normal = sidebar_ui.split("if ui_mode_input == UI_MODE_DEVELOPER:", 1)[0]
    if "/Users/" in report_ui.split("def render_compressed_report_tab", 1)[1].split(
      "def render_developer_report_expander",
      1,
    )[0]:
      failures.append("通常レポートに /Users/ パスが含まれています")
    if "/Users/" in sidebar_normal:
      failures.append("通常サイドバーに /Users/ パスが含まれています")
  finally:
    for key, value in saved.items():
      if value is None:
        os.environ.pop(key, None)
      else:
        os.environ[key] = value

  print(f"Project: {PROJECT_ROOT}")
  print(f"Procfile: {'yes' if procfile.exists() else 'no'}")
  print(f"Dockerfile: {'yes' if dockerfile.exists() else 'no'}")
  print(f".gcloudignore: {'yes' if gcloudignore.exists() else 'no'}")
  print(f".dockerignore: {'yes' if dockerignore.exists() else 'no'}")
  print(f"demo_outputs bundle missing files: {len(missing_bundle)}")
  print(f"legacy demo output paths missing: {len(missing_outputs)}")

  for warning in warnings:
    print(f"WARN: {warning}")

  if failures:
    print("Cloud Run demo readiness: FAILED")
    for item in failures:
      print(f"- {item}")
    return 1

  print("Cloud Run demo readiness: OK")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
