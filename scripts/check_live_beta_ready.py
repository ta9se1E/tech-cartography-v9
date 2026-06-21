#!/usr/bin/env python3
"""Pre-deploy checks for Cloud Run live beta (Phase 25C)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from tech_cartography.runtime.api_secret_config import (  # noqa: E402
  KNOWN_API_SECRETS,
  can_use_external_api,
  get_api_secret_status,
  is_secret_present,
)
from tech_cartography.runtime.cloud_run_config import (  # noqa: E402
  DISABLE_EXTERNAL_API_ENV,
  is_external_api_disabled,
)


def _read(path: Path) -> str:
  if not path.exists():
    return ""
  return path.read_text(encoding="utf-8")


def main() -> int:
  failures: list[str] = []
  warnings: list[str] = []

  module_path = PROJECT_ROOT / "src/tech_cartography/runtime/api_secret_config.py"
  guard_path = PROJECT_ROOT / "src/tech_cartography/runtime/external_api_guard.py"
  ui_path = PROJECT_ROOT / "src/tech_cartography/ui/api_secret_status_ui.py"
  docs_path = PROJECT_ROOT / "docs/phase25c_live_api_secret_foundation.md"

  for path in (module_path, guard_path, ui_path, docs_path):
    if not path.exists():
      failures.append(f"missing: {path.relative_to(PROJECT_ROOT)}")

  env_example = _read(PROJECT_ROOT / ".env.example")
  for token in (
    "OPENAI_API_KEY=<secret-manager-only>",
    "GEMINI_API_KEY=<secret-manager-only>",
    "TAVILY_API_KEY=<secret-manager-only>",
    "Secret Manager",
  ):
    if token not in env_example:
      failures.append(f".env.example に {token!r} がありません")

  ui_text = _read(ui_path)
  if "APIキー本体は表示しません" not in ui_text:
    failures.append("api_secret_status_ui に秘密値非表示の注意がありません")

  settings_ui = _read(PROJECT_ROOT / "src/tech_cartography/ui/user_settings_view.py")
  sidebar_ui = _read(PROJECT_ROOT / "src/tech_cartography/ui/demo_safe_ui.py")
  if "render_api_secret_status_expander" not in settings_ui:
    failures.append("user_settings_view に admin API status UI がありません")
  if "render_api_secret_status_expander" not in sidebar_ui:
    failures.append("demo_safe_ui sidebar に admin API status UI がありません")

  saved_disable = os.environ.get(DISABLE_EXTERNAL_API_ENV)
  try:
    os.environ[DISABLE_EXTERNAL_API_ENV] = "true"
    if not is_external_api_disabled():
      failures.append("DISABLE_EXTERNAL_API=true が有効になりません")

    allowed, missing = can_use_external_api(["TAVILY_API_KEY"])
    if allowed:
      failures.append("DISABLE_EXTERNAL_API=true でも can_use_external_api が True です")

    status = get_api_secret_status()
    if status["external_api_execution"] != "disabled":
      failures.append("get_api_secret_status が disabled を返しません")

    serialized = str(status)
    for name in KNOWN_API_SECRETS:
      os.environ[name] = "configured-test-value-not-real"
    status_with_keys = get_api_secret_status()
    if any(v != "configured" for v in status_with_keys["secrets"].values()):
      failures.append("configured env でも secrets status が configured になりません")
    if "configured-test-value-not-real" in json.dumps(status_with_keys):
      failures.append("get_api_secret_status が secret 値を含んでいます")
    for name in KNOWN_API_SECRETS:
      os.environ.pop(name, None)

    os.environ["TAVILY_API_KEY"] = "placeholder"
    if is_secret_present("TAVILY_API_KEY"):
      failures.append("placeholder が configured 扱いになっています")
    os.environ.pop("TAVILY_API_KEY", None)

    if any(secret_value in serialized for secret_value in ("configured-test-value", "placeholder")):
      failures.append("初期 get_api_secret_status が secret 値を含んでいます")
  finally:
    if saved_disable is None:
      os.environ.pop(DISABLE_EXTERNAL_API_ENV, None)
    else:
      os.environ[DISABLE_EXTERNAL_API_ENV] = saved_disable

  demo_ready = PROJECT_ROOT / "scripts/check_cloudrun_demo_ready.py"
  if not demo_ready.exists():
    warnings.append("check_cloudrun_demo_ready.py がありません")

  print(f"Project: {PROJECT_ROOT}")
  print(f"api_secret_config: {'yes' if module_path.exists() else 'no'}")
  print(f"external_api_guard: {'yes' if guard_path.exists() else 'no'}")
  print(f"admin status UI: {'yes' if ui_path.exists() else 'no'}")

  for warning in warnings:
    print(f"WARN: {warning}")

  if failures:
    print("Cloud Run live beta readiness: FAILED")
    for item in failures:
      print(f"- {item}")
    return 1

  print("Cloud Run live beta readiness: OK")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
