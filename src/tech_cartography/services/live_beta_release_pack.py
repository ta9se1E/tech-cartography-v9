"""Live Beta Release Pack — stakeholder handoff bundle (Phase 25L)."""

from __future__ import annotations

import json
import os
import re
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tech_cartography.runtime.cloud_run_config import (
  is_email_send_disabled,
  is_external_api_disabled,
  is_scheduler_disabled,
)
from tech_cartography.runtime.live_artifact_paths import (
  LIVE_OUTPUTS_ROOT_ENV,
  check_directory_writable,
  describe_live_artifact_storage,
  get_live_outputs_root,
  get_live_release_pack_dir,
  using_live_outputs_root_env,
)
from tech_cartography.services.live_digest_preview import (
  find_latest_live_digest_preview_path,
  load_live_digest_preview,
)
from tech_cartography.services.live_next_cycle_search_plan import (
  find_latest_next_cycle_search_plan_path,
  load_next_cycle_search_plan,
)
from tech_cartography.services.live_run_history import (
  attach_user_run_metadata,
  generate_run_id,
  record_live_run,
)
from tech_cartography.services.live_operation_status import (
  STEP_GUIDANCE,
  STEP_ORDER,
  build_operation_cycle_status,
  find_latest_operation_status_path,
  load_latest_operation_status,
)
from tech_cartography.services.watch_profile_draft import resolve_watch_profile_draft_status

DEFAULT_SERVICE_NAME = "tech-cartography-v7-live"
DEFAULT_SERVICE_URL_PLACEHOLDER = "<Cloud Run service URL — share separately>"

_SENSITIVE_TEXT_PATTERN = re.compile(
  r"(api[_-]?key\s*[:=]|authorization\s*:\s*bearer|smtp[_-]?host\s*[:=]|smtp[_-]?user\s*[:=])",
  re.IGNORECASE,
)

_FORBIDDEN_CREDENTIAL_NAMES: tuple[str, ...] = (
  "TECH_CARTOGRAPHY_LOGIN_PASSWORD",
  "SMTP_PASSWORD",
  "OPENAI_API_KEY",
  "GEMINI_API_KEY",
  "TAVILY_API_KEY",
)

_MANUAL_WEEKLY_FLOW: tuple[str, ...] = (
  "Web Signal Pack を手動作成（Tavily 候補の収集）",
  "Digest Preview を手動作成（メール送信なし）",
  "Self-only Email Send Test（任意・自分宛て1通のみ）",
  "Watch Expansion Proposals を手動作成",
  "Watch Profile Draft を人間承認して保存",
  "Next Cycle Search Plan を手動作成",
  "Next Cycle Web Signal Pack を手動作成（選択 query のみ）",
  "Live Operation Console で状態を確認・保存",
)

_KNOWN_LIMITATIONS = (
  "Web Signal は確認候補であり、事実確定ではありません。",
  "Paper や Web 情報は裏取り候補であり、単独で判断根拠にしないでください。",
  "FTO、侵害、有効性判断は行いません。",
  "メール送信は self_only（自分宛てテスト）のみです。",
  "scheduler は OFF です。",
  "外部 API は通常 OFF 運用です（手動 smoke / pack 作成時のみ一時 ON 可）。",
  "現時点では手動運用です。自動週次実行はありません。",
  "本番導入前には認証強化、監査ログ、権限管理が必要です。",
  "共有先には限定公開として扱ってください。",
)

_ADMIN_CHECKLIST: tuple[str, ...] = (
  "Live Operation Console で最新状態を保存したか",
  "Web Signal Pack / Digest Preview が最新か",
  "Watch Profile Draft が人間承認済みか",
  "Next Cycle Search Plan / Pack の有無を確認したか",
  "外部 API・scheduler・一斉メールが OFF のままか",
  "共有パックに機密情報やログイン情報が含まれていないか",
  "関係者へは限定公開・研究開発補助である旨を伝えたか",
)


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _timestamp_slug(iso_ts: str) -> str:
  return iso_ts.replace(":", "").replace("-", "")


def _collect_runtime_flags() -> dict[str, Any]:
  return {
    "disable_external_api": is_external_api_disabled(),
    "disable_email_send": is_email_send_disabled(),
    "disable_scheduler": is_scheduler_disabled(),
    "live_outputs_root_env_set": using_live_outputs_root_env(),
  }


