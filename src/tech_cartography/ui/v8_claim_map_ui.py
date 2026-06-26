"""v8 Claim Map tab (Phase 27E)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from tech_cartography.runtime.v8_claim_map_schema import V8ClaimMap, V8ClaimRecord
from tech_cartography.services.v8_claim_map import build_claim_map
from tech_cartography.services.v8_claim_map_export import (
  claim_map_to_csv_text,
  claim_map_to_markdown,
  export_claim_map,
)
from tech_cartography.services.v8_patent_shortlist import build_patent_shortlist
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_next_action_box, render_warning_box
from tech_cartography.ui.v8_input_ui import get_v8_input_state
from tech_cartography.ui.v8_tab_config import (
  STATE_V8_SELECTED_CASE,
  STATE_V8_SELECTED_PUBLICATION,
  V8_CASE_SAMPLES,
  V8_TAB_LABELS,
)

STATE_V8_CLAIM_MAP = "v8_claim_map_cache"


def _case_options() -> list[tuple[str, str]]:
  return [("all", "All cases")] + [(s["case_id"], s["label"]) for s in V8_CASE_SAMPLES]


def _render_claim_table(records: list[V8ClaimRecord]) -> None:
  cols = [
    "publication_number", "claim_no", "claim_text_status", "primary_axis",
    "technical_axis_labels", "material_terms", "process_terms", "property_terms",
    "structure_terms", "application_terms", "evidence_needed", "next_evidence_check",
    "human_review_required",
  ]
  rows = []
  for rec in records:
    rows.append({
      "publication_number": rec.publication_number,
      "claim_no": rec.claim_no,
      "claim_text_status": rec.claim_text_status,
      "primary_axis": rec.primary_axis,
      "technical_axis_labels": ", ".join(rec.technical_axis_labels),
      "material_terms": ", ".join(rec.material_terms),
      "process_terms": ", ".join(rec.process_terms),
      "property_terms": ", ".join(rec.property_terms),
      "structure_terms": ", ".join(rec.structure_terms),
      "application_terms": ", ".join(rec.application_terms),
      "evidence_needed": ", ".join(rec.evidence_needed),
      "next_evidence_check": rec.next_evidence_check,
      "human_review_required": rec.human_review_required,
    })
  st.dataframe(pd.DataFrame(rows, columns=cols), width="stretch", hide_index=True)


def _render_claim_detail(records: list[V8ClaimRecord], *, key_prefix: str) -> None:
  if not records:
    return
  labels = [f"{r.publication_number} claim {r.claim_no}" for r in records]
  idx = st.selectbox("詳細", range(len(records)), format_func=lambda i: labels[i], key=f"{key_prefix}_detail")
  detail = records[idx]
  if detail.claim_text_status == "not_loaded":
    st.markdown(
      render_warning_box(
        "<strong>claim text not loaded</strong> — 請求項本文が未取得です。"
        " 原典公報から本文を投入するまで技術軸分類は行いません。"
      ),
      unsafe_allow_html=True,
    )
  st.text_area("claim_text", detail.claim_text, height=120, disabled=True, key=f"{key_prefix}_text")
  st.markdown(f"**caution_flags:** {', '.join(detail.caution_flags)}")
  st.caption(f"evidence_needed: {', '.join(detail.evidence_needed)}")
  st.caption(f"next_phase: {detail.next_phase}")


def render_v8_claim_map_tab(*, project_root: Path | str) -> None:
  root = Path(project_root)
  state = get_v8_input_state()
  default_case = str(state.get("selected_case_id") or st.session_state.get(STATE_V8_SELECTED_CASE) or "").strip()
  default_pub = str(st.session_state.get(STATE_V8_SELECTED_PUBLICATION) or "").strip()

  st.markdown("### Claim Map v1")
  st.markdown(
    render_caution_box(
      "<strong>Claim Map は技術整理の暫定分類（heuristic / draft）</strong> です。"
      " 権利範囲の解釈・FTO・侵害・有効性判断ではありません。"
      " claim text not loaded の請求項は分類しません。"
    ),
    unsafe_allow_html=True,
  )

  case_options = _case_options()
  case_ids = [c for c, _ in case_options]
  labels = {c: label for c, label in case_options}
  default_idx = case_ids.index(default_case) if default_case in case_ids else 0

  col1, col2 = st.columns(2)
  with col1:
    selected_case = st.selectbox(
      "案件",
      options=case_ids,
      index=default_idx,
      format_func=lambda cid: labels[cid],
      key="v8_claim_map_case",
    )
  if selected_case != "all":
    st.session_state[STATE_V8_SELECTED_CASE] = selected_case

  active_case = case_ids[1] if selected_case == "all" else selected_case
  shortlist = build_patent_shortlist(case_id=active_case, top_n=5, project_root=root)
  pub_options = ["（Shortlist 全件）"] + [p.publication_number for p in shortlist.patent_candidates]
  default_pub_idx = pub_options.index(default_pub) if default_pub in pub_options else 0
  with col2:
    selected_pub_label = st.selectbox(
      "特許（Patent Shortlist）",
      options=pub_options,
      index=default_pub_idx,
      key="v8_claim_map_pub",
    )
  publication_number = None if selected_pub_label == "（Shortlist 全件）" else selected_pub_label
  if publication_number:
    st.session_state[STATE_V8_SELECTED_PUBLICATION] = publication_number

  input_mode = st.radio(
    "claim入力方法",
    options=["claims_input.csv", "手動claim text貼り付け", "claim text未取得でMap作成"],
    horizontal=True,
    key="v8_claim_map_input_mode",
  )

  manual_rows: list[dict[str, str]] = []
  if input_mode == "手動claim text貼り付け":
    manual_pub = st.text_input("publication_number", value=publication_number or "", key="v8_claim_manual_pub")
    manual_claim_no = st.text_input("claim_no", value="1", key="v8_claim_manual_no")
    manual_title = st.text_input("patent_title（任意）", key="v8_claim_manual_title")
    manual_text = st.text_area("claim text", height=150, key="v8_claim_manual_text")
    if manual_pub.strip() and manual_text.strip():
      manual_rows.append({
        "publication_number": manual_pub.strip(),
        "claim_no": manual_claim_no.strip() or "1",
        "patent_title": manual_title.strip(),
        "claim_text": manual_text.strip(),
      })

  use_shortlist_only = input_mode == "claim text未取得でMap作成"
  refresh = st.button("Generate / Refresh Claim Map", key="v8_claim_map_refresh", type="primary")

  cache_key = f"{selected_case}:{publication_number}:{input_mode}:{bool(manual_rows)}"
  if refresh or st.session_state.get("v8_claim_map_cache_key") != cache_key:
    if selected_case == "all":
      bundles: dict[str, dict] = {}
      for sample in V8_CASE_SAMPLES:
        cid = sample["case_id"]
        claim_map = build_claim_map(
          case_id=cid,
          publication_number=None,
          project_root=root,
          manual_rows=manual_rows or None,
          use_shortlist_only=use_shortlist_only,
        )
        export_result = export_claim_map(claim_map, project_root=root)
        bundles[cid] = {"claim_map": claim_map.to_dict(), "export": export_result.to_dict()}
      st.session_state[STATE_V8_CLAIM_MAP] = {"mode": "all", "bundles": bundles}
    else:
      claim_map = build_claim_map(
        case_id=selected_case,
        publication_number=publication_number,
        project_root=root,
        manual_rows=manual_rows or None,
        use_shortlist_only=use_shortlist_only,
      )
      export_result = export_claim_map(claim_map, project_root=root)
      st.session_state[STATE_V8_CLAIM_MAP] = {
        "mode": "single",
        "claim_map": claim_map.to_dict(),
        "export": export_result.to_dict(),
      }
    st.session_state["v8_claim_map_cache_key"] = cache_key

  cached = st.session_state.get(STATE_V8_CLAIM_MAP)
  if not cached:
    st.info("「Generate / Refresh Claim Map」を押してください。")
    st.markdown(
      render_next_action_box(
        f"先に「{V8_TAB_LABELS['patent_shortlist']}」で Top 特許を確認し、"
        f" cases/<case_id>/claims_input.csv に publication_number を登録してください。"
      ),
      unsafe_allow_html=True,
    )
    return

  def _dict_to_claim_map(data: dict) -> V8ClaimMap:
    return V8ClaimMap(
      claim_map_id=data["claim_map_id"],
      case_id=data["case_id"],
      publication_number=data["publication_number"],
      generated_at=data["generated_at"],
      records=[V8ClaimRecord.from_dict(r) for r in data["records"]],
      claim_count=data["claim_count"],
      loaded_claim_count=data["loaded_claim_count"],
      not_loaded_claim_count=data["not_loaded_claim_count"],
      count_by_axis=data.get("count_by_axis", {}),
      count_by_evidence_needed=data.get("count_by_evidence_needed", {}),
      warnings=data.get("warnings", []),
      source_artifact_paths=data.get("source_artifact_paths", []),
      next_actions=data.get("next_actions", []),
    )

  if cached.get("mode") == "all":
    bundles = cached.get("bundles") or {}
    for sample in V8_CASE_SAMPLES:
      cid = sample["case_id"]
      bundle = bundles.get(cid)
      if not bundle:
        continue
      claim_map = _dict_to_claim_map(bundle["claim_map"])
      export_info = bundle.get("export") or {}
      with st.expander(f"{sample['label']} — {claim_map.claim_count} claims", expanded=cid == active_case):
        m1, m2, m3 = st.columns(3)
        m1.metric("claims", claim_map.claim_count)
        m2.metric("loaded", claim_map.loaded_claim_count)
        m3.metric("not_loaded", claim_map.not_loaded_claim_count)
        _render_claim_table(claim_map.records)
        _render_claim_detail(claim_map.records, key_prefix=f"v8_claim_{cid}")
        st.download_button(
          "CSV",
          claim_map_to_csv_text(claim_map.records).encode("utf-8"),
          f"claim_map_{cid}.csv",
          "text/csv",
          key=f"v8_claim_dl_csv_{cid}",
        )
        st.download_button(
          "Markdown",
          claim_map_to_markdown(claim_map).encode("utf-8"),
          f"claim_map_{cid}.md",
          "text/markdown",
          key=f"v8_claim_dl_md_{cid}",
        )
        xlsx_path = Path(str(export_info.get("xlsx_path", "")))
        if xlsx_path.exists():
          st.download_button(
            "Excel",
            xlsx_path.read_bytes(),
            xlsx_path.name,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"v8_claim_dl_xlsx_{cid}",
          )
    st.markdown(
      render_next_action_box(
        f"「{V8_TAB_LABELS['patent_shortlist']}」に戻るか、"
        f"「{V8_TAB_LABELS['evidence_map']}」で Evidence 照合（Phase27F）へ進んでください。"
      ),
      unsafe_allow_html=True,
    )
    return

  claim_map = _dict_to_claim_map(cached["claim_map"])
  export_info = cached.get("export") or {}

  m1, m2, m3 = st.columns(3)
  m1.metric("claims", claim_map.claim_count)
  m2.metric("loaded", claim_map.loaded_claim_count)
  m3.metric("not_loaded", claim_map.not_loaded_claim_count)

  if claim_map.not_loaded_claim_count > 0:
    st.markdown(
      render_warning_box(
        f"{claim_map.not_loaded_claim_count} 件は claim text not loaded。"
        " 原典公報から請求項を投入してください。"
      ),
      unsafe_allow_html=True,
    )

  _render_claim_table(claim_map.records)
  st.markdown("#### 選択 claim の詳細")
  _render_claim_detail(claim_map.records, key_prefix="v8_claim_map")

  st.markdown("#### ダウンロード")
  st.download_button(
    "CSV",
    claim_map_to_csv_text(claim_map.records).encode("utf-8"),
    f"claim_map_{selected_case}.csv",
    "text/csv",
    key="v8_claim_dl_csv",
  )
  st.download_button(
    "Markdown",
    claim_map_to_markdown(claim_map).encode("utf-8"),
    f"claim_map_{selected_case}.md",
    "text/markdown",
    key="v8_claim_dl_md",
  )
  xlsx_path = Path(str(export_info.get("xlsx_path", "")))
  if xlsx_path.exists():
    st.download_button(
      "Excel",
      xlsx_path.read_bytes(),
      xlsx_path.name,
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      key="v8_claim_dl_xlsx",
    )
  if export_info.get("excel_warning"):
    st.caption(str(export_info.get("excel_warning")))
  st.caption(f"export dir: {export_info.get('output_dir', '')}")

  st.markdown(
    render_next_action_box(
      f"「{V8_TAB_LABELS['patent_shortlist']}」に戻るか、"
      f"「{V8_TAB_LABELS['evidence_map']}」で Evidence 照合（Phase27F）へ進んでください。"
    ),
    unsafe_allow_html=True,
  )


def pd_columns_markdown(columns: tuple[str, ...]) -> str:
  return "\n".join(f"- `{col}`" for col in columns)
