"""v8 Cloud Run Readiness service (Phase 27N) — prepare only, no deploy."""

from __future__ import annotations

import importlib.util
import json
import uuid
from pathlib import Path

from tech_cartography.runtime.live_artifact_paths import LIVE_OUTPUTS_ROOT_ENV
from tech_cartography.runtime.v8_cloud_run_readiness_schema import (
  CLOUD_RUN_SAFETY_NOTICES,
  V8CloudRunArtifactPolicy,
  V8CloudRunCheckResult,
  V8CloudRunEnvVarSpec,
  V8CloudRunReadinessReport,
)
from tech_cartography.runtime.v8_sources_schema import utc_now_iso

RECOMMENDED_STREAMLIT_CMD = (
  "streamlit run app.py --server.port=${PORT:-8080} --server.address=0.0.0.0 "
  "--server.headless=true --server.fileWatcherType=none --browser.gatherUsageStats=false"
)

REQUIRED_PACKAGES: tuple[str, ...] = (
  "streamlit",
  "openpyxl",
  "PyYAML",
)

RECOMMENDED_PACKAGES: tuple[str, ...] = (
  "pandas",
  "bcrypt",
)


def _check(
  check_id: str,
  check_name: str,
  *,
  status: str,
  summary: str,
  details: str = "",
  required_before_deploy: bool = True,
  next_fix_hint: str = "",
  artifact_paths: list[str] | None = None,
) -> V8CloudRunCheckResult:
  return V8CloudRunCheckResult(
    check_id=check_id,
    check_name=check_name,
    status=status,
    summary=summary,
    details=details,
    required_before_deploy=required_before_deploy,
    next_fix_hint=next_fix_hint,
    artifact_paths=artifact_paths or [],
  )


def _read_text(path: Path) -> str:
  if not path.is_file():
    return ""
  return path.read_text(encoding="utf-8")


def _build_env_var_specs() -> list[V8CloudRunEnvVarSpec]:
  return [
    V8CloudRunEnvVarSpec(
      name="APP_UI_VERSION",
      required=False,
      default_value_description="未設定時 v8",
      example_value="v8",
      purpose="v8 user-flow UI を起動（v7 fallback あり）",
      used_in_files=["app.py"],
    ),
    V8CloudRunEnvVarSpec(
      name="PORT",
      required=True,
      default_value_description="Cloud Run が注入（固定値を docs に書かない）",
      example_value="(Cloud Run injected)",
      purpose="Streamlit server port",
      used_in_files=["Procfile", "Dockerfile"],
      warning="ローカルは 8501/8502 でも可。Cloud Run では PORT 必須。",
    ),
    V8CloudRunEnvVarSpec(
      name=LIVE_OUTPUTS_ROOT_ENV,
      required=False,
      default_value_description="未設定時 project outputs/",
      example_value="/tmp/tech_cartography_outputs",
      purpose="artifact 出力ルート（Cloud Run 一時 FS 向け）",
      used_in_files=["src/tech_cartography/runtime/live_artifact_paths.py"],
      warning="Phase27O 以降で Cloud Storage 永続化を検討。",
    ),
    V8CloudRunEnvVarSpec(
      name="OUTPUT_ROOT",
      required=False,
      default_value_description="(未実装 — LIVE_OUTPUTS_ROOT を使用)",
      example_value="",
      purpose="将来の統一出力ルート（Phase27O 以降）",
      warning="現行コードは LIVE_OUTPUTS_ROOT を参照。Phase27O 以降で整理。",
    ),
    V8CloudRunEnvVarSpec(
      name="DISABLE_EMAIL_SEND",
      required=False,
      default_value_description="Cloud Run では true 推奨",
      example_value="true",
      purpose="SMTP 送信を無効化（機能は保持）",
      used_in_files=["app.py", "src/tech_cartography/ui/v8_admin_settings_ui.py"],
    ),
    V8CloudRunEnvVarSpec(
      name="DISABLE_SCHEDULER",
      required=False,
      default_value_description="Cloud Run では true 推奨",
      example_value="true",
      purpose="Scheduler 起動を無効化（機能は保持）",
      used_in_files=["app.py"],
    ),
    V8CloudRunEnvVarSpec(
      name="ENABLE_EMAIL_SEND",
      required=False,
      default_value_description="false（DISABLE_EMAIL_SEND=true と同等方針）",
      example_value="false",
      purpose="メール送信デフォルト OFF の明示（参考）",
      warning="実装は DISABLE_EMAIL_SEND を優先。Cloud Run では OFF。",
    ),
    V8CloudRunEnvVarSpec(
      name="ENABLE_SCHEDULER",
      required=False,
      default_value_description="false",
      example_value="false",
      purpose="Scheduler デフォルト OFF の明示（参考）",
      warning="実装は DISABLE_SCHEDULER を優先。Cloud Run では OFF。",
    ),
    V8CloudRunEnvVarSpec(
      name="SMTP_PASSWORD",
      required=False,
      secret_value_allowed=True,
      should_use_secret_manager=True,
      default_value_description="Secret Manager から注入",
      example_value="(Secret Manager — 値を docs に書かない)",
      purpose="SMTP 認証",
      warning="export / docs / UI に secret 値を含めない。",
    ),
    V8CloudRunEnvVarSpec(
      name="TAVILY_API_KEY",
      required=False,
      secret_value_allowed=True,
      should_use_secret_manager=True,
      default_value_description="Secret Manager から注入",
      example_value="(Secret Manager — 値を docs に書かない)",
      purpose="Web 検索 API（デフォルト OFF 運用）",
      warning="Cloud Run demo では DISABLE_EXTERNAL_API=true 推奨。",
    ),
  ]


