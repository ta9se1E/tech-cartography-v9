#!/usr/bin/env python3
"""Pre-deploy checks for Cloud Run live beta (Phase 25C–25K)."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from tech_cartography.runtime.auth_provider_config import (
  get_admin_emails,
  get_allowed_email_domains,
  get_auth_provider_mode,
)
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
from tech_cartography.runtime.approved_member_send_config import (  # noqa: E402
  ENABLE_APPROVED_MEMBER_SEND_ENV,
  can_send_approved_member_email,
  is_approved_member_send_enabled,
)
from tech_cartography.services.live_digest_preview import can_create_live_digest_preview  # noqa: E402
from tech_cartography.runtime.external_api_guard import check_live_tavily_smoke_allowed  # noqa: E402
from tech_cartography.runtime.live_artifact_paths import (  # noqa: E402
  describe_live_artifact_storage,
  ensure_live_artifact_dirs,
  get_live_outputs_root,
  using_live_outputs_root_env,
)
from tech_cartography.runtime.watch_profile_management_config import is_watch_profile_management_enabled
from tech_cartography.runtime.external_api_operation_config import (
  get_web_signal_max_queries,
  get_web_signal_max_results_per_query,
  is_manual_web_signal_collection_enabled,
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
  approved_member_cfg = PROJECT_ROOT / "src/tech_cartography/runtime/approved_member_send_config.py"
  approved_member_sender = PROJECT_ROOT / "src/tech_cartography/services/live_approved_member_email_sender.py"
  approved_member_ui = PROJECT_ROOT / "src/tech_cartography/ui/live_approved_member_email_send_ui.py"
  approved_member_docs = PROJECT_ROOT / "docs/phase25q_approved_member_send.md"
  email_operation_status = PROJECT_ROOT / "src/tech_cartography/runtime/email_operation_status.py"
  email_operation_status_ui = PROJECT_ROOT / "src/tech_cartography/ui/email_operation_status_ui.py"
  send_safety_docs = PROJECT_ROOT / "docs/phase25q2_send_safety_reset.md"
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
  operation_status = PROJECT_ROOT / "src/tech_cartography/services/live_operation_status.py"
  operation_console_ui = PROJECT_ROOT / "src/tech_cartography/ui/live_operation_console_ui.py"
  operation_docs = PROJECT_ROOT / "docs/phase25k_manual_weekly_operation_console.md"
  release_pack_service = PROJECT_ROOT / "src/tech_cartography/services/live_beta_release_pack.py"
  release_pack_ui = PROJECT_ROOT / "src/tech_cartography/ui/live_beta_release_pack_ui.py"
  release_pack_docs = PROJECT_ROOT / "docs/phase25l_live_beta_release_pack.md"
  user_context_module = PROJECT_ROOT / "src/tech_cartography/runtime/user_context.py"
  run_history_service = PROJECT_ROOT / "src/tech_cartography/services/live_run_history.py"
  run_history_ui = PROJECT_ROOT / "src/tech_cartography/ui/live_run_history_ui.py"
  run_history_docs = PROJECT_ROOT / "docs/phase25m_user_run_context_and_execution_history.md"
  password_hash_script = PROJECT_ROOT / "scripts/generate_login_password_hash.py"
  auth_provider_config = PROJECT_ROOT / "src/tech_cartography/runtime/auth_provider_config.py"
  iap_identity = PROJECT_ROOT / "src/tech_cartography/runtime/iap_identity.py"
  iap_role_mapping = PROJECT_ROOT / "src/tech_cartography/runtime/iap_role_mapping.py"
  auth_status_ui = PROJECT_ROOT / "src/tech_cartography/ui/auth_status_ui.py"
  auth_bridge_docs = PROJECT_ROOT / "docs/phase25n_google_iap_ready_auth_bridge.md"
  iap_cutover_docs = PROJECT_ROOT / "docs/phase25o_cloud_run_iap_cutover_runbook.md"
  iap_cutover_script = PROJECT_ROOT / "scripts/check_iap_cutover_ready.py"
  iap_cutover_status_ui = PROJECT_ROOT / "src/tech_cartography/ui/iap_cutover_status_ui.py"
  cloudbuild_yaml = PROJECT_ROOT / "cloudbuild.yaml"
  deploy_live_script = PROJECT_ROOT / "scripts/deploy_live_safe.sh"
  rollback_live_script = PROJECT_ROOT / "scripts/rollback_live_to_basic.sh"
  cicd_docs = PROJECT_ROOT / "docs/phase25p_cicd_cloud_build_deploy.md"
  cicd_ready_script = PROJECT_ROOT / "scripts/check_cicd_ready.py"
  watch_profile_schema = PROJECT_ROOT / "src/tech_cartography/runtime/watch_profile_schema.py"
  watch_profile_mgmt_cfg = PROJECT_ROOT / "src/tech_cartography/runtime/watch_profile_management_config.py"
  watch_profile_manager = PROJECT_ROOT / "src/tech_cartography/services/live_watch_profile_manager.py"
  watch_profile_ui = PROJECT_ROOT / "src/tech_cartography/ui/live_watch_profile_ui.py"
  scheduler_dry_run_service = PROJECT_ROOT / "src/tech_cartography/services/live_scheduler_dry_run.py"
  scheduler_dry_run_ui = PROJECT_ROOT / "src/tech_cartography/ui/live_scheduler_dry_run_ui.py"
  watch_profile_docs = PROJECT_ROOT / "docs/phase25s_watch_profile_management.md"
  external_api_op_cfg = PROJECT_ROOT / "src/tech_cartography/runtime/external_api_operation_config.py"
  web_signal_collector = PROJECT_ROOT / "src/tech_cartography/services/live_web_signal_collector.py"
  web_signal_collection_ui = PROJECT_ROOT / "src/tech_cartography/ui/live_web_signal_collection_ui.py"
  web_signal_collection_docs = PROJECT_ROOT / "docs/phase25t_controlled_web_signal_collection.md"

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
    approved_member_cfg,
    approved_member_sender,
    approved_member_ui,
    approved_member_docs,
    email_operation_status,
    email_operation_status_ui,
    send_safety_docs,
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
    operation_status,
    operation_console_ui,
    operation_docs,
    release_pack_service,
    release_pack_ui,
    release_pack_docs,
    user_context_module,
    run_history_service,
    run_history_ui,
    run_history_docs,
    password_hash_script,
    auth_provider_config,
    iap_identity,
    iap_role_mapping,
    auth_status_ui,
    auth_bridge_docs,
    iap_cutover_docs,
    iap_cutover_script,
    iap_cutover_status_ui,
    cloudbuild_yaml,
    deploy_live_script,
    rollback_live_script,
    cicd_docs,
    cicd_ready_script,
    watch_profile_schema,
    watch_profile_mgmt_cfg,
    watch_profile_manager,
    watch_profile_ui,
    scheduler_dry_run_service,
    scheduler_dry_run_ui,
    watch_profile_docs,
    external_api_op_cfg,
    web_signal_collector,
    web_signal_collection_ui,
    web_signal_collection_docs,
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
  if "render_live_approved_member_email_send_section" not in analyst_ui:
    failures.append("theme_validation_ui に approved member email send UI がありません")
  approved_member_ui_text = _read(approved_member_ui)
  if "承認済みメンバーへDigestを送信" not in approved_member_ui_text:
    failures.append("live_approved_member_email_send_ui に送信ボタンがありません")
  if "SEND TO APPROVED MEMBER" not in approved_member_ui_text and "get_confirmation_text" not in approved_member_ui_text:
    failures.append("live_approved_member_email_send_ui に確認テキスト要件がありません")
  if "st.text_input" in approved_member_ui_text and "st.selectbox" not in approved_member_ui_text:
    failures.append("live_approved_member_email_send_ui が selectbox を使っていません")
  if "SMTP_PASSWORD" in approved_member_ui_text and "os.environ" in approved_member_ui_text:
    failures.append("live_approved_member_email_send_ui が SMTP_PASSWORD env を参照しています")
  if "render_live_approved_member_email_send_section" not in digest_ui_text:
    failures.append("live_digest_preview_ui に approved member email send UI がありません")
  if digest_ui_text.index("render_live_approved_member_email_send_section") > digest_ui_text.index(
    "render_live_email_send_section",
  ):
    failures.append("live_digest_preview_ui で approved member send が self-only より後です")
  if "send_live_digest_email_self_only" in approved_member_ui_text:
    failures.append("live_approved_member_email_send_ui が self_only sender を呼んでいます")
  if "send_live_digest_email_to_approved_member" not in approved_member_ui_text:
    failures.append("live_approved_member_email_send_ui が approved member sender を呼んでいません")
  if "is_app_authenticated" not in approved_member_ui_text:
    failures.append("live_approved_member_email_send_ui が is_app_authenticated を使っていません")
  if "evaluate_live_admin_access" not in _read(approved_member_sender):
    failures.append("live_approved_member_email_sender が evaluate_live_admin_access を使っていません")
  if "evaluate_live_admin_access" not in _read(email_sender):
    failures.append("live_email_sender が evaluate_live_admin_access を使っていません")
  if "evaluate_live_admin_access" not in _read(user_context_module):
    failures.append("user_context が evaluate_live_admin_access を提供していません")
  if "get_email_operation_status" not in _read(email_operation_status):
    failures.append("email_operation_status が get_email_operation_status を提供していません")
  if "reset_required" not in _read(approved_member_sender):
    failures.append("live_approved_member_email_sender に post-send reset guidance がありません")
  if "operation_metadata" not in _read(run_history_service):
    failures.append("live_run_history に operation_metadata サポートがありません")
  if "render_email_operation_status_panel" not in _read(email_operation_status_ui):
    failures.append("email_operation_status_ui に status panel がありません")
  if "SMTP_PASSWORD" in _read(email_operation_status_ui) and "configured" not in _read(email_operation_status_ui):
    failures.append("email_operation_status_ui が SMTP_PASSWORD を露出しています")
  send_safety_docs_text = _read(send_safety_docs)
  if "controlled_manual_send_enabled" not in send_safety_docs_text:
    failures.append("phase25q2 docs に safety level 説明がありません")
  if "reset_required" not in send_safety_docs_text:
    failures.append("phase25q2 docs に reset_required 説明がありません")
  if "DISABLE_EMAIL_SEND=true" not in send_safety_docs_text:
    failures.append("phase25q2 docs に DISABLE_EMAIL_SEND=true 復帰手順がありません")
  email_ops_text = _read(email_operation_status)
  if "SMTP_PASSWORD" in email_ops_text and "smtp_password_configured" not in email_ops_text:
    failures.append("email_operation_status が SMTP_PASSWORD 実値を扱っている可能性があります")
  if "build_post_send_reset_command" not in email_ops_text:
    failures.append("email_operation_status に reset command builder がありません")
  if "secret" in email_ops_text.lower() and "no secrets" not in email_ops_text.lower():
    failures.append("email_operation_status の reset command に secret が含まれる可能性があります")
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
  operation_console_text = _read(operation_console_ui)
  if "render_live_operation_console_section" not in analyst_ui:
    failures.append("theme_validation_ui に live operation console UI がありません")
  if "Live Operation Console（手動週次運用）" not in operation_console_text:
    failures.append("live_operation_console_ui にコンソールタイトルがありません")
  if "build_operation_cycle_status" not in _read(operation_status):
    failures.append("live_operation_status が build_operation_cycle_status を提供していません")
  if "get_live_operation_status_dir" not in _read(artifact_paths):
    failures.append("live_artifact_paths に get_live_operation_status_dir がありません")
  if "get_live_release_pack_dir" not in _read(artifact_paths):
    failures.append("live_artifact_paths に get_live_release_pack_dir がありません")
  release_pack_ui_text = _read(release_pack_ui)
  if "render_live_beta_release_pack_section" not in market_ui:
    failures.append("v7_easy_app reports タブに live beta release pack UI がありません")
  if "render_live_beta_release_pack_section" not in settings_ui:
    failures.append("user_settings_view に live beta release pack UI がありません")
  if "Live Beta Release Pack（共有用）" not in release_pack_ui_text:
    failures.append("live_beta_release_pack_ui に共有パックタイトルがありません")
  if "共有パックを作成" not in release_pack_ui_text:
    failures.append("live_beta_release_pack_ui に作成ボタンがありません")
  if "build_live_beta_release_pack" not in _read(release_pack_service):
    failures.append("live_beta_release_pack が build_live_beta_release_pack を提供していません")
  if "live_artifact_paths" not in _read(release_pack_service):
    failures.append("live_beta_release_pack が live_artifact_paths を使っていません")
  if "find_latest_operation_status_path" not in _read(operation_status):
    failures.append("live_operation_status が find_latest_operation_status_path を提供していません")
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

    saved_approved_send = os.environ.get(ENABLE_APPROVED_MEMBER_SEND_ENV)
    os.environ[ENABLE_APPROVED_MEMBER_SEND_ENV] = "false"
    if is_approved_member_send_enabled():
      failures.append("ENABLE_APPROVED_MEMBER_SEND=false が有効になりません")
    allowed_approved, approved_reason = can_send_approved_member_email("approved@example.com")
    if allowed_approved:
      failures.append("ENABLE_APPROVED_MEMBER_SEND=false でも approved member send が許可されています")
    if approved_reason != "approved_member_send_disabled":
      failures.append(f"approved member send block reason が不正: {approved_reason}")

    os.environ[ENABLE_APPROVED_MEMBER_SEND_ENV] = "true"
    os.environ["TECH_CARTOGRAPHY_APPROVED_MEMBER_EMAILS"] = "approved@example.com"
    os.environ[DISABLE_EMAIL_SEND_ENV] = "true"
    allowed_disabled_email, disabled_reason = can_send_approved_member_email("approved@example.com")
    if allowed_disabled_email:
      failures.append("DISABLE_EMAIL_SEND=true でも approved member send が許可されています")
    if disabled_reason != "disabled_by_env":
      failures.append(f"approved member DISABLE_EMAIL_SEND block reason が不正: {disabled_reason}")

    if saved_approved_send is None:
      os.environ.pop(ENABLE_APPROVED_MEMBER_SEND_ENV, None)
    else:
      os.environ[ENABLE_APPROVED_MEMBER_SEND_ENV] = saved_approved_send
    os.environ.pop("TECH_CARTOGRAPHY_APPROVED_MEMBER_EMAILS", None)

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
  if "live_release_packs" not in artifact_ui_text:
    failures.append("live_artifact_storage_ui に live_release_packs 件数がありません")
  if "get_live_run_history_dir" not in _read(artifact_paths):
    failures.append("live_artifact_paths に get_live_run_history_dir がありません")
  if "live_run_history_entries" not in artifact_ui_text:
    failures.append("live_artifact_storage_ui に live_run_history 件数がありません")
  if "render_run_history_section" not in market_ui:
    failures.append("v7_easy_app reports タブに run history UI がありません")
  if "render_run_history_section" not in settings_ui:
    failures.append("user_settings_view に run history UI がありません")
  if "record_live_run" not in _read(run_history_service):
    failures.append("live_run_history が record_live_run を提供していません")
  if "resolve_user_context" not in _read(user_context_module):
    failures.append("user_context が resolve_user_context を提供していません")
  basic_auth_path = PROJECT_ROOT / "src/tech_cartography/auth/basic_auth.py"
  if "hash_password_pbkdf2" not in _read(basic_auth_path):
    failures.append("basic_auth が pbkdf2 hash を提供していません")
  auth_status_text = _read(auth_status_ui)
  if "Authentication Status（管理者向け）" not in auth_status_text:
    failures.append("auth_status_ui に管理者向けタイトルがありません")
  if "render_auth_status_expander" not in settings_ui:
    failures.append("user_settings_view に auth status UI がありません")
  if "render_auth_status_expander" not in analyst_ui:
    failures.append("theme_validation_ui に auth status UI がありません")
  if "get_auth_provider_mode" not in _read(auth_provider_config):
    failures.append("auth_provider_config が get_auth_provider_mode を提供していません")
  if "resolve_iap_identity_from_headers" not in _read(iap_identity):
    failures.append("iap_identity が resolve_iap_identity_from_headers を提供していません")
  if "map_email_to_role" not in _read(iap_role_mapping):
    failures.append("iap_role_mapping が map_email_to_role を提供していません")
  if "require_auth_login_gate" not in _read(PROJECT_ROOT / "src/tech_cartography/ui/login_ui.py"):
    failures.append("login_ui が require_auth_login_gate を提供していません")
  if "AUTH_PROVIDER_MODE" not in env_example:
    failures.append(".env.example に AUTH_PROVIDER_MODE がありません")
  if "SMTP_PASSWORD" in auth_status_text or "TECH_CARTOGRAPHY_LOGIN_PASSWORD" in auth_status_text:
    failures.append("auth_status_ui が secret 名を露出しています")
  iap_cutover_ui_text = _read(iap_cutover_status_ui)
  if "IAP Cutover Status（管理者向け）" not in iap_cutover_ui_text:
    failures.append("iap_cutover_status_ui に管理者向けタイトルがありません")
  if "render_iap_cutover_status_expander" not in settings_ui:
    failures.append("user_settings_view に IAP cutover status UI がありません")
  if "SMTP_PASSWORD" in iap_cutover_ui_text or "TECH_CARTOGRAPHY_LOGIN_PASSWORD" in iap_cutover_ui_text:
    failures.append("iap_cutover_status_ui が secret 名を露出しています")
  cutover_script_text = _read(iap_cutover_script)
  if "never enables" not in cutover_script_text.lower():
    failures.append("check_iap_cutover_ready に read-only / never enables の宣言がありません")
  cloudbuild_text = _read(cloudbuild_yaml)
  deploy_script_text = _read(deploy_live_script)
  rollback_script_text = _read(rollback_live_script)
  if "pytest" not in cloudbuild_text:
    failures.append("cloudbuild.yaml が pytest を実行していません")
  if "gcloud run deploy" not in cloudbuild_text:
    failures.append("cloudbuild.yaml が Cloud Run deploy を含んでいません")
  if "--no-iap" in cloudbuild_text or re.search(r"gcloud\s+run\s+.*--no-iap", deploy_script_text):
    failures.append("CI/CD deploy が IAP を無効化する --no-iap を含んでいます")
  if "live_approved_member_email_send" not in _read(run_history_service):
    failures.append("live_run_history に live_approved_member_email_send action_type がありません")
  if "get_live_approved_member_send_dir" not in _read(artifact_paths):
    failures.append("live_artifact_paths に get_live_approved_member_send_dir がありません")
  if "live_artifact_paths" not in _read(approved_member_sender):
    failures.append("live_approved_member_email_sender が live_artifact_paths を使っていません")
  if "ENABLE_APPROVED_MEMBER_SEND=false" not in cloudbuild_text:
    failures.append("cloudbuild.yaml に ENABLE_APPROVED_MEMBER_SEND=false がありません")
  if "TECH_CARTOGRAPHY_APPROVED_MEMBER_EMAILS=" in cloudbuild_text:
    failures.append("cloudbuild.yaml に TECH_CARTOGRAPHY_APPROVED_MEMBER_EMAILS が直書きされています")
  approved_member_docs_text = _read(approved_member_docs)
  if "approved@example.com" not in approved_member_docs_text:
    failures.append("phase25q docs に approved@example.com 例がありません")
  if "一斉送信" not in approved_member_docs_text:
    failures.append("phase25q docs に一斉送信禁止の記載がありません")
  if "SMTP_PASSWORD=" in cloudbuild_text and "tech-cartography-smtp-password" not in cloudbuild_text:
    failures.append("cloudbuild.yaml が SMTP 値を直書きしている可能性があります")
  if "read -rs" not in rollback_script_text and "read -s" not in rollback_script_text:
    failures.append("rollback_live_to_basic.sh が read -s を使っていません")
  cicd_ready_text = _read(cicd_ready_script)
  if "CI/CD readiness" not in cicd_ready_text:
    failures.append("check_cicd_ready.py が CI/CD readiness を報告していません")
  auth_mode = os.environ.get("AUTH_PROVIDER_MODE", "").strip().lower() or get_auth_provider_mode()
  print(f"auth provider mode (local): {auth_mode}")
  if auth_mode in {"iap", "hybrid"}:
    if not get_admin_emails() and not get_allowed_email_domains():
      warnings.append(f"AUTH_PROVIDER_MODE={auth_mode} ですが ADMIN_EMAILS / ALLOWED_EMAIL_DOMAINS が未設定です")
  if os.environ.get("IAP_JWT_VERIFY_MODE", "").strip().lower() == "strict":
    if not os.environ.get("IAP_EXPECTED_AUDIENCE", "").strip():
      failures.append("IAP_JWT_VERIFY_MODE=strict ですが IAP_EXPECTED_AUDIENCE が未設定です")
  if "SMTP_PASSWORD" in artifact_ui_text or "API_KEY" in artifact_ui_text:
    failures.append("live_artifact_storage_ui が secret 名を露出しています")

  watch_profile_manager_text = _read(watch_profile_manager)
  watch_profile_paths_text = _read(artifact_paths)
  run_history_text = _read(run_history_service)
  if "live_watch_profiles/drafts" not in watch_profile_paths_text.replace('"', ""):
    if "LIVE_WATCH_PROFILES_DRAFTS_SUBDIR" not in watch_profile_paths_text:
      failures.append("live_artifact_paths に live_watch_profiles/drafts がありません")
  for sub in ("drafts", "active", "archive"):
    if f"LIVE_WATCH_PROFILES_{sub.upper()}_SUBDIR" not in watch_profile_paths_text and f"live_watch_profiles/{sub}" not in watch_profile_paths_text:
      failures.append(f"live_artifact_paths に live_watch_profiles/{sub} がありません")
  for action in (
    "live_watch_profile_draft_save",
    "live_watch_profile_activate",
    "live_watch_profile_archive",
    "live_watch_profile_rollback",
    "live_scheduler_dry_run",
    "live_web_signal_collection",
  ):
    if action not in run_history_text:
      failures.append(f"live_run_history に {action} がありません")
  if is_watch_profile_management_enabled():
    warnings.append("ENABLE_WATCH_PROFILE_MANAGEMENT=true — deploy デフォルトは false 推奨")
  for forbidden in ("requests.", "smtplib", "send_email", "scheduler.start", "cloudscheduler"):
    if forbidden in watch_profile_manager_text.lower():
      failures.append(f"live_watch_profile_manager が禁止操作 {forbidden} を含みます")
  for secret_token in ("SMTP_PASSWORD", "oauth", "jwt", "api_key"):
    if secret_token.lower() in watch_profile_manager_text.lower() and "sensitive" not in watch_profile_manager_text.lower():
      pass
  if re.search(r"SMTP_PASSWORD|jwt|oauth", watch_profile_manager_text, re.IGNORECASE):
    if "_SENSITIVE_PATTERN" not in watch_profile_manager_text:
      failures.append("live_watch_profile_manager に secret ガードがありません")
  if "ENABLE_WATCH_PROFILE_MANAGEMENT=false" not in _read(cloudbuild_yaml):
    failures.append("cloudbuild.yaml が ENABLE_WATCH_PROFILE_MANAGEMENT=false をデフォルトにしていません")
  if "ENABLE_WATCH_PROFILE_MANAGEMENT=false" not in _read(deploy_live_script):
    failures.append("deploy_live_safe.sh が ENABLE_WATCH_PROFILE_MANAGEMENT=false をデフォルトにしていません")
  if "phase25s" not in _read(watch_profile_docs).lower() and "Watch Profile" not in _read(watch_profile_docs):
    failures.append("phase25s docs に Watch Profile 説明がありません")

  collector_text = _read(web_signal_collector)
  digest_text = _read(digest_service)
  scheduler_text = _read(scheduler_dry_run_service)
  if "live_web_signal_collection" not in run_history_text:
    failures.append("live_run_history に live_web_signal_collection がありません")
  if "ENABLE_MANUAL_WEB_SIGNAL_COLLECTION=false" not in _read(cloudbuild_yaml):
    failures.append("cloudbuild.yaml が ENABLE_MANUAL_WEB_SIGNAL_COLLECTION=false をデフォルトにしていません")
  if "DISABLE_EXTERNAL_API=true" not in _read(cloudbuild_yaml):
    failures.append("cloudbuild.yaml が DISABLE_EXTERNAL_API=true を維持していません")
  if get_web_signal_max_queries() > 5:
    failures.append("WEB_SIGNAL_MAX_QUERIES が大きすぎます")
  if get_web_signal_max_results_per_query() > 10:
    failures.append("WEB_SIGNAL_MAX_RESULTS_PER_QUERY が大きすぎます")
  for forbidden in ("smtplib", "send_email", "cloudscheduler"):
    if forbidden in collector_text.lower():
      failures.append(f"live_web_signal_collector が禁止操作 {forbidden} を含みます")
  if "_default_post_tavily" in collector_text and "post_fn" not in collector_text:
    failures.append("live_web_signal_collector に post_fn 注入がありません")
  if "collect_live_web_signals" in scheduler_text:
    failures.append("live_scheduler_dry_run が web signal collector を呼んでいます")
  if "collect_live_web_signals" in digest_text:
    failures.append("live_digest_preview が web signal collector を自動呼び出ししています")
  if "fto_judgement" not in collector_text or "candidate_information_only" not in collector_text:
    failures.append("live_web_signal_collector に safety_flags がありません")
  if "phase25t" not in _read(web_signal_collection_docs).lower() and "Web Signal" not in _read(web_signal_collection_docs):
    failures.append("phase25t docs に Web Signal 説明がありません")
  if is_manual_web_signal_collection_enabled():
    warnings.append("ENABLE_MANUAL_WEB_SIGNAL_COLLECTION=true — deploy デフォルトは false 推奨")

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
  print(f"approved member send: {'yes' if approved_member_sender.exists() else 'no'}")
  print(f"email operation status: {'yes' if email_operation_status.exists() else 'no'}")
  print(f"live artifact paths: {'yes' if artifact_paths.exists() else 'no'}")
  print(f"live watch expansion: {'yes' if expansion_service.exists() else 'no'}")
  print(f"watch profile draft: {'yes' if draft_service.exists() else 'no'}")
  print(f"next cycle search plan: {'yes' if next_cycle_plan.exists() else 'no'}")
  print(f"next cycle tavily runner: {'yes' if next_cycle_runner.exists() else 'no'}")
  print(f"live operation console: {'yes' if operation_status.exists() else 'no'}")
  print(f"live beta release pack: {'yes' if release_pack_service.exists() else 'no'}")
  print(f"user run history: {'yes' if run_history_service.exists() else 'no'}")
  print(f"iap auth bridge: {'yes' if iap_identity.exists() else 'no'}")
  print(f"iap cutover runbook: {'yes' if iap_cutover_docs.exists() else 'no'}")
  print(f"cicd pipeline: {'yes' if cloudbuild_yaml.exists() else 'no'}")
  print(f"watch profile management: {'yes' if watch_profile_manager.exists() else 'no'}")
  print(f"scheduler dry-run: {'yes' if scheduler_dry_run_service.exists() else 'no'}")
  print(f"controlled web signal collection: {'yes' if web_signal_collector.exists() else 'no'}")

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
