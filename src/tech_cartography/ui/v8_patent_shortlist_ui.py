"""v8 patent shortlist tab (Phase 27D)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from tech_cartography.runtime.v8_patent_shortlist_schema import V8PatentCandidate, V8PatentShortlist
from tech_cartography.services.v8_large_candidate_shortlist import (
  build_staged_shortlist,
  find_latest_large_shortlist_dir,
  load_large_candidates_csv,
)
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


STATE_V8_PATENT_SHORTLIST = "v8_patent_shortlist_cache"
STATE_V8_LARGE_SHORTLIST = "v8_large_shortlist_pack"


def _render_large_candidate_table(records: list, *, title: str) -> None:
  st.markdown(f"#### {title}")
  if not records:
    st.caption("（なし）")
    return
  cols = [
    "rank", "publication_number", "title", "organization", "year", "heuristic_score",
    "score_reason", "matched_keywords", "positive_reasons", "negative_reasons",
    "stage_label", "ranking_policy", "next_verification_action",
  ]
  rows = []
  for r in records:
    rows.append({
      "rank": r.rank,
      "publication_number": r.publication_number,
      "title": (r.title or "")[:80],
      "organization": r.organization or r.assignee,
      "year": r.year,
      "heuristic_score": r.heuristic_score,
      "score_reason": r.score_reason,
      "matched_keywords": ", ".join(r.matched_keywords[:5]),
      "positive_reasons": ", ".join(r.positive_reasons[:3]),
      "negative_reasons": ", ".join(r.negative_reasons[:3]),
      "stage_label": r.stage_label,
      "ranking_policy": (r.ranking_policy or "")[:40],
      "next_verification_action": r.next_verification_action,
    })
  st.dataframe(pd.DataFrame(rows, columns=cols), width="stretch", hide_index=True)


def _render_large_candidate_mode(*, root: Path, selected_case: str) -> None:
  st.markdown("#### Large Candidate mode (Phase27J.0 / 27J.1)")
  st.caption(
    "1000件母集団 → Top100 → Top20 → Top5。"
    " score は読む優先度の暫定値であり、技術的正しさ・特許価値・法的価値ではありません。"
    " Claim Map / Evidence Map は Top5 のみ深掘り。"
  )
  b1, b2, b3 = st.columns(3)
  with b1:
    gen100 = st.button("Generate Top100", key="v8_lc_top100")
  with b2:
    gen20 = st.button("Generate Top20", key="v8_lc_top20")
  with b3:
    gen5 = st.button("Generate Top5", key="v8_lc_top5", type="primary")
  if gen100 or gen20 or gen5 or st.session_state.get("v8_large_shortlist_force"):
    st.session_state.pop("v8_large_shortlist_force", None)
    pack = build_staged_shortlist(selected_case, project_root=root)
    st.session_state[STATE_V8_LARGE_SHORTLIST] = pack.to_dict()

  cached = st.session_state.get(STATE_V8_LARGE_SHORTLIST)
  latest = find_latest_large_shortlist_dir(selected_case, root)
  manifest = {}
  if latest and (latest / "large_candidate_shortlist_manifest.json").exists():
    import json as _json
    manifest = _json.loads((latest / "large_candidate_shortlist_manifest.json").read_text(encoding="utf-8"))

  triage_engine = manifest.get("triage_engine") or (cached or {}).get("selection", {}).get("triage_engine", "—")
  ranking_policy = manifest.get("ranking_policy") or (cached or {}).get("selection", {}).get("ranking_policy", "—")
  st.markdown(f"**Ranking Policy:** `{ranking_policy}`")
  st.markdown(f"**Triage engine:** `{triage_engine}`")

  if isinstance(cached, dict) and cached.get("case_id") == selected_case:
    sel = cached.get("selection") or {}
    funnel_cols = st.columns(6)
    labels = [
      ("Imported", sel.get("population_count", 0)),
      ("Deduped", sel.get("deduped_count", 0)),
      ("Scored", sel.get("scored_count", 0)),
      ("Top100", sel.get("top100_count", 0)),
      ("Top20", sel.get("top20_count", 0)),
      ("Top5", sel.get("top5_count", 0)),
    ]
    for col, (label, count) in zip(funnel_cols, labels):
      col.metric(label, count)

    if latest:
      top100 = load_large_candidates_csv(latest / "large_candidate_top100.csv")
      top20 = load_large_candidates_csv(latest / "large_candidate_top20.csv")
      top5 = load_large_candidates_csv(latest / "large_candidate_top5.csv")

      with st.expander("スコアリング方針", expanded=False):
        st.markdown(
          "- **patent_triage**: include_terms +2/term, target_companies +3, US +1, pub/title/abstract +1, exclude -5/term\n"
          "- **fallback**: Phase27J.0 keyword heuristic\n"
          "- いずれも読む優先度のみ。FTO/侵害/有効性判断ではありません。"
        )
        st.caption(f"ranking_policy: {ranking_policy}")

      if top5:
        st.markdown("#### Top5 Deep Dive カード")
        for rec in top5:
          with st.container(border=True):
            st.markdown(f"**{rec.rank}. {rec.publication_number}** — {rec.title[:80]}")
            st.caption(f"{rec.organization or rec.assignee} / {rec.year} / score={rec.heuristic_score}")
            st.markdown(f"**why_selected:** {rec.why_selected or '—'}")
            if rec.positive_reasons:
              st.markdown(f"**positive_reasons:** {', '.join(rec.positive_reasons[:5])}")
            if rec.negative_reasons:
              st.markdown(f"**negative_reasons:** {', '.join(rec.negative_reasons[:3])}")
            st.caption(rec.next_verification_action)

      with st.expander("なぜTop5に残ったか", expanded=False):
        for rec in top5:
          st.markdown(f"- **{rec.publication_number}**: {rec.why_selected or rec.score_reason}")

      with st.expander("Top20から落ちた候補の要約", expanded=False):
        top5_ids = {r.candidate_id for r in top5}
        dropped = [r for r in top20 if r.candidate_id not in top5_ids]
        if dropped:
          for rec in dropped[:10]:
            st.markdown(
              f"- **{rec.publication_number}** (score={rec.heuristic_score}): "
              f"Top5より include term 一致数が少ない、またはスコアが低いため除外"
            )
        else:
          st.caption("（Top20件以下のため該当なし）")

      dropped_md = latest / "dropped_candidate_summary.md"
      if dropped_md.exists():
        st.caption("詳細: dropped_candidate_summary.md を Export タブからダウンロード")

      st.markdown("#### Top100 / Top20 テーブル")
      score_min, score_max = st.slider(
        "score range",
        0.0,
        20.0,
        (0.0, 20.0),
        key="v8_lc_score_range",
      )
      kw_filter = st.text_input("matched keyword", key="v8_lc_kw_filter")
      org_filter = st.text_input("organization / assignee", key="v8_lc_org_filter")
      year_filter = st.text_input("year", key="v8_lc_year_filter")
      country_filter = st.text_input("country", key="v8_lc_country_filter")

      def _filter_records(records: list) -> list:
        out = []
        for r in records:
          if r.heuristic_score < score_min or r.heuristic_score > score_max:
            continue
          if kw_filter and kw_filter.lower() not in " ".join(r.matched_keywords).lower():
            continue
          org = f"{r.organization} {r.assignee}".lower()
          if org_filter and org_filter.lower() not in org:
            continue
          if year_filter and year_filter not in str(r.year):
            continue
          if country_filter and country_filter.upper() not in str(r.country_code).upper():
            continue
          out.append(r)
        return out

      _render_large_candidate_table(_filter_records(top100), title="Top100")
      _render_large_candidate_table(_filter_records(top20), title="Top20")

      if top5:
        pick = st.selectbox(
          "Claim Map へ進む特許（Top5のみ）",
          [r.publication_number for r in top5 if r.publication_number],
          key="v8_lc_top5_pick",
        )
        if pick:
          st.session_state[STATE_V8_SELECTED_PUBLICATION] = pick
          st.session_state[STATE_V8_SELECTED_CASE] = selected_case
          st.caption(f"selected_publication_number={pick}")
  else:
    st.info("Large Candidate を取り込み後、Generate Top5 を押してください。")


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

  shortlist_mode = st.radio(
    "Shortlist モード",
    options=["small demo (Top N)", "large candidate staged"],
    horizontal=True,
    key="v8_patent_shortlist_mode",
  )
  if shortlist_mode == "large candidate staged" and selected_case != "all":
    _render_large_candidate_mode(root=root, selected_case=selected_case)
    st.markdown(
      render_next_action_box(
        f"Top5 を選択後、「{V8_TAB_LABELS['claim_map']}」へ（Top5 のみ深掘り対象）。"
      ),
      unsafe_allow_html=True,
    )
    return

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