def _assert_no_sensitive_material(text: str) -> None:
  if _SENSITIVE_TEXT_PATTERN.search(text):
    raise ValueError("Refusing to save release pack containing sensitive material")


def _assert_no_forbidden_credential_names(text: str) -> None:
  for name in _FORBIDDEN_CREDENTIAL_NAMES:
    if name in text:
      raise ValueError(f"Refusing to save release pack containing credential name {name}")


def _assert_no_env_secret_leaks(text: str) -> None:
  for env_name in (
    "TECH_CARTOGRAPHY_LOGIN_PASSWORD",
    "SMTP_PASSWORD",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "TAVILY_API_KEY",
  ):
    value = str(os.environ.get(env_name, "") or "").strip()
    if value and value in text:
      raise ValueError(f"Refusing to save release pack leaking {env_name}")


def _validate_release_pack_output(text: str, *, strict_text: bool = True) -> None:
  if strict_text:
    _assert_no_sensitive_material(text)
  _assert_no_env_secret_leaks(text)
  _assert_no_forbidden_credential_names(text)


def _service_name() -> str:
  return str(os.environ.get("CLOUD_RUN_SERVICE_NAME", "") or DEFAULT_SERVICE_NAME).strip()


def _service_url_placeholder() -> str:
  url = str(os.environ.get("CLOUD_RUN_SERVICE_URL", "") or "").strip()
  if url:
    return url
  return DEFAULT_SERVICE_URL_PLACEHOLDER


def _summarize_digest_preview(project_root: Path | str | None) -> dict[str, Any]:
  latest_path = find_latest_live_digest_preview_path(project_root or Path.cwd())
  if latest_path is None:
    return {"status": "missing", "summary": "latest digest preview がありません。"}
  preview = load_live_digest_preview(latest_path)
  if not preview:
    return {"status": "invalid", "latest_path": str(latest_path), "summary": "読み込み失敗"}
  return {
    "status": "ok",
    "latest_path": str(latest_path),
    "created_at": preview.get("created_at"),
    "theme_name": preview.get("theme_name"),
    "candidate_count": len(preview.get("web_signal_candidates") or []),
    "summary": (
      f"Digest Preview: theme={preview.get('theme_name') or '(unset)'}, "
      f"candidates={len(preview.get('web_signal_candidates') or [])}"
    ),
  }


def _summarize_watch_profile_draft(project_root: Path | str | None) -> dict[str, Any]:
  status = resolve_watch_profile_draft_status(project_root)
  draft = status.get("draft")
  if not draft:
    return {
      "status": status.get("load_status") or "missing",
      "latest_path": status.get("latest_path"),
      "summary": status.get("load_message") or "approved watch profile draft がありません。",
    }
  approved_counts = {
    "keywords": len(draft.get("approved_keywords") or []),
    "companies": len(draft.get("approved_companies") or []),
    "technology_terms": len(draft.get("approved_technology_terms") or []),
    "market_applications": len(draft.get("approved_market_applications") or []),
    "public_projects": len(draft.get("approved_public_projects") or []),
  }
  return {
    "status": "ok",
    "latest_path": status.get("latest_path"),
    "theme_name": draft.get("theme_name"),
    "approved_by": draft.get("approved_by"),
    "approved_at": draft.get("approved_at"),
    "approved_counts": approved_counts,
    "summary": (
      f"Watch Profile Draft: theme={draft.get('theme_name') or '(unset)'}, "
      f"approved_by={draft.get('approved_by') or '(unset)'}, "
      f"counts={approved_counts}"
    ),
  }


def _summarize_next_cycle_search(project_root: Path | str | None) -> dict[str, Any]:
  latest_path = find_latest_next_cycle_search_plan_path(project_root or Path.cwd())
  if latest_path is None:
    return {"status": "missing", "summary": "latest next cycle search plan がありません。"}
  plan = load_next_cycle_search_plan(latest_path)
  if not plan:
    return {"status": "invalid", "latest_path": str(latest_path), "summary": "読み込み失敗"}
  queries = plan.get("query_candidates") or []
  query_texts = [str(item.get("query") or item) if isinstance(item, dict) else str(item) for item in queries]
  return {
    "status": "ok",
    "latest_path": str(latest_path),
    "created_at": plan.get("created_at"),
    "query_count": len(query_texts),
    "query_preview": query_texts[:5],
    "summary": f"Next Cycle Search Plan: {len(query_texts)} query candidate(s)",
  }