def _build_artifact_policy() -> V8CloudRunArtifactPolicy:
  return V8CloudRunArtifactPolicy(
    local_output_root="outputs/local_*",
    cloud_output_root="/tmp/tech_cartography_outputs",
    ephemeral_filesystem_notice=(
      "Cloud Run コンテナのファイルシステムは ephemeral です。"
      " 生成 Pack はダウンロード前提。永続化は Phase27O 以降 Cloud Storage を検討。"
    ),
    persistent_storage_required=False,
    recommended_storage_option="cloud_storage_later",
    affected_features=[
      "v8 export packs",
      "demo readiness",
      "cloud run readiness",
      "large candidate shortlists",
      "claim map / evidence map / gap exports",
    ],
    warning="LIVE_OUTPUTS_ROOT=/tmp/tech_cartography_outputs を Cloud Run 起動時に設定推奨。",
  )


def _check_app_entrypoint(project_root: Path) -> tuple[V8CloudRunCheckResult, str]:
  app_path = project_root / "app.py"
  if not app_path.is_file():
    return (
      _check(
        "app_entrypoint",
        "App entrypoint",
        status="fail",
        summary="app.py が見つかりません",
        next_fix_hint="プロジェクトルートに app.py を配置",
      ),
      "fail",
    )
  text = _read_text(app_path)
  issues: list[str] = []
  if "DEFAULT_UI_VERSION" not in text or '"v8"' not in text:
    issues.append("DEFAULT_UI_VERSION=v8 が不明")
  if "v8_user_flow_app" not in text:
    issues.append("v8_user_flow_app wiring なし")
  if "APP_UI_VERSION" not in text:
    issues.append("APP_UI_VERSION switch なし")

  import_ok = False
  try:
    spec = importlib.util.spec_from_file_location("app_entry_probe", app_path)
    if spec and spec.loader:
      import_ok = True
  except Exception as exc:
    issues.append(f"import probe: {exc}")

  if issues:
    return (
      _check(
        "app_entrypoint",
        "App entrypoint",
        status="warning" if import_ok else "fail",
        summary="app.py は存在するが v8 default に問題の可能性",
        details="; ".join(issues),
        artifact_paths=[str(app_path.relative_to(project_root))],
        next_fix_hint="app.py で APP_UI_VERSION 未設定時 v8 を default に",
      ),
      "warning" if import_ok else "fail",
    )

  v8_import_ok = False
  try:
    from tech_cartography.ui import v8_user_flow_app  # noqa: F401

    v8_import_ok = True
  except Exception as exc:
    return (
      _check(
        "app_entrypoint",
        "App entrypoint",
        status="fail",
        summary="v8_user_flow_app import 失敗",
        details=str(exc),
        artifact_paths=[str(app_path.relative_to(project_root))],
      ),
      "fail",
    )

  return (
    _check(
      "app_entrypoint",
      "App entrypoint",
      status="pass",
      summary="app.py 存在 — APP_UI_VERSION default v8 / v8_user_flow_app import OK",
      artifact_paths=[str(app_path.relative_to(project_root))],
      details=f"v8_user_flow_app import: {v8_import_ok}",
    ),
    "pass",
  )


