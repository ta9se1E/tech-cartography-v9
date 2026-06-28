"""Claim-example binding UI (Phase 27S.4 / 27S.5.4)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from tech_cartography.runtime.v8_claim_example_binding_schema import CLAIM_EXAMPLE_BINDING_NOTICES
from tech_cartography.services.v8_claim_example_binding import (
  bind_claims_to_example_facts,
  find_latest_claim_example_links_dir,
  find_latest_example_facts_output,
  get_full_patent_document_pipeline_status,
  load_binding_summary_from_dir,
  load_claims_input,
  should_rerun_claim_example_binding,
  write_claim_example_binding_outputs,
)
from tech_cartography.services.v8_large_candidate_shortlist import load_top5_publications
from tech_cartography.services.v8_top5_pdf_pipeline_status import build_top5_pdf_pipeline_status
from tech_cartography.services.v8_evidence_gap_next_actions import evidence_aware_gap_primary_available
from tech_cartography.ui.v8_judge_mode_copy import CLAIM_EXAMPLE_BINDING_HELP
from tech_cartography.ui.v8_tab_config import V8_TAB_LABELS

BINDING_DETAIL_WARNING = (
  "Claim-Example対応は候補です。OCR由来の数値・単位・実施例番号は必ず原文確認してください。"
)


def _session_key(case_id: str) -> str:
  return f"v8_claim_example_binding_{case_id}"


def render_claim_example_binding_section(
  case_id: str,
  project_root: Path,
  *,
  key_prefix: str = "v8_cebind",
) -> None:
  st.markdown("#### Claim-Example対応候補")
  st.caption(CLAIM_EXAMPLE_BINDING_HELP)
  for notice in CLAIM_EXAMPLE_BINDING_NOTICES:
    st.caption(notice)
  st.caption(BINDING_DETAIL_WARNING)

  output_root = project_root / "outputs"
  facts_dir = find_latest_example_facts_output(case_id, output_root)
  facts_csv = (facts_dir / "example_facts.csv") if facts_dir else None
  latest_bind_dir = find_latest_claim_example_links_dir(case_id, project_root)
  bind_summary = load_binding_summary_from_dir(latest_bind_dir) if latest_bind_dir else {}
  needs_rerun, latest_facts_csv, latest_bind_path = should_rerun_claim_example_binding(case_id, project_root)

  claims = load_claims_input(case_id, project_root)
  st.caption(f"claims_input.csv: {len(claims)} 件（本文投入済み）")
  if facts_dir:
    st.caption(f"最新 example_facts: {facts_dir}")
  else:
    st.caption("example_facts.csv がありません — 先に Gemini実施例ファクト抽出を実行してください。")

  top5 = load_top5_publications(case_id, project_root)
  rows = []
  for pub in top5:
    pipe = get_full_patent_document_pipeline_status(case_id, pub, project_root)
    row = bind_summary.get(pub, {})
    rows.append({
      "publication_number": pub,
      "fact_count": pipe.get("fact_count", 0),
      "linked_claim_count": row.get("linked_claim_count", pipe.get("linked_claim_count", 0)),
      "linked_example_count": row.get("linked_example_count", 0),
      "linked_fact_count": row.get("linked_fact_count", 0),
      "mixed_support": row.get("mixed_support_count", 0),
      "unlinked_claim_count": row.get("unlinked_claim_count", pipe.get("unlinked_claim_count", 0)),
      "claim_example_generated": pipe.get("claim_example_links_generated"),
    })
  if rows:
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

  disabled = not (facts_csv and facts_csv.exists()) or not claims
  col1, col2 = st.columns(2)
  with col1:
    if st.button("Bind claim to example facts", key=f"{key_prefix}_bind", type="primary", disabled=disabled):
      results = bind_claims_to_example_facts(case_id, project_root, output_root)
      out_dir = write_claim_example_binding_outputs(case_id, results, output_root)
      st.session_state[_session_key(case_id)] = {"output_dir": str(out_dir)}
      st.success(f"対応候補生成完了 — {out_dir}")
      st.rerun()
  with col2:
    if needs_rerun and st.button(
      "Re-run claim-example binding from latest example facts",
      key=f"{key_prefix}_rerun",
      disabled=disabled,
    ):
      results = bind_claims_to_example_facts(case_id, project_root, output_root)
      out_dir = write_claim_example_binding_outputs(case_id, results, output_root)
      st.session_state[_session_key(case_id)] = {"output_dir": str(out_dir)}
      st.success(f"最新 example_facts から再生成 — {out_dir}")
      st.rerun()
  if needs_rerun:
    st.info("最新 example_facts が binding 出力より新しいため、再実行を推奨します。")

  cached = st.session_state.get(_session_key(case_id))
  export_dir = Path(str(cached.get("output_dir", ""))) if cached else latest_bind_dir
  if export_dir and export_dir.exists():
    st.caption(f"出力先: {export_dir}")
    preview_csv = export_dir / "claim_example_links.csv"
    if preview_csv.exists():
      preview_df = pd.read_csv(preview_csv)
      if not preview_df.empty:
        st.markdown("**Claim-Example Binding Summary**")
        summary_csv = export_dir / "claim_example_binding_summary.csv"
        if summary_csv.exists():
          st.dataframe(pd.read_csv(summary_csv), width="stretch", hide_index=True)
        detail_cols = [
          c for c in (
            "claim_no", "example_id", "example_label", "support_level", "support_type",
            "matched_fact_types", "matched_elements", "matched_fact_count",
            "top_evidence_snippets", "needs_human_review",
          )
          if c in preview_df.columns
        ]
        st.markdown("**Claimごとの詳細**")
        st.dataframe(preview_df[detail_cols].head(20), width="stretch", hide_index=True)
        with st.expander("Evidence / reason 詳細", expanded=False):
          for _, row in preview_df.head(10).iterrows():
            st.markdown(f"**Claim {row.get('claim_no')} — {row.get('example_id') or row.get('example_label') or '—'}**")
            st.caption(f"support: {row.get('support_type')} / {row.get('support_level')}")
            st.caption(f"matched_fact_types: {row.get('matched_fact_types', '')}")
            st.caption(f"reason: {str(row.get('reason', ''))[:500]}")
            for label, col in (
              ("process", "process_evidence_texts"),
              ("property", "property_evidence_texts"),
              ("structure", "structure_evidence_texts"),
              ("table", "table_evidence_texts"),
            ):
              if col in row and pd.notna(row[col]) and str(row[col]).strip():
                st.caption(f"{label}: {str(row[col])[:300]}")
    files = [
      "claim_example_links.csv", "claim_example_links.json", "claim_example_links.md",
      "claim_example_binding_summary.csv", "claim_example_binding_summary.md",
      "claim_example_review_prompts.md",
    ]
    cols = st.columns(2)
    for idx, name in enumerate(files):
      path = export_dir / name
      if path.exists():
        cols[idx % 2].download_button(name, path.read_bytes(), name, key=f"{key_prefix}_dl_{name}")


def render_gap_document_pipeline_status(
  case_id: str,
  project_root: Path,
  publication_numbers: list[str] | None = None,
) -> None:
  pubs = publication_numbers or load_top5_publications(case_id, project_root)
  if not pubs:
    return

  output_root = project_root / "outputs"
  statuses = build_top5_pdf_pipeline_status(case_id, project_root, output_root)
  if publication_numbers:
    pub_set = set(publication_numbers)
    statuses = [s for s in statuses if s.publication_number in pub_set]

  st.markdown("**Top5公報PDF — 解析状況（次アクション）**")
  st.caption(
    f"操作本体は「{V8_TAB_LABELS['patent_shortlist']}」タブの Top5 Deep Dive｜公報PDF解析 で実行します。"
  )
  evidence_primary = evidence_aware_gap_primary_available(case_id, project_root)
  for s in statuses:
    status_label = s.pipeline_status_label or "—"
    st.caption(f"- **{s.publication_number}** [{status_label}]: {s.next_action}")
    if s.pipeline_status_details:
      st.caption(f"  details: {s.pipeline_status_details}")
    if s.needs_ocr and not s.vision_ocr_text_extracted and not s.evidence_ready_for_review:
      st.caption(
        "  PDFはアップロード済みですが、通常のPDF本文抽出では文字量が不足しています。"
        " Top5 Deep DiveでGoogle Vision OCRを実行してください。"
      )
    elif s.vision_ocr_text_extracted and not s.sections_extracted:
      st.caption("  OCR本文が取得済みです。次にTop5 Deep Diveでセクション抽出を実行してください。")
  if evidence_primary:
    st.caption(
      "Claim-Example evidence-aware Gap generated — human review checklist available"
    )
  elif any(s.claim_example_links_generated for s in statuses):
    st.caption(
      "claim-example対応候補あり — Gap / Next Actions タブで Evidence-aware Gap を生成してください"
    )
  st.caption("対応付けは候補です。Evidenceは裏取り候補であり、証明ではありません。")