def _resolve_latest_operation_status(project_root: Path | str | None) -> tuple[dict[str, Any], Path | None]:
  latest_path = find_latest_operation_status_path(project_root)
  if latest_path is None:
    return (
      {
        "status": "missing",
        "message": "saved live_operation_status がありません。Live Operation Console で状態を保存してください。",
      },
      None,
    )
  payload = load_latest_operation_status(project_root)
  if not payload:
    return (
      {
        "status": "invalid",
        "latest_path": str(latest_path),
        "message": "latest live_operation_status の読み込みに失敗しました。",
      },
      latest_path,
    )
  return (
    {
      "status": "ok",
      "latest_path": str(latest_path),
      "checked_at": payload.get("checked_at"),
      "cycle_id": payload.get("cycle_id"),
      "next_recommended_action": payload.get("next_recommended_action"),
      "step_statuses": payload.get("step_statuses"),
      "warnings": payload.get("warnings"),
    },
    latest_path,
  )


def _build_current_status_summary(
  *,
  operation_status: dict[str, Any],
  artifact_inventory: dict[str, Any],
) -> str:
  counts = artifact_inventory.get("artifact_counts") or {}
  if operation_status.get("status") == "ok":
    next_action = operation_status.get("next_recommended_action") or "手動運用を継続してください。"
    return (
      f"Live Beta は手動週次運用中です。最新 operation status: "
      f"checked_at={operation_status.get('checked_at')}. "
      f"次の推奨: {next_action} "
      f"成果物数: web_signal={counts.get('web_signal_packs', 0)}, "
      f"digest={counts.get('digest_previews', 0)}, "
      f"release_packs={counts.get('live_release_packs', 0)}."
    )
  return (
    "Live Beta は手動週次運用中ですが、保存済み operation status がありません。"
    " Live Operation Console で状態を保存してから共有パックを作成することを推奨します。"
  )


def build_stakeholder_share_message(
  *,
  service_name: str,
  service_url: str,
  release_note: str | None = None,
) -> str:
  note_block = ""
  if release_note and release_note.strip():
    note_block = f"\n\n【今回の補足】\n{release_note.strip()}\n"

  return (
    "Tech Cartography v7 Live Beta について\n"
    "\n"
    "これは PatentScout AI v7 の Live Beta 環境です。"
    " 特許・技術動向の探索を補助する研究開発向けツールであり、"
    " 法的判断（FTO・侵害・有効性）を行うものではありません。\n"
    "\n"
    "【できること（手動運用）】\n"
    "- Web Signal Pack: Web 上のシグナル候補を収集・確認\n"
    "- Digest Preview: 週次ダイジェストの下書きプレビュー（送信なし）\n"
    "- Watch Expansion / Watch Profile Draft: 監視範囲の拡張候補と人間承認 Draft\n"
    "- Next Cycle Search / Web Signal Pack: 次サイクルの検索計画と候補収集\n"
    "- Live Operation Console: 週次サイクルの進捗確認\n"
    "\n"
    "【今回見てほしい観点】\n"
    "- 候補情報がどのように整理・確認されるか\n"
    "- 人間承認を挟む運用フローになっているか\n"
    "- 研究開発・技術探索の補助として使えるか\n"
    "\n"
    "【まだできないこと】\n"
    "- 自動週次実行（scheduler OFF）\n"
    "- 一斉メール送信（self_only テストのみ）\n"
    "- 外部 API の常時 ON 運用\n"
    "- FTO / 侵害 / 有効性の判断\n"
    "- Web Signal の事実確定\n"
    "\n"
    "【安全上の注意】\n"
    "- Web / Paper 情報は裏取り候補です\n"
    "- 共有先は限定公開として扱ってください\n"
    "- ログイン情報は別途、安全な経路で共有してください（本パックには含めません）\n"
    f"- サービス名: {service_name}\n"
    f"- アクセス URL: {service_url}\n"
    f"{note_block}"
    "\n"
    "ご確認のうえ、フィードバックをお願いします。"
  ).strip()