def _check_streamlit_command(project_root: Path) -> tuple[V8CloudRunCheckResult, str]:
  paths_checked: list[str] = []
  port_ok = False
  for rel in ("Procfile", "Dockerfile"):
    path = project_root / rel
    if path.is_file():
      paths_checked.append(rel)
      text = _read_text(path)
      if "${PORT" in text or "$PORT" in text:
        port_ok = True
      if "streamlit run app.py" in text and "0.0.0.0" in text:
        pass

  docs_path = project_root / "docs" / "cloud_run_v8_prepare.md"
  if docs_path.is_file():
    paths_checked.append("docs/cloud_run_v8_prepare.md")
    doc_text = _read_text(docs_path)
    if "${PORT" in doc_text or "$PORT" in doc_text:
      port_ok = True

  if port_ok and paths_checked:
    return (
      _check(
        "streamlit_command",
        "Streamlit command",
        status="pass",
        summary=f"PORT-aware streamlit command — {', '.join(paths_checked)}",
        details=f"推奨: {RECOMMENDED_STREAMLIT_CMD}",
        artifact_paths=paths_checked,
      ),
      "pass",
    )
  if paths_checked:
    return (
      _check(
        "streamlit_command",
        "Streamlit command",
        status="warning",
        summary="起動設定はあるが PORT 参照を確認",
        details=f"推奨: {RECOMMENDED_STREAMLIT_CMD}",
        artifact_paths=paths_checked,
        next_fix_hint="Procfile/Dockerfile/docs に ${PORT:-8080} を追加",
      ),
      "warning",
    )
  return (
    _check(
      "streamlit_command",
      "Streamlit command",
      status="warning",
      summary="Procfile/Dockerfile なし — docs に推奨コマンドを記載",
      details=f"推奨: {RECOMMENDED_STREAMLIT_CMD}",
      next_fix_hint="docs/cloud_run_v8_prepare.md と Dockerfile を確認",
    ),
    "warning",
  )


def _check_port_env(project_root: Path) -> tuple[V8CloudRunCheckResult, str]:
  hardcoded_only = False
  for rel in ("Procfile", "Dockerfile", "app.py"):
    text = _read_text(project_root / rel)
    if "8501" in text and "${PORT" not in text and "$PORT" not in text:
      if rel != "app.py":
        hardcoded_only = True

  if hardcoded_only:
    return (
      _check(
        "port_env",
        "PORT environment",
        status="warning",
        summary="8501 固定の可能性 — Cloud Run では PORT 環境変数を使用",
        next_fix_hint="streamlit --server.port=${PORT:-8080} に変更",
      ),
      "warning",
    )
  return (
    _check(
      "port_env",
      "PORT environment",
      status="pass",
      summary="Cloud Run PORT 前提の起動コマンドを確認",
      details="ローカル 8501/8502 は可。Cloud Run は PORT 注入。",
    ),
    "pass",
  )


