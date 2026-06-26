"""v8 patent shortlist tab (Phase 27D)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from tech_cartography.runtime.v8_patent_shortlist_schema import V8PatentCandidate, V8PatentShortlist
from tech_cartography.services.v8_patent_shortlist import build_patent_shortlist
from tech_cartography.services.v8_patent_shortlist_export import (
  export_patent_shortlist,
  shortlist_to_csv_text,
  shortlist_to_markdown,
)
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_next_action_box
from tech_cartography.ui.v8_input_ui import get_v8_input_state
from tech_cartography.ui.v8_tab_config import STATE_V8_SELECTED_CASE, STATE_V8_SELECTED_PUBLICATION, V8_CASE_SAMPLES, V8_TAB_LABELS

STATE_V8_PATENT_SHORTLIST = "v8_patent_shortlist_cache"


def _case_options() -> list[tuple[str, str]]:
  return [("all", "All cases")] + [(s["case_id"], s["label"]) for s in V8_CASE_SAMPLES]


def _render_shortlist_table(shortlist: V8PatentShortlist) -> None:
  display_cols = [
    "rank", "publication_number", "title", "assignee_or_organization", "year",
    "total_score", "technical_axis_labels", "why_read",
    "expected_evidence_to_check", "next_verification_action", "human_review_required",
  ]
  rows = []
  for c in shortlist.patent_candidates:
    rows.append({
      "rank": c.rank,
      "publication_number": c.publication_number,
      "title": c.title,
      "assignee_or_organization": c.assignee_or_organization,
      "year": c.year,
      "total_score": c.total_score,
      "technical_axis_labels": ", ".join(c.technical_axis_labels),
      "why_read": c.why_read,
      "expected_evidence_to_check": c.expected_evidence_to_check,
      "next_verification_action": c.next_verification_action,
      "human_review_required": c.human_review_required,
    })
  st.dataframe(pd.DataFrame(rows, columns=display_cols), width="stretch", hide_index=True)


def _render_shortlist_detail(shortlist: V8PatentShortlist, *, key_prefix: str) -> None:
  if not shortlist.patent_candidates:
    return
  pick_labels = [f"#{c.rank} {c.publication_number}" for c in shortlist.patent_candidates]
  pick_idx = st.selectbox(
    "詳細",
    range(len(shortlist.patent_candidates)),
    format_func=lambda i: pick_labels[i],
    key=f"{key_prefix}_detail_pick",
  )
  detail = shortlist.patent_candidates[pick_idx]
  st.session_state[STATE_V8_SELECTED_PUBLICATION] = detail.publication_number
  st.json(detail.score_breakdown)
  st.markdown(f"**caution_flags:** {', '.join(detail.caution_flags)}")
  st.caption(f"url: {detail.url or '（なし）'}")
  st.caption(f"source_status: {detail.source_status} / evidence_role: {detail.evidence_role}")
  st.caption(f"next_phase: {detail.next_phase}")
  st.caption(
    f"claim text not loaded — 「{V8_TAB_LABELS['claim_map']}」で請求項本文を claims_input.csv または手動入力で投入してください。"
  )


def _render_downloads(
  shortlist: V8PatentShortlist,
  export_info: dict,
  *,
  key_prefix: str,
) -> None:
  case_id = shortlist.case_id
  st.download_button(
    "CSV",
    shortlist_to_csv_text(shortlist.patent_candidates).encode("utf-8"),
    f"patent_shortlist_{case_id}.csv",
    "text/csv",
    key=f"{key_prefix}_dl_csv",
  )
  st.download_button(
    "Markdown",
    shortlist_to_markdown(shortlist).encode("utf-8"),
    f"patent_shortlist_{case_id}.md",
    "text/markdown",
    key=f"{key_prefix}_dl_md",
  )
  xlsx_path = Path(str(export_info.get("xlsx_path", "")))
  if xlsx_path.exists():
    st.download_button(
      "Excel",
      xlsx_path.read_bytes(),
      xlsx_path.name,
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      key=f"{key_prefix}_dl_xlsx",
    )
  if export_info.get("excel_warning"):
    st.caption(str(export_info.get("excel_warning")))
  st.caption(f"export dir: {export_info.get('output_dir', '')}")


def render_v8_patent_shortlist_tab(*, project_root: Path | str) -> None:
  root = Path(project_root)
  state = get_v8_input_state()
  default_case = str(state.get("selected_case_id") or st.session_state.get(STATE_V8_SELECTED_CASE) or "").strip()

  st.markdown("### 読むべき特許 Top N")
  st.markdown(
    render_caution_box(
      "<strong>読む優先度の暫定スコア（heuristic / draft selection）</strong> です。"
      " 特許価値・権利価値・有効性・侵害リスクを意味しません。"
      " FTO、侵害、有効性判断、法的結論は行いません。"
      " claim text not loaded — 請求項・明細書は未読です。"
    ),
    unsafe_allow_html=True,
  )

  case_options = _case_options()
  case_ids = [cid for cid, _ in case_options]
  labels = {cid: label for cid, label in case_options}
  default_idx = case_ids.index(default_case) if default_case in case_ids else 0

  col1, col2, col3 = st.columns(3)
  with col1:
    selected_case = st.selectbox(
      "案件",
      options=case_ids,
      index=default_idx,
      format_func=lambda cid: labels[cid],
      key="v8_patent_shortlist_case",
    )
  with col2:
    top_n = st.selectbox("Top N", options=[3, 5, 10], index=1, key="v8_patent_shortlist_top_n")
  with col3:
    refresh = st.button("Generate / Refresh Patent Shortlist", key="v8_patent_shortlist_refresh", type="primary")

  if selected_case != "all":
    st.session_state[STATE_V8_SELECTED_CASE] = selected_case

  cache_key = f"{selected_case}:{top_n}"
  if refresh or st.session_state.get("v8_patent_shortlist_cache_key") != cache_key:
    if selected_case == "all":
      bundles: dict[str, dict] = {}
      for sample in V8_CASE_SAMPLES:
        cid = sample["case_id"]
        shortlist = build_patent_shortlist(case_id=cid, top_n=top_n, project_root=root)
        export_result = export_patent_shortlist(shortlist, project_root=root)
        bundles[cid] = {"shortlist": shortlist.to_dict(), "export": export_result.to_dict()}
      st.session_state[STATE_V8_PATENT_SHORTLIST] = {"mode": "all", "bundles": bundles, "top_n": top_n}
    else:
      shortlist = build_patent_shortlist(case_id=selected_case, top_n=top_n, project_root=root)
      export_result = export_patent_shortlist(shortlist, project_root=root)
      st.session_state[STATE_V8_PATENT_SHORTLIST] = {
        "mode": "single",
        "shortlist": shortlist.to_dict(),
        "export": export_result.to_dict(),
      }
    st.session_state["v8_patent_shortlist_cache_key"] = cache_key

  cached = st.session_state.get(STATE_V8_PATENT_SHORTLIST)
  if not cached:
    st.info("「Generate / Refresh Patent Shortlist」を押して Top N を生成してください。")
    st.markdown(
      render_next_action_box(f"先に「{V8_TAB_LABELS['sources']}」で patent source を確認してください。"),
      unsafe_allow_html=True,
    )
    return

  def _dict_to_shortlist(data: dict) -> V8PatentShortlist:
    return V8PatentShortlist(
      case_id=data["case_id"],
      case_name=data["case_name"],
      top_n=data["top_n"],
      count=data["count"],
      patent_candidates=[V8PatentCandidate.from_dict(c) for c in data["patent_candidates"]],
      excluded_sources=data.get("excluded_sources", []),
      warnings=data.get("warnings", []),
      generated_at=data["generated_at"],
    )

  if cached.get("mode") == "all":
    bundles = cached.get("bundles") or {}
    if not bundles:
      st.warning("案件データがありません。")
      return
    for sample in V8_CASE_SAMPLES:
      cid = sample["case_id"]
      bundle = bundles.get(cid)
      if not bundle:
        continue
      shortlist = _dict_to_shortlist(bundle["shortlist"])
      with st.expander(f"{sample['label']} — {shortlist.count}件", expanded=cid == case_ids[1]):
        if not shortlist.patent_candidates:
          st.warning("patent source が不足しています。")
          continue
        _render_shortlist_table(shortlist)
        _render_shortlist_detail(shortlist, key_prefix=f"v8_patent_{cid}")
        st.markdown("##### ダウンロード")
        _render_downloads(shortlist, bundle.get("export") or {}, key_prefix=f"v8_patent_{cid}")
  else:
    shortlist = _dict_to_shortlist(cached["shortlist"])
    export_info = cached.get("export") or {}
    if not shortlist.patent_candidates:
      st.warning("patent source が不足しています。Sources一覧で patent を追加してください。")
      return
    _render_shortlist_table(shortlist)
    st.markdown("#### 選択特許の詳細")
    _render_shortlist_detail(shortlist, key_prefix="v8_patent_single")
    st.markdown("#### ダウンロード")
    _render_downloads(shortlist, export_info, key_prefix="v8_patent_single")

  st.caption("Export Package への同梱は Phase27C 以降の拡張予定。現時点では patent_shortlist_* を個別ダウンロード。")
  st.markdown(
    render_next_action_box(
      f"Top候補の publication_number は Claim Map タブに引き継がれます。"
      f"「{V8_TAB_LABELS['claim_map']}」で請求項分解（Phase27E）へ進んでください。"
    ),
    unsafe_allow_html=True,
  )