def build_three_min_demo_script() -> str:
  return (
    "Tech Cartography v7 Live Beta — 3分デモ台本\n"
    "\n"
    "0:00-0:30 課題\n"
    "  技術動向や特許周辺情報は分散しており、毎週「何を確認すべきか」が属人化しがちです。"
    "  本サービスは自動で正解を出すのではなく、候補を整理し人間が確認・承認する補助を目指します。\n"
    "\n"
    "0:30-1:00 サービス概要\n"
    "  Live Beta は Cloud Run 上の手動運用環境です。"
    " scheduler OFF、外部 API は通常 OFF、メールは self_only テストのみ。"
    " 研究開発・技術探索の補助であり、法的判断は行いません。\n"
    "\n"
    "1:00-1:40 Web Signal / Digest Preview\n"
    "  入力・実行タブで Web Signal Pack を作成し、Web 上の候補を一覧します。"
    "  次に Digest Preview で週次ダイジェスト下書きを確認します（送信はしません）。"
    "  ここまでが「今週の確認候補」の整理です。\n"
    "\n"
    "1:40-2:20 Watch Expansion / Watch Profile Draft\n"
    "  Watch Expansion Proposals で監視範囲の拡張候補を作成し、"
    "  人間が承認した項目だけ Watch Profile Draft に保存します。"
    "  本番 profile は自動更新されません。\n"
    "\n"
    "2:20-2:50 Next Cycle Search / Operation Console\n"
    "  Watch Profile Draft から Next Cycle Search Plan を作成し、"
    "  選択した query のみ Next Cycle Web Signal Pack を実行します。"
    "  Live Operation Console で7ステップの進捗と次アクションを確認・保存します。\n"
    "\n"
    "2:50-3:00 今後の展望\n"
    "  候補整理と人間承認のループを継続し、"
    "  認証強化・閲覧権限・承認付き共有など本番化要件を段階的に検討します。"
  ).strip()


def build_known_limitations_text() -> str:
  lines = ["Known Limitations and Scope", ""]
  for item in _KNOWN_LIMITATIONS:
    lines.append(f"- {item}")
  return "\n".join(lines).strip()


def build_admin_operation_checklist_text() -> str:
  lines = ["Admin Operation Checklist", ""]
  for index, item in enumerate(_ADMIN_CHECKLIST, start=1):
    lines.append(f"{index}. {item}")
  return "\n".join(lines).strip()


def build_live_beta_release_pack(
  project_root: Path | str | None = None,
  *,
  release_note: str | None = None,
) -> dict[str, Any]:
  created_at = _utc_now_iso()
  release_pack_id = f"live-beta-release-{uuid.uuid4().hex[:12]}"
  service_name = _service_name()
  service_url = _service_url_placeholder()
  artifact_inventory = describe_live_artifact_storage(project_root)
  latest_operation_status, _operation_path = _resolve_latest_operation_status(project_root)
  digest_summary = _summarize_digest_preview(project_root)
  watch_summary = _summarize_watch_profile_draft(project_root)
  next_cycle_summary = _summarize_next_cycle_search(project_root)
  runtime_flags = _collect_runtime_flags()

  stakeholder_message = build_stakeholder_share_message(
    service_name=service_name,
    service_url=service_url,
    release_note=release_note,
  )
  demo_script = build_three_min_demo_script()
  known_limitations = build_known_limitations_text()
  admin_checklist = build_admin_operation_checklist_text()

  for text in (stakeholder_message, demo_script, known_limitations, admin_checklist):
    _validate_release_pack_output(text)

  manual_flow = [
    {"step": index, "description": text, "ui_hint": STEP_GUIDANCE.get(step, "")}
    for index, (step, text) in enumerate(zip(STEP_ORDER + ("operation_console",), _MANUAL_WEEKLY_FLOW), start=1)
  ]

  pack: dict[str, Any] = {
    "release_pack_id": release_pack_id,
    "created_at": created_at,
    "service_name": service_name,
    "service_url_placeholder": service_url,
    "current_status_summary": _build_current_status_summary(
      operation_status=latest_operation_status,
      artifact_inventory=artifact_inventory,
    ),
    "what_this_service_does": (
      "PatentScout AI v7 / Tech Cartography の Live Beta 環境。"
      " Web Signal 候補の収集、Digest 下書き、Watch 拡張候補、"
      " 次サイクル検索計画を手動で実行し、人間が確認・承認する研究開発補助ツール。"
    ),
    "target_users": (
      "社内の研究開発担当、特許・技術情報を扱うアナリスト、"
      " Live Beta の運用・評価を行う admin。"
    ),
    "manual_weekly_operation_flow": manual_flow,
    "current_artifact_inventory": artifact_inventory,
    "latest_operation_status": latest_operation_status,
    "latest_digest_preview_summary": digest_summary,
    "approved_watch_profile_summary": watch_summary,
    "next_cycle_search_summary": next_cycle_summary,
    "safety_policy": {
      "web_signals_are_candidates": True,
      "no_fto_or_infringement_analysis": True,
      "email_mode": "self_only",
      "scheduler": "off",
      "external_api_default": "off",
      "manual_operation_only": True,
      "limited_distribution": True,
    },
    "known_limitations": known_limitations,
    "admin_operation_checklist": list(_ADMIN_CHECKLIST),
    "stakeholder_share_message": stakeholder_message,
    "three_min_demo_script": demo_script,
    "next_actions": _build_next_actions(latest_operation_status, artifact_inventory),
    "release_note": (release_note or "").strip() or None,
    "runtime_flags": runtime_flags,
    "live_outputs_root_env": str(os.environ.get(LIVE_OUTPUTS_ROOT_ENV, "") or "(unset)"),
    "active_storage_root": str(get_live_outputs_root(project_root)),
  }

  serialized = json.dumps(pack, ensure_ascii=False, indent=2)
  _validate_release_pack_output(serialized, strict_text=False)
  return pack