def _check_requirements(project_root: Path) -> tuple[V8CloudRunCheckResult, str]:
  req_path = project_root / "requirements.txt"
  if not req_path.is_file():
    return (
      _check(
        "requirements",
        "Requirements",
        status="warning",
        summary="requirements.txt なし",
        next_fix_hint="requirements.txt を追加",
      ),
      "warning",
    )
  text = _read_text(req_path).lower()
  missing = [pkg for pkg in REQUIRED_PACKAGES if pkg.lower() not in text]
  missing_rec = [pkg for pkg in RECOMMENDED_PACKAGES if pkg.lower() not in text]
  if missing:
    return (
      _check(
        "requirements",
        "Requirements",
        status="warning",
        summary=f"必須パッケージ不足: {', '.join(missing)}",
        artifact_paths=["requirements.txt"],
        next_fix_hint="requirements.txt に streamlit / openpyxl 等を追加",
      ),
      "warning",
    )
  detail = "必須パッケージ OK"
  if missing_rec:
    detail += f" — 推奨不足: {', '.join(missing_rec)}"
  return (
    _check(
      "requirements",
      "Requirements",
      status="pass" if not missing_rec else "warning",
      summary="requirements.txt 確認済み",
      details=detail,
      artifact_paths=["requirements.txt"],
    ),
    "pass" if not missing_rec else "warning",
  )


def _check_dockerfile(project_root: Path) -> tuple[V8CloudRunCheckResult, str]:
  dockerfile = project_root / "Dockerfile"
  dockerignore = project_root / ".dockerignore"
  paths: list[str] = []
  if dockerfile.is_file():
    paths.append("Dockerfile")
    text = _read_text(dockerfile)
    if "v7" in text.lower() and "v8" not in text.lower():
      return (
        _check(
          "dockerfile",
          "Dockerfile",
          status="warning",
          summary="Dockerfile が v7 向け文言のみの可能性",
          artifact_paths=paths,
          next_fix_hint="app.py v8 起動 / PORT 対応に更新",
        ),
        "warning",
      )
    if "streamlit run app.py" not in text:
      return (
        _check(
          "dockerfile",
          "Dockerfile",
          status="warning",
          summary="Dockerfile に streamlit run app.py がない",
          artifact_paths=paths,
        ),
        "warning",
      )
    return (
      _check(
        "dockerfile",
        "Dockerfile",
        status="pass",
        summary="Dockerfile 存在 — v8 app.py 起動想定",
        artifact_paths=paths,
        details="docker build はこの Phase では実行しません。",
      ),
      "pass",
    )
  if dockerignore.is_file():
    paths.append(".dockerignore")
  return (
    _check(
      "dockerfile",
      "Dockerfile",
      status="warning",
      summary="Dockerfile なし — docs/cloud_run_v8_prepare.md に推奨案",
      artifact_paths=paths,
      next_fix_hint="Phase27N で最小 Dockerfile を追加（build は Phase27O）",
    ),
    "warning",
  )


def _check_dockerignore(project_root: Path) -> V8CloudRunCheckResult:
  path = project_root / ".dockerignore"
  if not path.is_file():
    return _check(
      "dockerignore",
      ".dockerignore",
      status="warning",
      summary=".dockerignore なし",
      next_fix_hint=".env / outputs / .git を除外する .dockerignore を追加",
    )
  text = _read_text(path)
  issues: list[str] = []
  for token in (".env", "outputs"):
    if token not in text:
      issues.append(f"{token} 除外なし")
  if issues:
    return _check(
      "dockerignore",
      ".dockerignore",
      status="warning",
      summary=".dockerignore に不足",
      details="; ".join(issues),
      artifact_paths=[".dockerignore"],
    )
  return _check(
    "dockerignore",
    ".dockerignore",
    status="pass",
    summary=".env / outputs 等を除外",
    artifact_paths=[".dockerignore"],
    required_before_deploy=False,
  )


def _check_output_policy(project_root: Path) -> tuple[V8CloudRunCheckResult, str, V8CloudRunArtifactPolicy]:
  policy = _build_artifact_policy()
  live_env_doc = LIVE_OUTPUTS_ROOT_ENV in _read_text(project_root / "docs" / "cloud_run_v8_prepare.md")
  return (
    _check(
      "output_artifact_policy",
      "Output artifact policy",
      status="pass" if live_env_doc else "warning",
      summary="local outputs/local_* vs Cloud Run /tmp — ephemeral FS 注意",
      details=policy.ephemeral_filesystem_notice,
      next_fix_hint="" if live_env_doc else "docs/cloud_run_v8_prepare.md に OUTPUT 方針を追記",
    ),
    "pass" if live_env_doc else "warning",
    policy,
  )


