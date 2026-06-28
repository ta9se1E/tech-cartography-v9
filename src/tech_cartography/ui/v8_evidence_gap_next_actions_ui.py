"""Evidence-aware Gap / Next Actions UI (Phase 27S.6 / 27S.6.1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from tech_cartography.runtime.v8_evidence_gap_schema import (
  BINDING_VERSION_EXPECTED,
  EVIDENCE_GAP_SAFETY_NOTICES,
  GENERATION_METHOD,
)
from tech_cartography.services.v8_claim_example_binding import find_latest_claim_example_links_dir
from tech_cartography.services.v8_evidence_gap_next_actions import (
  build_and_export_evidence_aware_gap_next_actions,
  build_evidence_aware_gap_report,
  build_top3_next_actions_from_evidence_gaps,
  evidence_aware_gap_primary_available,
  find_latest_evidence_aware_gap_dir,
  is_evidence_aware_gap_pack,
)
from tech_cartography.services.v8_top5_pdf_pipeline_status import build_top5_pdf_pipeline_status
from tech_cartography.ui.easy_japanese_ui import render_info_box, render_warning_box

STATE_V8_EVIDENCE_GAP = "v8_evidence_gap_next_actions"

SUMMARY_CARD_HELP: dict[str, str] = {
  "Review-ready claims": "Claim-example evidence candidates found; human review required",
  "OCR review needed": "OCR-derived text or evidence requires source PDF review",
  "Property/table review needed": "Property values or table candidates require unit/source verification",
  "Pubs w/o example facts": "Claims whose publication still lacks example facts",
}


def _load_gap_csv(pack_dir: Path) -> pd.DataFrame:
  path = pack_dir / "gap_next_actions.csv"
  if not path.exists():
    return pd.DataFrame()
  return pd.read_csv(path)


def _load_summary_csv(pack_dir: Path) -> pd.DataFrame:
  path = pack_dir / "gap_next_actions_summary.csv"
  if not path.exists():
    return pd.DataFrame()
  return pd.read_csv(path)


def _binding_version_from_dir(bind_dir: Path | None) -> str:
  if not bind_dir:
    return ""
  links_csv = bind_dir / "claim_example_links.csv"
  if not links_csv.exists():
    return ""
  try:
    df = pd.read_csv(links_csv, usecols=["binding_version"])
    versions = df["binding_version"].dropna().astype(str).unique().tolist()
    return versions[0] if versions else ""
  except (ValueError, KeyError):
    return ""


def _needs_regenerate(case_id: str, project_root: Path) -> tuple[bool, str]:
  bind_dir = find_latest_claim_example_links_dir(case_id, project_root)
  gap_dir = find_latest_evidence_aware_gap_dir(case_id, project_root)
  if bind_dir is None:
    return False, "claim_example_links.csv がありません"
  if gap_dir is None or not is_evidence_aware_gap_pack(gap_dir):
    return True, "Evidence-aware Gap 出力が未生成です"
  bind_mtime = bind_dir.stat().st_mtime
  gap_mtime = gap_dir.stat().st_mtime
  if bind_mtime > gap_mtime:
    return True, "Claim-Example binding が Gap 出力より新しいです"
  version = _binding_version_from_dir(bind_dir)
  if version and version != BINDING_VERSION_EXPECTED:
    return True, f"binding_version={version} — {BINDING_VERSION_EXPECTED} への更新を推奨"
  return False, ""


def _render_primary_intro(summary_df: pd.DataFrame) -> None:
  st.markdown(
    render_info_box(
      "<strong>この画面は Claim-Example Binding Evidence Detail から作成した未確認事項です。</strong><br>"
      "• <strong>CN108286090A</strong> は review-ready 候補です — 人手レビュー可能な対応候補があります。<br>"
      "• 他Top5は実施例ファクト未取得のため、PDF/OCR/section/facts抽出が次アクションです。"
    ),
    unsafe_allow_html=True,
  )
  if summary_df.empty:
    return
  ready_pubs = summary_df.loc[
    summary_df.get("ready_for_human_review_count", 0).fillna(0).astype(int) > 0,
    "publication_number",
  ].tolist() if "ready_for_human_review_count" in summary_df.columns else []
  no_fact = int(summary_df.get("no_example_facts_gap_count", pd.Series(dtype=int)).sum())
  if ready_pubs:
    st.caption(f"Review-ready publications: {', '.join(ready_pubs)}")
  if no_fact:
    st.caption(f"Pubs without example facts: {no_fact} claims — next: OCR or facts extraction")


def _render_summary_cards(summary_df: pd.DataFrame) -> None:
  if summary_df.empty:
    return
  ready = int(summary_df.get("ready_for_human_review_count", pd.Series(dtype=int)).sum())
  ocr = int(summary_df.get("ocr_human_review_gap_count", pd.Series(dtype=int)).sum())
  prop = int(summary_df.get("property_value_review_gap_count", pd.Series(dtype=int)).sum())
  table = int(summary_df.get("table_review_gap_count", pd.Series(dtype=int)).sum())
  process = int(summary_df.get("process_condition_review_gap_count", pd.Series(dtype=int)).sum())
  no_facts = int(summary_df.get("no_example_facts_gap_count", pd.Series(dtype=int)).sum())

  c1, c2, c3, c4 = st.columns(4)
  c1.metric("Review-ready claims", ready, help=SUMMARY_CARD_HELP["Review-ready claims"])
  c2.metric("OCR review needed", ocr, help=SUMMARY_CARD_HELP["OCR review needed"])
  c3.metric("Property/table review needed", prop + table + process, help=SUMMARY_CARD_HELP["Property/table review needed"])
  c4.metric("Pubs w/o example facts", no_facts, help=SUMMARY_CARD_HELP["Pubs w/o example facts"])
  for label, help_text in SUMMARY_CARD_HELP.items():
    st.caption(f"**{label}:** {help_text}")


def _render_top3_actions(case_id: str, project_root: Path) -> None:
  report = build_evidence_aware_gap_report(case_id, project_root=project_root)
  if not report.gaps:
    st.caption("Top 3 Next Actions は未生成です。")
    return
  top3 = build_top3_next_actions_from_evidence_gaps(report)
  if not top3:
    st.caption("Top 3 Next Actions は未生成です。")
    return
  st.markdown("#### Top 3 Next Actions（Evidence-aware）")
  for action in top3:
    st.markdown(
      render_info_box(
        f"<strong>#{action.action_rank} {action.action_title}</strong><br>"
        f"type: {action.action_type} / target: {action.target_publication_number}<br>"
        f"expected_output: {action.expected_output}"
      ),
      unsafe_allow_html=True,
    )


def _render_gap_table(gap_df: pd.DataFrame) -> None:
  if gap_df.empty:
    st.caption("Gap records は0件です。")
    return
  display_cols = [
    "publication_number",
    "claim_no",
    "gap_type",
    "action_priority",
    "evidence_status",
    "next_action",
    "support_level",
    "matched_fact_types",
    "needs_human_review",
  ]
  cols = [c for c in display_cols if c in gap_df.columns]
  st.dataframe(gap_df[cols], width="stretch", hide_index=True)

  for _, row in gap_df.head(15).iterrows():
    label = f"{row.get('publication_number', '')} claim {row.get('claim_no', '')} — {row.get('gap_type', '')}"
    with st.expander(label, expanded=False):
      st.markdown(f"**gap_description:** {row.get('gap_description', '')}")
      st.markdown(f"**next_action:** {row.get('next_action', '')}")
      st.markdown(f"**top_evidence_snippets:** {row.get('top_evidence_snippets', '')}")
      st.markdown(f"**missing_elements:** {row.get('missing_elements', '')}")
      st.caption(f"source: {row.get('source_claim_example_links_csv', '')}")


def _render_pipeline_status(case_id: str, project_root: Path) -> None:
  statuses = build_top5_pdf_pipeline_status(case_id, project_root, project_root / "outputs")
  if not statuses:
    return
  st.markdown("#### Top5公報PDF — 解析状況（Evidence-aware）")
  rows = []
  for s in statuses:
    rows.append({
      "publication_number": s.publication_number,
      "status": s.pipeline_status_label or "—",
      "next_action": s.next_action,
      "details": s.pipeline_status_details or "—",
    })
  st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def _render_downloads(out_dir: Path, gap_df: pd.DataFrame, report_dict: dict[str, Any]) -> None:
  st.markdown("#### ダウンロード（Evidence-aware Gap 出力）")
  st.caption("ダウンロード対象は Claim-Example Evidence 由来の gap_next_actions 出力です。")
  csv_path = out_dir / "gap_next_actions.csv"
  if csv_path.exists():
    st.download_button(
      "CSV",
      csv_path.read_bytes(),
      csv_path.name,
      "text/csv",
      key=f"v8_ev_gap_dl_csv_{out_dir.name}",
    )
  md_path = out_dir / "gap_next_actions.md"
  if md_path.exists():
    st.download_button(
      "Markdown",
      md_path.read_bytes(),
      md_path.name,
      "text/markdown",
      key=f"v8_ev_gap_dl_md_{out_dir.name}",
    )
  for name, label in (
    ("watch_profile_update_proposal.md", "watch_profile_update_proposal.md"),
    ("digest_summary.md", "digest_summary.md"),
    ("human_review_checklist.md", "human_review_checklist.md"),
  ):
    path = out_dir / name
    if path.exists():
      st.download_button(label, path.read_bytes(), name, "text/markdown", key=f"v8_ev_gap_dl_{name}_{out_dir.name}")


def render_evidence_aware_gap_section(
  case_id: str,
  project_root: Path,
  *,
  key_prefix: str = "v8_ev_gap",
  show_title: bool = True,
) -> dict[str, Any] | None:
  """Render Evidence-aware Gap / Next Actions primary block."""
  if show_title:
    st.markdown("### Evidence-aware Gap / Next Actions")
  st.caption(f"generation_method: {GENERATION_METHOD}")

  for notice in EVIDENCE_GAP_SAFETY_NOTICES:
    st.caption(notice)
  st.markdown(
    render_warning_box(
      "Gapは弱点ではなく、未確認事項です。"
      " Evidenceは証明ではなく、裏取り候補です。"
      " OCR由来の数値・単位・表は原文確認が必要です。"
      " 本ツールは特許の有効性・侵害・FTOを判断しません。"
    ),
    unsafe_allow_html=True,
  )

  bind_dir = find_latest_claim_example_links_dir(case_id, project_root)
  if bind_dir is None or not (bind_dir / "claim_example_links.csv").exists():
    st.markdown(
      render_info_box(
        "claim_example_links.csv がありません。"
        " Top5 Deep Dive で Claim-Example binding を先に実行してください。"
      ),
      unsafe_allow_html=True,
    )
    return None

  bind_version = _binding_version_from_dir(bind_dir)
  st.caption(f"最新 binding: {bind_dir} (binding_version={bind_version or 'unknown'})")

  needs_regen, regen_reason = _needs_regenerate(case_id, project_root)
  latest_gap_dir = find_latest_evidence_aware_gap_dir(case_id, project_root)

  col1, col2 = st.columns(2)
  with col1:
    generate = st.button(
      "Generate Gap / Next Actions from Claim-Example Evidence",
      key=f"{key_prefix}_generate",
      type="primary",
    )
  with col2:
    regen_disabled = not needs_regen and latest_gap_dir is not None
    if st.button(
      "Re-generate Gap / Next Actions",
      key=f"{key_prefix}_regen",
      disabled=regen_disabled,
    ):
      generate = True

  if needs_regen and regen_reason:
    st.caption(regen_reason)

  session_key = f"{STATE_V8_EVIDENCE_GAP}_{case_id}"
  if generate:
    report, out_dir = build_and_export_evidence_aware_gap_next_actions(case_id, project_root=project_root)
    gap_df = _load_gap_csv(out_dir)
    summary_df = _load_summary_csv(out_dir)
    bundle = {
      "case_id": case_id,
      "report": report.to_dict(),
      "output_dir": str(out_dir),
      "gap_df": gap_df.to_dict(orient="records"),
      "summary_df": summary_df.to_dict(orient="records"),
      "gaps": [g.to_dict() for g in report.gaps],
      "summaries": [s.to_dict() for s in report.summaries],
      "source_claim_example_links_csv": report.source_claim_example_links_csv,
      "source_example_facts_csv": report.source_example_facts_csv,
      "primary_available": True,
    }
    st.session_state[session_key] = bundle
    st.success(f"Evidence-aware Gap を生成しました: {out_dir}")
  elif session_key not in st.session_state and latest_gap_dir and is_evidence_aware_gap_pack(latest_gap_dir):
    gap_df = _load_gap_csv(latest_gap_dir)
    summary_df = _load_summary_csv(latest_gap_dir)
    report = build_evidence_aware_gap_report(case_id, project_root=project_root)
    bundle = {
      "case_id": case_id,
      "report": report.to_dict(),
      "output_dir": str(latest_gap_dir),
      "gap_df": gap_df.to_dict(orient="records"),
      "summary_df": summary_df.to_dict(orient="records"),
      "gaps": [g.to_dict() for g in report.gaps],
      "summaries": [s.to_dict() for s in report.summaries],
      "source_claim_example_links_csv": report.source_claim_example_links_csv,
      "source_example_facts_csv": report.source_example_facts_csv,
      "primary_available": evidence_aware_gap_primary_available(case_id, project_root),
    }
    st.session_state[session_key] = bundle

  bundle = st.session_state.get(session_key)
  if not bundle:
    st.info("「Generate Gap / Next Actions from Claim-Example Evidence」を押してください。")
    return None

  gap_df = pd.DataFrame(bundle.get("gap_df") or [])
  summary_df = pd.DataFrame(bundle.get("summary_df") or [])
  out_dir = Path(str(bundle.get("output_dir", "")))

  _render_primary_intro(summary_df)
  _render_summary_cards(summary_df)
  if not summary_df.empty:
    st.dataframe(summary_df, width="stretch", hide_index=True)

  st.markdown("#### Claim-level gaps")
  _render_gap_table(gap_df)

  checklist = out_dir / "human_review_checklist.md"
  st.markdown("#### Human Review Checklist")
  if checklist.exists():
    st.markdown(checklist.read_text(encoding="utf-8"))
  else:
    st.caption("human_review_checklist.md は未生成です。")

  _render_top3_actions(case_id, project_root)

  st.markdown("#### Watch Profile / Digest / Artifact trace")
  with st.expander("定点観測の詳細（Watch Profile / Digest / Artifact trace）", expanded=False):
    watch_path = out_dir / "watch_profile_update_proposal.md"
    digest_path = out_dir / "digest_summary.md"
    if watch_path.exists():
      st.markdown("**Watch Profile update proposal**")
      st.markdown(watch_path.read_text(encoding="utf-8"))
    if digest_path.exists():
      st.markdown("**Digest summary**")
      st.markdown(digest_path.read_text(encoding="utf-8"))
    st.markdown("**Artifact trace**")
    st.caption(f"gap output: {out_dir}")
    if bundle.get("source_claim_example_links_csv"):
      st.caption(f"claim_example_links: {bundle['source_claim_example_links_csv']}")
    if bundle.get("source_example_facts_csv"):
      st.caption(f"example_facts: {bundle['source_example_facts_csv']}")

  _render_pipeline_status(case_id, project_root)
  _render_downloads(out_dir, gap_df, bundle)

  with st.expander("export dir（開発者向け）", expanded=False):
    st.caption(str(out_dir))

  bundle["primary_available"] = evidence_aware_gap_primary_available(case_id, project_root)
  return bundle