def _build_next_actions(
  operation_status: dict[str, Any],
  artifact_inventory: dict[str, Any],
) -> list[str]:
  actions: list[str] = []
  if operation_status.get("status") != "ok":
    actions.append("Live Operation Console で状態を保存する")
  elif operation_status.get("next_recommended_action"):
    actions.append(str(operation_status["next_recommended_action"]))
  counts = artifact_inventory.get("artifact_counts") or {}
  if counts.get("live_release_packs", 0) == 0:
    actions.append("共有パックを関係者へ限定公開で配布する")
  actions.append("フィードバックを収集し、次 Phase（認証強化 / 閲覧権限）を検討する")
  return actions


def render_live_beta_release_pack_markdown(pack: dict[str, Any]) -> str:
  lines = [
    "# Live Beta Release Pack",
    "",
    f"- release_pack_id: {pack.get('release_pack_id')}",
    f"- created_at: {pack.get('created_at')}",
    f"- service_name: {pack.get('service_name')}",
    f"- service_url: {pack.get('service_url_placeholder')}",
    "",
    "## Current status summary",
    "",
    str(pack.get("current_status_summary") or ""),
    "",
    "## What this service does",
    "",
    str(pack.get("what_this_service_does") or ""),
    "",
    "## Target users",
    "",
    str(pack.get("target_users") or ""),
    "",
    "## Manual weekly operation flow",
    "",
  ]
  for item in pack.get("manual_weekly_operation_flow") or []:
    lines.append(f"{item.get('step')}. {item.get('description')}")
  lines.extend(
    [
      "",
      "## Latest operation status",
      "",
      f"status: {(pack.get('latest_operation_status') or {}).get('status')}",
    ],
  )
  op = pack.get("latest_operation_status") or {}
  if op.get("status") == "ok":
    lines.append(f"checked_at: {op.get('checked_at')}")
    lines.append(f"next_recommended_action: {op.get('next_recommended_action')}")
  else:
    lines.append(str(op.get("message") or op.get("summary") or ""))

  lines.extend(["", "## Stakeholder share message", "", str(pack.get("stakeholder_share_message") or ""), ""])
  lines.extend(["## 3-minute demo script", "", str(pack.get("three_min_demo_script") or ""), ""])
  lines.extend(["## Known limitations", "", str(pack.get("known_limitations") or ""), ""])
  lines.extend(["## Admin checklist", ""])
  for index, item in enumerate(pack.get("admin_operation_checklist") or [], start=1):
    lines.append(f"{index}. {item}")
  lines.extend(["", "## Next actions", ""])
  for item in pack.get("next_actions") or []:
    lines.append(f"- {item}")
  if pack.get("release_note"):
    lines.extend(["", "## Release note", "", str(pack["release_note"]), ""])
  return "\n".join(lines).strip() + "\n"


def render_live_beta_release_pack_text(pack: dict[str, Any]) -> str:
  sections = [
    ("STAKEHOLDER SHARE MESSAGE", pack.get("stakeholder_share_message")),
    ("3-MINUTE DEMO SCRIPT", pack.get("three_min_demo_script")),
    ("KNOWN LIMITATIONS AND SCOPE", pack.get("known_limitations")),
    ("ADMIN OPERATION CHECKLIST", build_admin_operation_checklist_text()),
    ("CURRENT STATUS", pack.get("current_status_summary")),
  ]
  parts: list[str] = [
    "Live Beta Release Pack",
    f"release_pack_id: {pack.get('release_pack_id')}",
    f"created_at: {pack.get('created_at')}",
    "",
  ]
  for title, body in sections:
    parts.extend([f"=== {title} ===", "", str(body or ""), ""])
  return "\n".join(parts).strip() + "\n"