def _check_secret_policy(project_root: Path) -> tuple[V8CloudRunCheckResult, str]:
  gitignore = _read_text(project_root / ".gitignore")
  dockerignore = _read_text(project_root / ".dockerignore")
  ok = ".env" in gitignore or ".env" in dockerignore
  return (
    _check(
      "secret_policy",
      "Secret policy",
      status="pass" if ok else "warning",
      summary="Secret 値は export/docs/UI に含めない — Secret Manager 前提",
      details=".env は git/docker から除外。placeholder のみ docs。",
      next_fix_hint="" if ok else ".gitignore / .dockerignore に .env を追加",
    ),
    "pass" if ok else "warning",
  )


def _check_demo_data(project_root: Path) -> tuple[V8CloudRunCheckResult, str, list[str], list[str]]:
  demo_checklist = [
    "少なくとも1ケースで実データ CSV（source_candidates_large.csv）を投入",
    "Top100 / Top20 / Top5 を生成",
    "claim 本文を1件手動投入（望ましい — デモ見栄え向上）",
    "Evidence Map / Gap / Demo Polish Pack / Demo Readiness Pack を生成",
    "Export タブから提出用 Pack をダウンロード確認",
  ]
  warnings: list[str] = []
  demo_status = "unknown"
  try:
    from tech_cartography.services.v8_demo_readiness import build_demo_readiness_report

    dr = build_demo_readiness_report(project_root=project_root)
    demo_status = dr.overall_status
    if dr.overall_status == "not_ready":
      warnings.append(
        "Demo Readiness not_ready — Large Candidate CSV 未投入等。"
        " Cloud deploy 技術ブロッカーではないが、提出デモのブロッカー。"
      )
    elif dr.overall_status in {"needs_large_candidate_csv", "needs_shortlist", "needs_claim_text"}:
      warnings.append(f"Demo Readiness: {dr.overall_status} — 提出前に1ケース分を完成させる")
  except Exception as exc:
    warnings.append(f"Demo Readiness 参照失敗: {exc}")
    demo_status = "unknown"

  status = "warning" if warnings else "pass"
  return (
    _check(
      "demo_data",
      "Demo data readiness",
      status=status,
      summary=f"demo_data_status={demo_status} — not_ready は deploy 技術ブロッカーではない",
      details="; ".join(warnings) if warnings else "Demo Readiness 参照 OK",
      required_before_deploy=False,
      next_fix_hint="1ケース分: CSV投入 → Top5 → Demo Pack 生成",
    ),
    demo_status,
    demo_checklist,
    warnings,
  )


def _check_email_scheduler() -> tuple[V8CloudRunCheckResult, str]:
  return (
    _check(
      "email_scheduler",
      "Email / Scheduler policy",
      status="pass",
      summary="メール送信 / Scheduler は保持 — Cloud Run では DISABLE_*=true 推奨",
      details="no_email_send=true / no_scheduler_start=true — この Phase では実行しない",
      required_before_deploy=False,
    ),
    "pass",
  )


def _build_deploy_checklist() -> list[str]:
  return [
    "Cloud Run Readiness Pack を生成して overall_status を確認",
    "app.py — APP_UI_VERSION 未設定時 v8 default",
    "Procfile / Dockerfile — PORT-aware streamlit command",
    "requirements.txt — streamlit / openpyxl 等",
    ".dockerignore — .env / outputs 除外",
    "LIVE_OUTPUTS_ROOT=/tmp/tech_cartography_outputs を Cloud Run env に設定",
    "DISABLE_EMAIL_SEND=true / DISABLE_SCHEDULER=true",
    "Secret Manager に SMTP / API keys を配置（値を docs に書かない）",
    "Demo data — 1ケース分の CSV + Top5 + Pack 生成",
    "Phase27O で gcloud builds submit / gcloud run deploy を実行",
  ]


