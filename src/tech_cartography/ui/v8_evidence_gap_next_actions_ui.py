"""Evidence-aware Gap / Next Actions UI (Phase 27S.6)."""

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
  find_latest_evidence_aware_gap_dir,
  is_evidence_aware_gap_pack,
)
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_warning_box

STATE_V8_EVIDENCE_GAP = "v8_evidence_gap_next_actions"


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
  c1.metric("Review-ready claims", ready)
  c2.metric("OCR review needed", ocr)
  c3.metric("Property/table review needed", prop + table + process)
  c4.metric("Pubs w/o example facts", no_facts)


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


def render_evidence_aware_gap_section(
  case_id: str,
  project_root: Path,
  *,
  key_prefix: str = "v8_ev_gap",
  show_title: bool = True,
) -> dict[str, Any] | None:
  """Render Evidence-aware Gap / Next Actions block. Returns cached bundle dict."""
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
    bundle = {
      "report": report.to_dict(),
      "output_dir": str(out_dir),
      "gap_df": _load_gap_csv(out_dir).to_dict(orient="records"),
      "summary_df": _load_summary_csv(out_dir).to_dict(orient="records"),
    }
    st.session_state[session_key] = bundle
    st.success(f"Evidence-aware Gap を生成しました: {out_dir}")
  elif session_key not in st.session_state and latest_gap_dir and is_evidence_aware_gap_pack(latest_gap_dir):
    gap_df = _load_gap_csv(latest_gap_dir)
    summary_df = _load_summary_csv(latest_gap_dir)
    report = build_evidence_aware_gap_report(case_id, project_root=project_root)
    st.session_state[session_key] = {
      "report": report.to_dict(),
      "output_dir": str(latest_gap_dir),
      "gap_df": gap_df.to_dict(orient="records"),
      "summary_df": summary_df.to_dict(orient="records"),
    }

  bundle = st.session_state.get(session_key)
  if not bundle:
    st.info("「Generate Gap / Next Actions from Claim-Example Evidence」を押してください。")
    return None

  gap_df = pd.DataFrame(bundle.get("gap_df") or [])
  summary_df = pd.DataFrame(bundle.get("summary_df") or [])
  _render_summary_cards(summary_df)
  if not summary_df.empty:
    st.dataframe(summary_df, width="stretch", hide_index=True)

  st.markdown("#### Claim-level gaps")
  _render_gap_table(gap_df)

  out_dir = Path(str(bundle.get("output_dir", "")))
  checklist = out_dir / "human_review_checklist.md"
  if checklist.exists():
    with st.expander("human_review_checklist.md", expanded=False):
      st.markdown(checklist.read_text(encoding="utf-8"))

  with st.expander("出力パス（開発者向け）", expanded=False):
    st.caption(str(out_dir))

  return bundle