def _build_zip_readme(pack: dict[str, Any]) -> str:
  return (
    "# Tech Cartography v7 Live Beta Release Pack\n"
    "\n"
    "This bundle is for limited stakeholder review only.\n"
    "\n"
    f"- release_pack_id: {pack.get('release_pack_id')}\n"
    f"- created_at: {pack.get('created_at')}\n"
    f"- service_name: {pack.get('service_name')}\n"
    "\n"
    "Contents:\n"
    "- release_pack.json — structured metadata\n"
    "- stakeholder_share_message.txt\n"
    "- demo_script_3min.txt\n"
    "- known_limitations_and_scope.txt\n"
    "- admin_operation_checklist.txt\n"
    "\n"
    "No login credentials, API keys, or mail relay configuration values are included.\n"
    "Web Signals are candidates — not confirmed facts.\n"
    "Not for FTO, infringement, or validity analysis.\n"
  )


def _write_release_pack_zip(zip_path: Path, pack: dict[str, Any]) -> None:
  zip_payload = {
    "README.md": _build_zip_readme(pack),
    "demo_script_3min.txt": str(pack.get("three_min_demo_script") or ""),
    "stakeholder_share_message.txt": str(pack.get("stakeholder_share_message") or ""),
    "known_limitations_and_scope.txt": str(pack.get("known_limitations") or ""),
    "admin_operation_checklist.txt": build_admin_operation_checklist_text(),
    "release_pack.json": json.dumps(pack, ensure_ascii=False, indent=2),
  }
  for content in zip_payload.values():
    _validate_release_pack_output(content)

  with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for name, content in zip_payload.items():
      archive.writestr(name, content)


def save_live_beta_release_pack(
  pack: dict[str, Any],
  project_root: Path | str | None = None,
) -> dict[str, str]:
  out_dir = get_live_release_pack_dir(project_root)
  writable, message = check_directory_writable(out_dir)
  if not writable:
    raise ValueError(message or f"Cannot write release pack to {out_dir}")

  created_at = str(pack.get("created_at") or _utc_now_iso())
  slug = _timestamp_slug(created_at)
  json_path = out_dir / f"live_beta_release_pack_{slug}.json"
  md_path = out_dir / f"live_beta_release_pack_{slug}.md"
  txt_path = out_dir / f"live_beta_release_pack_{slug}.txt"
  zip_path = out_dir / f"live_beta_release_pack_{slug}.zip"

  json_text = json.dumps(pack, ensure_ascii=False, indent=2)
  md_text = render_live_beta_release_pack_markdown(pack)
  txt_text = render_live_beta_release_pack_text(pack)
  for content in (json_text, md_text, txt_text):
    _validate_release_pack_output(content, strict_text=False)

  json_path.write_text(json_text, encoding="utf-8")
  md_path.write_text(md_text, encoding="utf-8")
  txt_path.write_text(txt_text, encoding="utf-8")
  _write_release_pack_zip(zip_path, pack)

  return {
    "json": str(json_path),
    "markdown": str(md_path),
    "text": str(txt_path),
    "zip": str(zip_path),
  }


def build_and_save_live_beta_release_pack(
  project_root: Path | str | None = None,
  *,
  release_note: str | None = None,
  user_context: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, str] | None, str | None]:
  run_id = generate_run_id()
  started_at = _utc_now_iso()
  pack = build_live_beta_release_pack(project_root, release_note=release_note)
  pack = attach_user_run_metadata(pack, user_context=user_context, run_id=run_id)
  try:
    saved_paths = save_live_beta_release_pack(pack, project_root)
    record_live_run(
      action_type="live_beta_release_pack",
      status="success",
      run_id=run_id,
      started_at=started_at,
      user_context=user_context,
      input_summary=release_note,
      output_artifact_paths=saved_paths,
      project_root=project_root,
    )
  except (OSError, ValueError) as exc:
    record_live_run(
      action_type="live_beta_release_pack",
      status="failed",
      run_id=run_id,
      started_at=started_at,
      user_context=user_context,
      input_summary=release_note,
      error_summary=str(exc),
      project_root=project_root,
    )
    return pack, None, str(exc)
  return pack, saved_paths, None
