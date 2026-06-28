"""Evidence-aware Weekly Watch preview UI (Phase 27S.7)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from tech_cartography.services.v8_demo_flow_export_readiness import load_evidence_aware_watch_context
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_warning_box


def render_evidence_aware_watch_section(
  case_id: str,
  project_root: Path,
  *,
  key_prefix: str = "v8_ev_watch",
) -> bool:
  """Render Evidence-aware Gap → Weekly Watch connection. Returns True if context loaded."""
  st.markdown("#### Evidence-aware Gap → Weekly Watch")
  ctx = load_evidence_aware_watch_context(case_id, project_root=project_root)
  if not ctx:
    st.markdown(
      render_info_box(
        "Evidence-aware Gap 出力がありません。"
        " 先に Gap / Next Actions タブで Generate Gap / Next Actions from Claim-Example Evidence を実行してください。"
      ),
      unsafe_allow_html=True,
    )
    return False

  st.markdown(
    render_info_box(
      "<strong>今回のEvidence-aware Gapから、次回Watch Profileへ以下を追加候補として提案します。</strong><br>"
      "• CN108286090Aの物性値・表候補の原文確認<br>"
      "• CN108286090Aの工程条件確認<br>"
      "• 他Top5公報のOCR / section / facts抽出"
    ),
    unsafe_allow_html=True,
  )

  if ctx.watch_proposal_bullets:
    for bullet in ctx.watch_proposal_bullets:
      st.caption(f"- {bullet}")

  st.markdown("##### Top 3 Next Actions（Evidence-aware）")
  for idx, title in enumerate(ctx.top3_action_titles, start=1):
    st.caption(f"{idx}. {title}")

  st.markdown("##### Watch Profile update proposal")
  if ctx.watch_profile_text:
    st.markdown(ctx.watch_profile_text)
  else:
    st.caption("watch_profile_update_proposal.md がありません")

  st.markdown("##### Digest preview")
  st.caption(f"件名案: {ctx.digest_subject_draft}")
  st.caption("メール送信: demo OFF / not sent")
  if ctx.digest_preview_text:
    with st.expander("digest_summary.md", expanded=True):
      st.markdown(ctx.digest_preview_text)
  else:
    st.caption("digest_summary.md がありません")

  st.markdown("##### Scheduler plan")
  st.caption("Scheduler起動: demo OFF — 実運用では週次で再確認")
  st.caption("scope expansion feedback と接続 — 人手承認後に Watch Profile 反映")

  st.markdown(
    render_warning_box(
      "Digest preview のみ — メール送信しません。"
      " Scheduler は起動しません。"
      " Evidenceは裏取り候補、Gapは未確認事項です。"
    ),
    unsafe_allow_html=True,
  )

  st.markdown(
    render_caution_box(
      "email_sent=False / scheduler_started=False は Judge Mode の正常状態です。"
    ),
    unsafe_allow_html=True,
  )

  col1, col2 = st.columns(2)
  watch_path = Path(ctx.watch_profile_path)
  digest_path = Path(ctx.digest_summary_path)
  if watch_path.exists():
    col1.download_button(
      "watch_profile_update_proposal.md",
      watch_path.read_bytes(),
      watch_path.name,
      "text/markdown",
      key=f"{key_prefix}_dl_watch",
    )
  if digest_path.exists():
    col2.download_button(
      "digest_summary.md",
      digest_path.read_bytes(),
      digest_path.name,
      "text/markdown",
      key=f"{key_prefix}_dl_digest",
    )

  with st.expander("Artifact trace（Evidence-aware Gap）", expanded=False):
    st.caption(f"gap output: {ctx.gap_output_dir}")
    if ctx.claim_example_links_dir:
      st.caption(f"claim_example_links: {ctx.claim_example_links_dir}")
    if ctx.human_review_checklist_path:
      st.caption(f"checklist: {ctx.human_review_checklist_path}")

  for warning in ctx.warnings:
    st.caption(warning)

  return True
