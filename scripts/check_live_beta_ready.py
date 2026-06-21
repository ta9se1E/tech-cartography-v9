#!/usr/bin/env python3
"""Pre-deploy checks for Cloud Run live beta (Phase 25C–25J)."""

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
  DISABLE_EMAIL_SEND_ENV,
  DISABLE_EXTERNAL_API_ENV,
  is_email_send_disabled,
  is_external_api_disabled,
)
from tech_cartography.runtime.email_send_config import (  # noqa: E402
  SELF_ONLY_SEND_MODE,
  can_send_self_only_email,
)
from tech_cartography.services.live_digest_preview import can_create_live_digest_preview  # noqa: E402
from tech_cartography.runtime.external_api_guard import check_live_tavily_smoke_allowed  # noqa: E402
from tech_cartography.runtime.live_artifact_paths import (  # noqa: E402
  describe_live_artifact_storage,
  ensure_live_artifact_dirs,
  get_live_outputs_root,
  using_live_outputs_root_env,
)
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
  digest_service = PROJECT_ROOT / "src/tech_cartography/services/live_digest_preview.py"
  digest_ui = PROJECT_ROOT / "src/tech_cartography/ui/live_digest_preview_ui.py"
  digest_docs = PROJECT_ROOT / "docs/phase25f_live_digest_mail_preview.md"
  email_cfg = PROJECT_ROOT / "src/tech_cartography/runtime/email_send_config.py"
  email_sender = PROJECT_ROOT / "src/tech_cartography/services/live_email_sender.py"
  email_ui = PROJECT_ROOT / "src/tech_cartography/ui/live_email_send_ui.py"
  email_docs = PROJECT_ROOT / "docs/phase25g_self_only_live_digest_email_send_test.md"
  artifact_paths = PROJECT_ROOT / "src/tech_cartography/runtime/live_artifact_paths.py"
  artifact_ui = PROJECT_ROOT / "src/tech_cartography/ui/live_artifact_storage_ui.py"
  artifact_docs = PROJECT_ROOT / "docs/phase25h_live_artifact_persistence_cloud_storage.md"
  expansion_service = PROJECT_ROOT / "src/tech_cartography/services/live_watch_expansion_proposal.py"
  draft_service = PROJECT_ROOT / "src/tech_cartography/services/watch_profile_draft.py"
  expansion_ui = PROJECT_ROOT / "src/tech_cartography/ui/live_watch_expansion_ui.py"
  expansion_docs = PROJECT_ROOT / "docs/phase25i_human_approved_watch_expansion_proposal.md"
  next_cycle_plan = PROJECT_ROOT / "src/tech_cartography/services/live_next_cycle_search_plan.py"
  next_cycle_runner = PROJECT_ROOT / "src/tech_cartography/services/live_next_cycle_tavily_runner.py"
  next_cycle_ui = PROJECT_ROOT / "src/tech_cartography/ui/live_next_cycle_search_ui.py"
  next_cycle_docs = PROJECT_ROOT / "docs/phase25j_watch_profile_driven_next_cycle_search.md"

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
    digest_service,
    digest_ui,
    digest_docs,
    email_cfg,
    email_sender,
    email_ui,
    email_docs,
    artifact_paths,
    artifact_ui,
    artifact_docs,
    expansion_service,
    draft_service,
    expansion_ui,
    expansion_docs,
    next_cycle_plan,
    next_cycle_runner,
    next_cycle_ui,
    next_cycle_docs,
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
  if "LIVE_OUTPUTS_ROOT" not in env_example:
    failures.append(".env.example に LIVE_OUTPUTS_ROOT がありません")

  ui_text = _read(ui_path)
  if "APIキー本体は表示しません" not in ui_text:
    failures.append("api_secret_status_ui に秘密値非表示の注意がありません")

  settings_ui = _read(PROJECT_ROOT / "src/tech_cartography/ui/user_settings_view.py")
  sidebar_ui = _read(PROJECT_ROOT / "src/tech_cartography/ui/demo_safe_ui.py")
  if "render_api_secret_status_expander" not in settings_ui:
    failures.append("user_settings_view に admin API status UI がありません")
  if "render_api_secret_status_expander" not in sidebar_ui:
    failures.append("demo_safe_ui sidebar に admin API status UI がありません")
  if "render_live_artifact_storage_expander" not in settings_ui:
    failures.append("user_settings_view に live artifact storage UI がありません")

  analyst_ui = _read(PROJECT_ROOT / "src/tech_cartography/ui/theme_validation_ui.py")
  tavily_ui_text = _read(tavily_ui)
  pack_ui_text = _read(pack_ui)
  market_ui = _read(PROJECT_ROOT / "src/tech_cartography/ui/v7_easy_app.py")
  digest_ui_text = _read(digest_ui)
  email_ui_text = _read(email_ui)
  if "render_live_tavily_smoke_test_section" in analyst_ui and "render_live_web_signal_pack_section" not in analyst_ui:
    failures.append("theme_validation_ui が live web signal pack UI に更新されていません")
  if "render_live_web_signal_pack_section" not in analyst_ui:
    failures.append("theme_validation_ui に live web signal pack UI がありません")
  if "Web Signal Packを作成" not in pack_ui_text:
    failures.append("live_web_signal_pack_ui に pack 作成ボタンがありません")
  if "render_live_web_signal_candidates_section" not in market_ui:
    failures.append("v7_easy_app market タブに live candidates セクションがありません")
  if "render_live_digest_preview_section" not in analyst_ui:
    failures.append("theme_validation_ui に live digest preview UI がありません")
  if "メール下書きを作成" not in digest_ui_text:
    failures.append("live_digest_preview_ui に preview 作成ボタンがありません")
  if "send_email" in digest_ui_text.lower():
    failures.append("live_digest_preview_ui が send_email を参照しています")
  if "render_live_digest_preview_reports_section" not in market_ui:
    failures.append("v7_easy_app reports タブに live digest preview セクションがありません")
  if "render_live_email_send_section" not in analyst_ui:
    failures.append("theme_validation_ui に live email send UI がありません")
  if "render_live_artifact_storage_expander" not in analyst_ui:
    failures.append("theme_validation_ui に live artifact storage UI がありません")
  if "render_live_watch_expansion_section" not in analyst_ui:
    failures.append("theme_validation_ui に watch expansion UI がありません")
  expansion_ui_text = _read(expansion_ui)
  if "監視範囲の拡張候補を作成" not in expansion_ui_text:
    failures.append("live_watch_expansion_ui に proposal 作成ボタンがありません")
  if "update_watch_profile" in expansion_ui_text:
    failures.append("live_watch_expansion_ui が本番 watch profile を更新しています")
  if "render_watch_profile_draft_reports_section" not in market_ui:
    failures.append("v7_easy_app reports タブに watch profile draft セクションがありません")
  if "render_watch_profile_draft_reports_section" not in settings_ui:
    failures.append("user_settings_view に watch profile draft セクションがありません")
  if "resolve_watch_profile_draft_status" not in _read(draft_service):
    failures.append("watch_profile_draft が resolve_watch_profile_draft_status を提供していません")
  if "Watch Profile Draft Storage（管理者向け）" not in expansion_ui_text:
    failures.append("live_watch_expansion_ui に watch profile draft debug UI がありません")
  if "live_artifact_paths" not in _read(expansion_service):
    failures.append("live_watch_expansion_proposal が live_artifact_paths を使っていません")
  if "live_artifact_paths" not in _read(draft_service):
    failures.append("watch_profile_draft が live_artifact_paths を使っていません")
  next_cycle_ui_text = _read(next_cycle_ui)
  if "render_live_next_cycle_search_section" not in analyst_ui:
    failures.append("theme_validation_ui に next cycle search UI がありません")
  if "次回検索クエリ候補を作成" not in next_cycle_ui_text:
    failures.append("live_next_cycle_search_ui に plan 作成ボタンがありません")
  if "選択したクエリでTavily検索" not in next_cycle_ui_text:
    failures.append("live_next_cycle_search_ui に Tavily 実行ボタンがありません")
  if "render_live_next_cycle_search_reports_section" not in market_ui:
    failures.append("v7_easy_app reports タブに next cycle pack セクションがありません")
  if "live_artifact_paths" not in _read(next_cycle_plan):
    failures.append("live_next_cycle_search_plan が live_artifact_paths を使っていません")
  if "live_artifact_paths" not in _read(next_cycle_runner):
    failures.append("live_next_cycle_tavily_runner が live_artifact_paths を使っていません")
  if "source_type" not in _read(digest_service):
    failures.append("live_digest_preview が source_type 対応していません")
  if "CONFIRMATION_TEXT" not in email_ui_text and "SEND TO MYSELF" not in email_ui_text:
    failures.append("live_email_send_ui に確認テキスト要件がありません")
  if "SMTP_PASSWORD" in email_ui_text and "os.environ" in email_ui_text:
    failures.append("live_email_send_ui が SMTP_PASSWORD env を参照しています")
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

    saved_email_disable = os.environ.get(DISABLE_EMAIL_SEND_ENV)
    os.environ[DISABLE_EMAIL_SEND_ENV] = "true"
    if not is_email_send_disabled():
      failures.append("DISABLE_EMAIL_SEND=true が有効になりません")
    allowed_preview, preview_reason = can_create_live_digest_preview()
    if not allowed_preview:
      failures.append("DISABLE_EMAIL_SEND=true でも digest preview が不可です")
    if "preview" not in preview_reason.lower():
      failures.append(f"digest preview reason が不正: {preview_reason}")

    allowed_send, send_reason = can_send_self_only_email("me@example.com")
    if allowed_send:
      failures.append("DISABLE_EMAIL_SEND=true でも self_only email send が許可されています")
    if send_reason != "disabled_by_env":
      failures.append(f"self_only send block reason が不正: {send_reason}")

    os.environ[DISABLE_EMAIL_SEND_ENV] = "false"
    os.environ["EMAIL_SEND_MODE"] = SELF_ONLY_SEND_MODE
    os.environ["EMAIL_RECIPIENT_ALLOWLIST"] = "me@example.com"
    os.environ["SMTP_HOST"] = "smtp.example.com"
    os.environ["SMTP_PORT"] = "465"
    os.environ["SMTP_USERNAME"] = "me@example.com"
    os.environ.pop("SMTP_PASSWORD", None)
    allowed_send_missing_pw, send_reason_missing = can_send_self_only_email("me@example.com")
    if allowed_send_missing_pw:
      failures.append("SMTP_PASSWORD 未設定でも self_only send が許可されています")
    if send_reason_missing != "missing_smtp_config":
      failures.append(f"SMTP 不足 block reason が不正: {send_reason_missing}")

    if saved_email_disable is None:
      os.environ.pop(DISABLE_EMAIL_SEND_ENV, None)
    else:
      os.environ[DISABLE_EMAIL_SEND_ENV] = saved_email_disable
  finally:
    if saved_disable is None:
      os.environ.pop(DISABLE_EXTERNAL_API_ENV, None)
    else:
      os.environ[DISABLE_EXTERNAL_API_ENV] = saved_disable

  demo_ready = PROJECT_ROOT / "scripts/check_cloudrun_demo_ready.py"
  if not demo_ready.exists():
    warnings.append("check_cloudrun_demo_ready.py がありません")

  artifact_ui_text = _read(artifact_ui)
  if "Live Artifact Storage（管理者向け）" not in artifact_ui_text:
    failures.append("live_artifact_storage_ui に管理者向けタイトルがありません")
  if "SMTP_PASSWORD" in artifact_ui_text or "API_KEY" in artifact_ui_text:
    failures.append("live_artifact_storage_ui が secret 名を露出しています")

  pack_service_text = _read(pack_service)
  if "live_artifact_paths" not in pack_service_text:
    failures.append("live_web_signal_pack が live_artifact_paths を使っていません")
  if "live_artifact_paths" not in _read(digest_service):
    failures.append("live_digest_preview が live_artifact_paths を使っていません")
  if "live_artifact_paths" not in _read(email_sender):
    failures.append("live_email_sender が live_artifact_paths を使っていません")

  if using_live_outputs_root_env():
    print(f"live artifact storage: LIVE_OUTPUTS_ROOT configured")
    ok_dirs, dir_message = ensure_live_artifact_dirs(PROJECT_ROOT)
    if not ok_dirs:
      failures.append(f"live artifact dirs: {dir_message}")
    storage = describe_live_artifact_storage(PROJECT_ROOT)
    for label, is_writable in storage["writable"].items():
      if not is_writable:
        detail = storage["writable_messages"].get(label) or label
        failures.append(f"live artifact not writable: {detail}")
  else:
    print("live artifact storage: local outputs fallback (LIVE_OUTPUTS_ROOT unset)")
    fallback_root = get_live_outputs_root(PROJECT_ROOT)
    if fallback_root.name != "outputs":
      failures.append("LIVE_OUTPUTS_ROOT 未設定時の fallback root が outputs ではありません")
    storage = describe_live_artifact_storage(PROJECT_ROOT)
    serialized = json.dumps(storage)
    for secret_token in ("SMTP_PASSWORD", "OPENAI_API_KEY", "TAVILY_API_KEY", "configured-test-value"):
      if secret_token in serialized:
        failures.append("describe_live_artifact_storage が secret 値を含んでいます")

  print(f"Project: {PROJECT_ROOT}")
  print(f"api_secret_config: {'yes' if module_path.exists() else 'no'}")
  print(f"external_api_guard: {'yes' if guard_path.exists() else 'no'}")
  print(f"admin status UI: {'yes' if ui_path.exists() else 'no'}")
  print(f"live tavily smoke: {'yes' if tavily_service.exists() else 'no'}")
  print(f"live web signal pack: {'yes' if pack_service.exists() else 'no'}")
  print(f"live digest preview: {'yes' if digest_service.exists() else 'no'}")
  print(f"live email send: {'yes' if email_sender.exists() else 'no'}")
  print(f"live artifact paths: {'yes' if artifact_paths.exists() else 'no'}")
  print(f"live watch expansion: {'yes' if expansion_service.exists() else 'no'}")
  print(f"watch profile draft: {'yes' if draft_service.exists() else 'no'}")
  print(f"next cycle search plan: {'yes' if next_cycle_plan.exists() else 'no'}")
  print(f"next cycle tavily runner: {'yes' if next_cycle_runner.exists() else 'no'}")

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
