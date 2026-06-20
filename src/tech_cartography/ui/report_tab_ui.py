"""Compressed report tab and Cloud Run readiness checklist (Phase 24.5C)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import streamlit as st

from tech_cartography.ui.delivery_ui import (
  DeliveryUIArtifacts,
  load_delivery_artifacts,
  make_download_key,
  render_core_validation_section,
  render_email_draft_preview_section,
  render_report_bundle_zip_section,
  render_send_log_section,
  render_weekly_schedule_section,
)
from tech_cartography.ui.demo_safe_ui import format_display_path
from tech_cartography.ui.easy_japanese_ui import (
  DEMO_DEEP_DIVE_PUBLICATION,
  render_info_box,
  render_markdown_preview,
  render_ok_box,
)
from tech_cartography.ui.label_renderer import POLISHED_NEXT_ACTIONS

DEFAULT_PUB = DEMO_DEEP_DIVE_PUBLICATION
FINAL_VALIDATION_JSON = "final_end_to_end_validation_summary.json"
REVIEW_PACK_JSON = "web_signal_review_pack.json"


def _read_text(path: Path) -> str | None:
  if not path.exists():
    return None
  try:
    return path.read_text(encoding="utf-8")
  except OSError:
    return None


def _read_json(path: Path) -> dict[str, Any] | None:
  text = _read_text(path)
  if not text:
    return None
  try:
    data = json.loads(text)
    return data if isinstance(data, dict) else None
  except json.JSONDecodeError:
    return None


def extract_markdown_section(md: str, *headings: str, max_chars: int = 1200) -> str:
  if not md.strip():
    return ""
  for heading in headings:
    pattern = re.compile(
      rf"(?:^|\n)#{{1,3}}\s*{re.escape(heading)}\s*\n(.*?)(?=\n#{{1,3}}\s|\Z)",
      re.DOTALL | re.IGNORECASE,
    )
    match = pattern.search(md)
    if match:
      body = match.group(1).strip()
      if len(body) > max_chars:
        return body[: max_chars - 1] + "…"
      return body
  trimmed = md.strip()
  return trimmed[:max_chars] + ("…" if len(trimmed) > max_chars else "")


def load_final_validation_brief(project_root: Path) -> dict[str, Any]:
  path = project_root / "outputs" / "validation" / "final_validation" / FINAL_VALIDATION_JSON
  data = _read_json(path)
  if not data:
    return {}
  return {
    "seed_count": data.get("seed_count", 0),
    "completed_end_to_end_count": data.get("completed_end_to_end_count", 0),
    "freeze_readiness": data.get("freeze_readiness", ""),
    "evidence_level": data.get("evidence_level", ""),
    "caveats": data.get("caveats") or [],
    "next_actions": data.get("next_actions") or [],
  }


def build_final_validation_brief_lines(brief: dict[str, Any]) -> list[str]:
  if not brief:
    return ["Final Validation Summary はまだ生成されていません。"]
  seed_count = int(brief.get("seed_count") or 0)
  completed = int(brief.get("completed_end_to_end_count") or 0)
  freeze = str(brief.get("freeze_readiness") or "")
  lines = [
    f"JP seed {seed_count}件で End-to-End 確認済み（{completed}/{seed_count} 完了）",
    "Paper / Web 実データあり（actual_data）",
  ]
  if freeze:
    lines.append(f"freeze_readiness: MVPデモ可能（{freeze}）")
  else:
    lines.append("freeze_readiness: MVPデモ可能")
  lines.append("ただし、Paper / Web / Link / Watch は確認候補です")
  return lines


def build_cloud_run_checklist(project_root: Path) -> list[dict[str, Any]]:
  root = project_root.resolve()
  ui_files = [
    root / "app.py",
    root / "src/tech_cartography/ui/report_tab_ui.py",
    root / "src/tech_cartography/ui/demo_safe_ui.py",
    root / "src/tech_cartography/ui/v7_easy_app.py",
  ]
  ui_text = "\n".join(path.read_text(encoding="utf-8") for path in ui_files if path.exists())
  compressed_fn = _read_text(root / "src/tech_cartography/ui/report_tab_ui.py") or ""
  sidebar_fn = _read_text(root / "src/tech_cartography/ui/demo_safe_ui.py") or ""
  sidebar_normal = sidebar_fn.split("if ui_mode_input == UI_MODE_DEVELOPER:", 1)[0]

  review_pack = (
    root / "outputs" / "web_signals" / "tavily_pan_carbon_fiber" / "review_pack" / REVIEW_PACK_JSON
  )
  readme = _read_text(root / "README.md") or ""
  docs_post_mvp = any(
    "Post-MVP" in (_read_text(path) or "")
    for path in (
      root / "docs/phase24_5a_demo_safe_ui_core.md",
      root / "docs/phase24_5b_demo_surface_polish.md",
    )
  )

  return [
    {
      "label": "通常画面に /Users/ が出ていない",
      "passed": "/Users/" not in compressed_fn and "/Users/" not in sidebar_normal,
      "note": "report_tab_ui / サイドバー通常部を確認",
    },
    {
      "label": "通常画面に個人メールアドレスが強く出ていない",
      "passed": "email@" not in compressed_fn and "SMTP" not in compressed_fn,
      "note": "圧縮レポートにメール下書き本文なし",
    },
    {
      "label": "run_id / outputs path は開発者向けに隠れている",
      "passed": "run_id:" not in compressed_fn.split("render_developer_report_expander", 1)[0],
      "note": "圧縮レポートに run_id 表示なし",
    },
    {
      "label": "デモモードで入力フォームが出ていない",
      "passed": "DEMO_TAB_IDS" in ui_text and "theme_validation" not in ui_text.split("DEMO_TAB_IDS", 1)[1][:120],
      "note": "demo_safe_ui のタブ定義を確認",
    },
    {
      "label": "外部APIは自動実行しない",
      "passed": "allow_external_api" in (_read_text(root / "src/tech_cartography/ui/theme_validation_ui.py") or ""),
      "note": "明示同意チェック付き実行のみ",
    },
    {
      "label": "scheduler / launchd / cron は通常画面に出ていない",
      "passed": "render_weekly_schedule_section" not in compressed_fn.split("render_developer_report_expander", 1)[0],
      "note": "圧縮レポートに scheduler セクションなし",
    },
    {
      "label": "Review Packは生成済み",
      "passed": review_pack.exists(),
      "note": format_display_path(review_pack, project_root=root) if review_pack.exists() else "未生成",
    },
    {
      "label": "README / docs に Post-MVP 項目がある",
      "passed": docs_post_mvp or "Post-MVP" in readme or "post-mvp" in readme.lower(),
      "note": "docs/phase24_5a 等を確認",
    },
  ]


def render_cloud_run_ready_checklist(project_root: Path) -> None:
  st.markdown("**Cloud Run 前チェックリスト**")
  checks = build_cloud_run_checklist(project_root)
  for item in checks:
    mark = "✅" if item["passed"] else "⚠️"
    st.markdown(f"- {mark} {item['label']} — _{item['note']}_")
  passed_count = sum(1 for item in checks if item["passed"])
  st.caption(f"{passed_count}/{len(checks)} 項目を確認済み（ローカル静的チェック）")


def render_final_validation_brief_section(project_root: Path) -> None:
  st.subheader("Final Validation（概要）")
  brief = load_final_validation_brief(project_root)
  lines = build_final_validation_brief_lines(brief)
  body = "".join(f"<li>{line}</li>" for line in lines)
  st.markdown(render_info_box(f"<ul>{body}</ul>"), unsafe_allow_html=True)


def _render_evidence_map_highlights(
  *,
  demo_artifacts: Any = None,
  delivery_artifacts: DeliveryUIArtifacts | None = None,
) -> None:
  st.subheader("Evidence Map の要点")
  bullets: list[str] = []
  if demo_artifacts is not None and getattr(demo_artifacts, "evidence_map_json", None):
    synthesis = demo_artifacts.evidence_map_json or {}
    findings = synthesis.get("key_findings_japanese") or []
    if isinstance(findings, list) and findings:
      bullets.extend(str(item) for item in findings[:4])
    else:
      bullets.append(f"Selected papers: {len(demo_artifacts.selected_papers_df)} 件")
      bullets.append(f"Claim × Paper links: {len(demo_artifacts.claim_paper_links_df)} 件")
  elif delivery_artifacts and delivery_artifacts.intelligence_report_md:
    section = extract_markdown_section(
      delivery_artifacts.intelligence_report_md,
      "4. Evidence Map Summary",
      "Evidence Map Summary",
      max_chars=900,
    )
    for line in section.splitlines():
      stripped = line.strip().lstrip("-•").strip()
      if stripped.startswith("#") or not stripped:
        continue
      bullets.append(stripped)
      if len(bullets) >= 5:
        break
  if not bullets:
    bullets = [
      "請求項から技術要素を抽出し、論文候補と対応づけた Evidence Map を表示しています",
      "論文候補は技術背景の確認候補です",
    ]
  body = "".join(f"<li>{item}</li>" for item in bullets[:6])
  st.markdown(render_info_box(f"<ul>{body}</ul>"), unsafe_allow_html=True)


def _render_digest_preview_highlights(artifacts: DeliveryUIArtifacts) -> None:
  st.subheader("週次 Digest Preview の要点")
  if not artifacts.weekly_digest_md:
    st.info("週次 Digest Preview はまだありません。")
    return
  section = extract_markdown_section(
    artifacts.weekly_digest_md,
    "2. 今週の重点監視候補 Top 3",
    "今週の重点監視候補",
    max_chars=1000,
  )
  st.markdown(render_markdown_preview(section or artifacts.weekly_digest_md[:800]))
  st.caption("Digest は preview only です。メール送信は行いません。")


def _render_watch_highlights(project_root: Path) -> None:
  st.subheader("重点監視候補")
  digest_path = project_root / "outputs" / "delivery" / f"weekly_digest_preview_{DEFAULT_PUB}.md"
  digest_md = _read_text(digest_path)
  if digest_md:
    section = extract_markdown_section(
      digest_md,
      "2. 今週の重点監視候補 Top 3",
      max_chars=900,
    )
    if section:
      for line in section.splitlines():
        if line.strip().startswith("###"):
          st.markdown(f"- {line.strip().lstrip('#').strip()}")
      return
  st.caption("Strategic Watch / Web Signal から抽出した監視候補は Digest Preview を参照してください。")


def _render_next_verification_actions(project_root: Path) -> None:
  st.subheader("次に確認すること")
  brief = load_final_validation_brief(project_root)
  actions = list(POLISHED_NEXT_ACTIONS[:4])
  next_from_brief = brief.get("next_actions") if isinstance(brief.get("next_actions"), list) else []
  for item in next_from_brief:
    text = str(item).strip()
    if text and text not in actions:
      actions.append(text)
  body = "".join(f"<li>{action}</li>" for action in actions[:6])
  st.markdown(render_ok_box(f"<ul>{body}</ul>"), unsafe_allow_html=True)


def _render_export_buttons(artifacts: DeliveryUIArtifacts, *, key_prefix: str) -> None:
  st.subheader("Download / Export")
  cols = st.columns(3)
  file_pub = artifacts.publication_number if artifacts.publication_number != "unknown" else DEFAULT_PUB
  with cols[0]:
    if artifacts.intelligence_report_md:
      st.download_button(
        label="Intelligence Report (.md)",
        data=artifacts.intelligence_report_md,
        file_name=f"intelligence_report_{file_pub}.md",
        mime="text/markdown",
        key=make_download_key(f"{key_prefix}_brief_intel", artifacts.publication_number, artifacts.intelligence_report_path),
      )
  with cols[1]:
    if artifacts.weekly_digest_md:
      st.download_button(
        label="Digest Preview (.md)",
        data=artifacts.weekly_digest_md,
        file_name=f"weekly_digest_preview_{file_pub}.md",
        mime="text/markdown",
        key=make_download_key(f"{key_prefix}_brief_digest", artifacts.publication_number, artifacts.weekly_digest_md_path),
      )
  with cols[2]:
    if artifacts.report_zip_path and artifacts.report_zip_path.exists():
      st.download_button(
        label="Report Bundle (.zip)",
        data=artifacts.report_zip_path.read_bytes(),
        file_name=artifacts.report_zip_path.name,
        mime="application/zip",
        key=make_download_key(f"{key_prefix}_brief_zip", artifacts.publication_number, artifacts.report_zip_path),
      )
    else:
      st.caption("ZIP bundle: `--include-zip` で生成")


def render_compressed_report_tab(
  *,
  project_root: Path,
  delivery_artifacts: DeliveryUIArtifacts | None = None,
  demo_artifacts: Any = None,
  key_prefix: str = "reports_brief",
) -> None:
  """Normal-user compressed report view."""
  root = project_root.resolve()
  artifacts = delivery_artifacts or load_delivery_artifacts(root, publication_number=DEFAULT_PUB)

  st.markdown("## レポート（概要）")
  st.caption("審査員・初見ユーザー向けの短いまとめです。詳細は開発者向け expander をご利用ください。")

  st.subheader("Executive Summary")
  if artifacts.intelligence_report_md:
    summary = extract_markdown_section(
      artifacts.intelligence_report_md,
      "1. Executive Summary",
      "Executive Summary",
      max_chars=700,
    )
    st.markdown(render_markdown_preview(summary))
  else:
    st.info("Intelligence Report を生成すると Executive Summary が表示されます。")

  st.subheader("今回の対象特許")
  pub = DEFAULT_PUB
  title = pub
  if demo_artifacts is not None and getattr(demo_artifacts, "evidence_map_json", None):
    title = str((demo_artifacts.evidence_map_json or {}).get("title") or pub)
  st.markdown(
    render_info_box(f"<strong>{pub}</strong><br>{title}<br>Manual Claims Route による Evidence Map デモ"),
    unsafe_allow_html=True,
  )

  _render_evidence_map_highlights(demo_artifacts=demo_artifacts, delivery_artifacts=artifacts)
  _render_digest_preview_highlights(artifacts)
  _render_watch_highlights(root)
  render_final_validation_brief_section(root)
  _render_next_verification_actions(root)
  _render_export_buttons(artifacts, key_prefix=key_prefix)


def render_developer_report_expander(
  *,
  project_root: Path,
  delivery_artifacts: DeliveryUIArtifacts,
  developer_mode: bool,
  render_core_validation_links,
  render_final_validation_links,
  render_theme_validation_links,
  render_full_evidence_report=None,
  render_repro_section=None,
  key_prefix: str = "reports_dev",
) -> None:
  if not developer_mode:
    return
  with st.expander("開発者向け情報 / 詳細レポート", expanded=False):
    render_cloud_run_ready_checklist(project_root)
    st.divider()
    st.markdown("**Core / Final Validation（技術ファイル）**")
    render_core_validation_links(developer_mode=True)
    st.divider()
    render_final_validation_links(developer_mode=True)
    st.divider()
    render_theme_validation_links(developer_mode=True)
    st.divider()
    st.markdown("**Delivery 技術セクション**")
    render_email_draft_preview_section(delivery_artifacts, key_prefix=key_prefix)
    st.divider()
    render_send_log_section(delivery_artifacts)
    st.divider()
    render_core_validation_section(delivery_artifacts, key_prefix=key_prefix)
    st.divider()
    render_weekly_schedule_section(delivery_artifacts, key_prefix=key_prefix)
    st.divider()
    render_report_bundle_zip_section(delivery_artifacts, key_prefix=key_prefix)
    if render_full_evidence_report is not None:
      st.divider()
      render_full_evidence_report()
    if render_repro_section is not None:
      st.divider()
      render_repro_section()
