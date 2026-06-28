"""Google Patents links UI helpers (Phase 27S.0)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from tech_cartography.runtime.v8_google_patents_links_schema import (
  GOOGLE_PATENTS_SAFETY_NOTICES,
  PDF_DOWNLOAD_INSTRUCTION,
  GooglePatentsLink,
)
from tech_cartography.services.v8_google_patents_links import (
  build_top5_google_patents_links,
  export_google_patents_links,
)
from tech_cartography.services.v8_claim_example_binding import get_full_patent_document_pipeline_status


def _session_pdf_uploads() -> dict[str, str]:
  raw = st.session_state.get("v8_patent_pdf_uploads")
  return dict(raw) if isinstance(raw, dict) else {}


def render_google_patents_caution() -> None:
  st.caption(GOOGLE_PATENTS_SAFETY_NOTICES[0])
  st.caption(
    "PDF解析は「読むべき特許｜Top5」タブの Top5 Deep Dive｜公報PDF解析 で実行できます。"
  )


def render_google_patents_link_on_card(link: GooglePatentsLink) -> None:
  st.markdown(f"[Google Patentsで開く]({link.google_patents_url})")
  st.markdown("**PDF取得ガイド**")
  st.caption(PDF_DOWNLOAD_INSTRUCTION)
  st.caption(
    "PDF取得後、この画面内の Top5 Deep Dive｜公報PDF解析 で対象特許を選択し、PDFをアップロードしてください。"
  )
  st.caption(f"PDF取得状況: {link.pdf_upload_status}")


def render_top5_pdf_links_table(
  links: list[GooglePatentsLink],
  *,
  case_id: str = "",
  project_root: Path | None = None,
  key_prefix: str = "v8_gp",
) -> None:
  if not links:
    st.caption("Top5 未生成 — Generate Reading Priority を実行してください。")
    return
  st.markdown("#### Top5公報PDF取得リンク")
  render_google_patents_caution()
  rows = []
  for link in links:
    row = {
      "publication_number": link.publication_number,
      "title": (link.title or "—")[:80],
      "Google Patents": link.google_patents_url,
      "PDF取得状況": link.pdf_upload_status,
      "次の操作": link.next_action,
    }
    if case_id and project_root is not None:
      pipe = get_full_patent_document_pipeline_status(case_id, link.publication_number, project_root)
      row["pdf_uploaded"] = pipe["pdf_uploaded"]
      row["text_extracted"] = pipe["text_extracted"]
      row["sections_extracted"] = pipe.get("sections_extracted")
      row["has_examples"] = pipe.get("has_examples")
      row["example_facts_extracted"] = pipe.get("example_facts_extracted")
      row["claim_example_links_generated"] = pipe.get("claim_example_links_generated")
      row["fact_count"] = pipe.get("fact_count", 0)
      row["linked_claim_count"] = pipe.get("linked_claim_count", 0)
      row["unlinked_claim_count"] = pipe.get("unlinked_claim_count", 0)
      row["matched_user_keyword_count"] = pipe.get("matched_user_keyword_count", 0)
      row["needs_ocr"] = pipe["needs_ocr"]
      row["needs_human_review"] = pipe.get("facts_needs_human_review") or pipe.get("section_needs_human_review")
      row["next_action"] = pipe["next_action"]
    rows.append(row)
  st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
  for link in links:
    st.markdown(f"- [{link.publication_number} — Google Patentsで開く]({link.google_patents_url})")

  if st.button("Export Google Patents links (CSV/MD)", key=f"{key_prefix}_export"):
    export = export_google_patents_links(links)
    st.session_state[f"{key_prefix}_last_export"] = export.to_dict()
    st.success(f"Export 完了 — {export.output_dir}")

  cached = st.session_state.get(f"{key_prefix}_last_export")
  if isinstance(cached, dict):
    csv_path = Path(str(cached.get("csv_path", "")))
    md_path = Path(str(cached.get("md_path", "")))
    col1, col2 = st.columns(2)
    if csv_path.exists():
      col1.download_button(
        "google_patents_links.csv",
        csv_path.read_bytes(),
        csv_path.name,
        "text/csv",
        key=f"{key_prefix}_dl_csv",
      )
    if md_path.exists():
      col2.download_button(
        "google_patents_links.md",
        md_path.read_bytes(),
        md_path.name,
        "text/markdown",
        key=f"{key_prefix}_dl_md",
      )


def load_and_render_top5_pdf_links(
  case_id: str,
  project_root: Path,
  *,
  key_prefix: str = "v8_gp",
) -> list[GooglePatentsLink]:
  links = build_top5_google_patents_links(
    case_id, project_root, session_uploads=_session_pdf_uploads(),
  )
  render_top5_pdf_links_table(
    links, key_prefix=key_prefix, case_id=case_id, project_root=project_root,
  )
  return links