def _build_operator_checklist() -> list[str]:
  return [
    "Export タブで Cloud Run Readiness Pack を生成",
    "deploy_preparation_checklist.md を確認",
    "demo_data_checklist.md — 提出デモ不足を解消",
    "env_var_template.md — Secret 値を手動で docs に書かない",
    "Cloud Build / Cloud Run deploy は Phase27O まで実行しない",
    "artifact_policy.md — ephemeral FS / Cloud Storage 将来方針を確認",
  ]


def build_cloud_run_readiness_report(
  project_root: Path | str | None = None,
) -> V8CloudRunReadinessReport:
  """Assess Cloud Run deploy preparation — no build/deploy/gcloud."""
  root = Path(project_root).resolve() if project_root else Path.cwd().resolve()
  checks: list[V8CloudRunCheckResult] = []
  warnings: list[str] = []
  known_blockers: list[str] = []

  status_map: dict[str, str] = {}

  for fn in (
    lambda: _check_app_entrypoint(root),
    lambda: _check_streamlit_command(root),
    lambda: _check_port_env(root),
    lambda: _check_requirements(root),
    lambda: _check_dockerfile(root),
  ):
    result, st = fn()
    checks.append(result)
    status_map[result.check_id] = st
    if st == "fail" and result.required_before_deploy:
      known_blockers.append(f"{result.check_name}: {result.summary}")

  checks.append(_check_dockerignore(root))

  out_check, out_st, artifact_policy = _check_output_policy(root)
  checks.append(out_check)
  status_map["output_artifact_policy"] = out_st

  sec_check, sec_st = _check_secret_policy(root)
  checks.append(sec_check)
  status_map["secret_policy"] = sec_st

  demo_check, demo_status, demo_checklist, demo_warnings = _check_demo_data(root)
  checks.append(demo_check)
  status_map["demo_data"] = demo_check.status
  warnings.extend(demo_warnings)

  email_check, email_st = _check_email_scheduler()
  checks.append(email_check)
  status_map["email_scheduler"] = email_st

  checks.append(
    _check(
      "cloud_build",
      "Cloud Build",
      status="skipped",
      summary="この Phase では Cloud Build を実行していない",
      required_before_deploy=False,
    )
  )
  checks.append(
    _check(
      "cloud_run_deploy",
      "Cloud Run deploy",
      status="skipped",
      summary="この Phase では Cloud Run deploy を実行していない",
      required_before_deploy=False,
    )
  )

  fail_count = sum(1 for c in checks if c.status == "fail" and c.required_before_deploy)
  warn_count = sum(1 for c in checks if c.status == "warning")

  if fail_count:
    overall = "blocked"
  elif warn_count or demo_warnings:
    overall = "ready_with_warnings"
  else:
    overall = "ready_for_prepare"

  return V8CloudRunReadinessReport(
    report_id=f"cloud_run_readiness_{uuid.uuid4().hex[:12]}",
    generated_at=utc_now_iso(),
    overall_status=overall,
    app_entrypoint_status=status_map.get("app_entrypoint", "unknown"),
    streamlit_command_status=status_map.get("streamlit_command", "unknown"),
    port_env_status=status_map.get("port_env", "unknown"),
    requirements_status=status_map.get("requirements", "unknown"),
    dockerfile_status=status_map.get("dockerfile", "unknown"),
    output_artifact_policy_status=status_map.get("output_artifact_policy", "unknown"),
    secret_policy_status=status_map.get("secret_policy", "unknown"),
    demo_data_status=demo_status,
    email_scheduler_status=status_map.get("email_scheduler", "unknown"),
    cloud_build_status="not_executed",
    cloud_run_deploy_status="not_executed",
    check_results=checks,
    env_var_specs=_build_env_var_specs(),
    artifact_policy=artifact_policy,
    deploy_preparation_checklist=_build_deploy_checklist(),
    demo_data_checklist=demo_checklist,
    operator_checklist=_build_operator_checklist(),
    known_blockers=known_blockers,
    warnings=warnings,
    no_cloud_build_executed=True,
    no_cloud_run_deploy_executed=True,
    no_email_send=True,
    no_scheduler_start=True,
    no_secret_exposed=True,
    no_legal_judgement=True,
  )
