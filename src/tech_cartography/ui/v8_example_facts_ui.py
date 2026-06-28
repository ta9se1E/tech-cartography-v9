"""Example facts extraction UI (Phase 27S.3)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from tech_cartography.runtime.v8_example_facts_schema import EXAMPLE_FACTS_NOTICES
from tech_cartography.services.v8_extraction_vocabulary import load_extraction_vocabulary
from tech_cartography.services.v8_llm_provider_gemini import ENABLE_GEMINI_EXAMPLE_FACTS_ENV
from tech_cartography.services.v8_gemini_example_facts import (
  export_gemini_prompts_only,
  extract_example_facts_from_sections,
  find_latest_example_facts_dir,
  find_latest_patent_sections_output,
  load_example_facts_summary_from_dir,
  load_target_sections,
  write_example_facts_outputs,
)
from tech_cartography.services.v8_claim_example_binding import get_full_patent_document_pipeline_status
from tech_cartography.services.v8_large_candidate_shortlist import load_top5_publications
from tech_cartography.services.v8_llm_provider_gemini import (
  gemini_availability_message,
  is_gemini_example_facts_enabled,
)
from tech_cartography.ui.v8_judge_mode_copy import EXAMPLE_FACTS_EXTRACT_HELP


def _session_key(case_id: str) -> str:
  return f"v8_example_facts_{case_id}"


def render_example_facts_caution() -> None:
  for notice in EXAMPLE_FACTS_NOTICES:
    st.caption(notice)


def render_gemini_example_facts_section(
  case_id: str,
  project_root: Path,
  *,
  key_prefix: str = "v8_efacts",
) -> None:
  st.markdown("#### Gemini実施例ファクト抽出")
  st.caption(EXAMPLE_FACTS_EXTRACT_HELP)
  render_example_facts_caution()

  output_root = project_root / "outputs"
  sections_dir = find_latest_patent_sections_output(case_id, output_root)
  sections_csv = (sections_dir / "publication_fulltext_sections.csv") if sections_dir else None
  latest_facts_dir = find_latest_example_facts_dir(case_id, project_root)
  facts_summary = load_example_facts_summary_from_dir(latest_facts_dir) if latest_facts_dir else {}
  vocabulary = load_extraction_vocabulary(case_id, project_root)
  vocab_counts = vocabulary.keyword_counts()

  if sections_dir:
    st.caption(f"最新セクション抽出: {sections_dir}")
  else:
    st.caption("セクション抽出結果がありません — 先に Extract sections を実行してください。")

  target_count = len(load_target_sections(sections_csv)) if sections_csv and sections_csv.exists() else 0
  c1, c2, c3, c4 = st.columns(4)
  c1.metric("対象section", target_count)
  c2.metric("語彙(material)", vocab_counts["material"])
  c3.metric("語彙(process)", vocab_counts["process"])
  c4.metric("Gemini", "ON" if is_gemini_example_facts_enabled() else "OFF")
  st.caption(f"{ENABLE_GEMINI_EXAMPLE_FACTS_ENV}={is_gemini_example_facts_enabled()} — {gemini_availability_message()}")

  top5 = load_top5_publications(case_id, project_root)
  rows = []
  for pub in top5:
    pipe = get_full_patent_document_pipeline_status(case_id, pub, project_root)
    row = facts_summary.get(pub, {})
    rows.append({
      "publication_number": pub,
      "examples_detected": pipe.get("has_examples"),
      "fact_count": row.get("fact_count", pipe.get("fact_count", 0)),
      "property_facts": row.get("property_fact_count", 0),
      "process_facts": row.get("process_condition_fact_count", 0),
      "matched_keywords": row.get("matched_user_keyword_count", 0),
      "needs_human_review": row.get("needs_human_review", True),
    })
  if rows:
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

  disabled = not (sections_csv and sections_csv.exists())
  col1, col2 = st.columns(2)
  with col1:
    if st.button(
      "Extract example facts with Gemini",
      key=f"{key_prefix}_extract",
      type="primary",
      disabled=disabled or not is_gemini_example_facts_enabled(),
    ):
      results, prompts, vocab = extract_example_facts_from_sections(
        case_id, sections_csv, output_root, project_root, use_gemini=True,
      )
      out_dir = write_example_facts_outputs(case_id, results, output_root, vocab, prompts)
      st.session_state[_session_key(case_id)] = {"output_dir": str(out_dir)}
      st.success(f"抽出完了 — {out_dir}")
  with col2:
    if st.button("Export Gemini prompts", key=f"{key_prefix}_prompts", disabled=disabled):
      out_dir = export_gemini_prompts_only(case_id, sections_csv, output_root, project_root)
      st.session_state[_session_key(case_id)] = {"output_dir": str(out_dir)}
      st.info(f"プロンプト出力 — {out_dir}")

  cached = st.session_state.get(_session_key(case_id))
  export_dir = Path(str(cached.get("output_dir", ""))) if cached else latest_facts_dir
  if export_dir and export_dir.exists():
    st.caption(f"出力先: {export_dir}")
    preview_csv = export_dir / "example_facts.csv"
    if preview_csv.exists():
      preview_df = pd.read_csv(preview_csv).head(10)
      if not preview_df.empty:
        st.markdown("**example_facts preview (top 10)**")
        st.dataframe(
          preview_df[["fact_type", "evidence_text", "matched_user_keywords", "needs_human_review"]],
          width="stretch",
          hide_index=True,
        )
    files = [
      "example_facts.csv", "example_facts.json", "example_facts.md",
      "example_facts_summary.csv", "example_facts_summary.md",
      "gemini_prompts.md", "extraction_vocabulary.json",
    ]
    cols = st.columns(2)
    for idx, name in enumerate(files):
      path = export_dir / name
      if path.exists():
        cols[idx % 2].download_button(name, path.read_bytes(), name, key=f"{key_prefix}_dl_{name}")

