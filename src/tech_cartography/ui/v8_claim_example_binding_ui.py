"""Claim-example binding UI (Phase 27S.4)."""

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
  write_claim_example_binding_outputs,
)
from tech_cartography.services.v8_large_candidate_shortlist import load_top5_publications
from tech_cartography.ui.v8_judge_mode_copy import CLAIM_EXAMPLE_BINDING_HELP


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

  output_root = project_root / "outputs"
  facts_dir = find_latest_example_facts_output(case_id, output_root)
  facts_csv = (facts_dir / "example_facts.csv") if facts_dir else None
  latest_bind_dir = find_latest_claim_example_links_dir(case_id, project_root)
  bind_summary = load_binding_summary_from_dir(latest_bind_dir) if latest_bind_dir else {}

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
      "unlinked_claim_count": row.get("unlinked_claim_count", pipe.get("unlinked_claim_count", 0)),
      "strong_candidate": row.get("strong_candidate_count", 0),
      "claim_example_generated": pipe.get("claim_example_links_generated"),
    })
  if rows:
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

  disabled = not (facts_csv and facts_csv.exists()) or not claims
  if st.button("Bind claim to example facts", key=f"{key_prefix}_bind", type="primary", disabled=disabled):
    results = bind_claims_to_example_facts(case_id, project_root, output_root)
    out_dir = write_claim_example_binding_outputs(case_id, results, output_root)
    st.session_state[_session_key(case_id)] = {"output_dir": str(out_dir)}
    st.success(f"対応候補生成完了 — {out_dir}")

  cached = st.session_state.get(_session_key(case_id))
  export_dir = Path(str(cached.get("output_dir", ""))) if cached else latest_bind_dir
  if export_dir and export_dir.exists():
    st.caption(f"出力先: {export_dir}")
    preview_csv = export_dir / "claim_example_links.csv"
    if preview_csv.exists():
      preview_df = pd.read_csv(preview_csv).head(10)
      if not preview_df.empty:
        st.markdown("**claim_example_links preview (top 10)**")
        st.dataframe(
          preview_df[[
            "publication_number", "claim_no", "support_type", "support_level",
            "matched_elements", "missing_elements", "needs_human_review",
          ]],
          width="stretch",
          hide_index=True,
        )
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

  st.markdown("**Top5公報PDF — 解析パイプライン状況**")
  for pub in pubs:
    pipe = get_full_patent_document_pipeline_status(case_id, pub, project_root)
    if not pipe["pdf_uploaded"]:
      line = f"- **{pub}**: PDF未アップロード — PDF取得が必要"
    elif not pipe["text_extracted"]:
      line = f"- **{pub}**: PDF本文未抽出 — Extract PDF text が必要"
    elif not pipe.get("sections_extracted"):
      line = f"- **{pub}**: セクション未抽出 — Extract sections が必要"
    elif pipe.get("has_examples") and not pipe.get("example_facts_extracted"):
      line = f"- **{pub}**: Example facts未抽出 — Extract example facts が必要"
    elif pipe.get("example_facts_extracted") and not pipe.get("claim_example_links_generated"):
      line = f"- **{pub}**: Claim-example未対応 — Claim-Example対応候補の生成が必要"
    elif pipe.get("claim_example_links_generated"):
      line = f"- **{pub}**: Claim-example対応候補あり — 次PhaseでGapロジック更新へ"
    elif pipe.get("facts_needs_human_review") or pipe.get("section_needs_human_review"):
      line = f"- **{pub}**: needs_human_review=True — 抽出結果の人手確認が必要"
    else:
      line = f"- **{pub}**: パイプライン途中 — 上記手順を確認してください"
    st.markdown(line)

  st.caption("対応付けは候補です。Gapロジックへの反映は次Phaseで行います。")
