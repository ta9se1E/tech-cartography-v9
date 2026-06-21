#!/usr/bin/env python3
"""Pre-deploy checks for Cloud Run live beta (Phase 25C–25E)."""

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
from tech_cartography.runtime.external_api_guard import check_live_tavily_smoke_allowed  # noqa: E402
from tech_cartography.services.live_tavily_search import clamp_max_results  # noqa: E402


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
  tavily_service = PROJECT_ROOT / "src/tech_cartography/services/live_tavily_search.py"
  tavily_ui = PROJECT_ROOT / "src/tech_cartography/ui/live_tavily_search_ui.py"
  tavily_docs = PROJECT_ROOT / "docs/phase25d_live_tavily_web_search_smoke_test.md"
  pack_service = PROJECT_ROOT / "src/tech_cartography/services/live_web_signal_pack.py"
  pack_ui = PROJECT_ROOT / "src/tech_cartography/ui/live_web_signal_pack_ui.py"
  pack_docs = PROJECT_ROOT / "docs/phase25e_live_tavily_web_signal_pack_integration.md"

  for path in (
    module_path,
    guard_path,
    ui_path,
    docs_path,
    tavily_service,
    tavily_ui,
    tavily_docs,
    pack_service,
    pack_ui,
    pack_docs,
  ):
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

  analyst_ui = _read(PROJECT_ROOT / "src/tech_cartography/ui/theme_validation_ui.py")
  tavily_ui_text = _read(tavily_ui)
  pack_ui_text = _read(pack_ui)
  market_ui = _read(PROJECT_ROOT / "src/tech_cartography/ui/v7_easy_app.py")
  if "render_live_tavily_smoke_test_section" in analyst_ui and "render_live_web_signal_pack_section" not in analyst_ui:
    failures.append("theme_validation_ui が live web signal pack UI に更新されていません")
  if "render_live_web_signal_pack_section" not in analyst_ui:
    failures.append("theme_validation_ui に live web signal pack UI がありません")
  if "Web Signal Packを作成" not in pack_ui_text:
    failures.append("live_web_signal_pack_ui に pack 作成ボタンがありません")
  if "render_live_web_signal_candidates_section" not in market_ui:
    failures.append("v7_easy_app market タブに live candidates セクションがありません")
  if clamp_max_results(99) != 3:
    failures.append("live Tavily max_results が 3 を超えてしまいます")

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

    allowed_smoke, smoke_reason = check_live_tavily_smoke_allowed(
      login_required=True,
      is_authenticated=True,
      auth_role="admin",
    )
    if allowed_smoke:
      failures.append("DISABLE_EXTERNAL_API=true でも live Tavily smoke が許可されています")
    if smoke_reason != "disabled_by_env":
      failures.append(f"live Tavily smoke block reason が不正: {smoke_reason}")
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
  print(f"live tavily smoke: {'yes' if tavily_service.exists() else 'no'}")
  print(f"live web signal pack: {'yes' if pack_service.exists() else 'no'}")

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
