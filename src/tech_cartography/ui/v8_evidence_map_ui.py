"""v8 Evidence Map tab (Phase 27F)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from tech_cartography.runtime.v8_evidence_map_schema import V8EvidenceLink, V8EvidenceMap
from tech_cartography.services.v8_claim_map_export import find_latest_claim_map_dir
from tech_cartography.services.v8_evidence_map import build_evidence_map
from tech_cartography.services.v8_evidence_map_export import (
  evidence_map_to_csv_text,
  evidence_map_to_markdown,
  export_evidence_map,
)
from tech_cartography.services.v8_large_candidate_shortlist import load_top5_publications
from tech_cartography.services.v8_patent_shortlist import build_patent_shortlist
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_next_action_box, render_warning_box
from tech_cartography.ui.v8_demo_flow_ui import render_artifact_count_metric, render_demo_flow_banner
from tech_cartography.ui.v8_executive_summary_ui import (
  render_evidence_executive_summary,
  render_evidence_how_to_read_section,
)
from tech_cartography.ui.v8_judge_mode_ui import render_judge_conclusion_card, render_judge_next_tab_hint
from tech_cartography.ui.v8_input_ui import get_v8_input_state
from tech_cartography.ui.v8_tab_config import (
  STATE_V8_SELECTED_CASE,
  STATE_V8_SELECTED_PUBLICATION,
  V8_CASE_SAMPLES,
  V8_TAB_LABELS,
)

STATE_V8_EVIDENCE_MAP = "v8_evidence_map_cache"


def _case_options() -> list[tuple[str, str]]:
  return [("all", "All cases")] + [(s["case_id"], s["label"]) for s in V8_CASE_SAMPLES]


def _render_link_table(links: list[V8EvidenceLink]) -> None:
  cols = [
    "evidence_link_id", "publication_number", "claim_no", "claim_text_status", "primary_axis",
    "technical_axis_labels", "evidence_needed", "source_type", "source_title", "evidence_role",
    "support_type", "support_level", "match_reason", "matched_terms", "evidence_gap",
    "next_verification_action", "human_review_required",
  ]
  rows = []
  for link in links:
    rows.append({
      "evidence_link_id": link.evidence_link_id,
      "publication_number": link.publication_number,
      "claim_no": link.claim_no,
      "claim_text_status": link.claim_text_status,
      "primary_axis": link.primary_axis,
      "technical_axis_labels": ", ".join(link.technical_axis_labels),
      "evidence_needed": ", ".join(link.evidence_needed),
      "source_type": link.source_type or "—",
      "source_title": link.source_title or "—",
      "evidence_role": link.evidence_role,
      "support_type": link.support_type,
      "support_level": link.support_level,
      "match_reason": link.match_reason,
      "matched_terms": ", ".join(link.matched_terms),
      "evidence_gap": link.evidence_gap,
      "next_verification_action": link.next_verification_action,
      "human_review_required": link.human_review_required,
    })
  st.dataframe(pd.DataFrame(rows, columns=cols), width="stretch", hide_index=True)


def _apply_filters(links: list[V8EvidenceLink], *, filters: dict[str, str]) -> list[V8EvidenceLink]:
  result = links
  if filters.get("support_level") and filters["support_level"] != "（すべて）":
    result = [l for l in result if l.support_level == filters["support_level"]]
  if filters.get("support_type") and filters["support_type"] != "（すべて）":
    result = [l for l in result if l.support_type == filters["support_type"]]
  if filters.get("source_type") and filters["source_type"] != "（すべて）":
    result = [l for l in result if l.source_type == filters["source_type"]]
  if filters.get("human_review") == "はい":
    result = [l for l in result if l.human_review_required]
  return result


def _count_manual_claims(links: list[V8EvidenceLink]) -> int:
  return sum(
    1 for l in links
    if l.claim_text_status in {"manual_input", "loaded", "csv_imported", "artifact_imported"}
  )


def _claim_status_summary(links: list[V8EvidenceLink]) -> dict[str, int]:
  counts: dict[str, int] = {"not_loaded": 0, "manual_input": 0, "loaded": 0, "other": 0}
  for link in links:
    status = link.claim_text_status
    if status == "not_loaded":
      counts["not_loaded"] += 1
    elif status == "manual_input":
      counts["manual_input"] += 1
    elif status in {"loaded", "csv_imported", "artifact_imported"}:
      counts["loaded"] += 1
    else:
      counts["other"] += 1
  return counts


def _render_how_to_read_card() -> None:
  st.markdown(
    render_info_box(
      "<strong>Evidence Mapの見方 (Phase27L)</strong><br>"
      "• 1000件母集団から Top5 のみ Deep Dive しています。<br>"
      "• claim 本文未投入 → <strong>claim_text_required</strong>（深掘り不足）。<br>"
      "• claim 手動投入済み → Claim Map / Evidence Map が具体化します。<br>"
      "• paper / web / company は <strong>supporting evidence candidate</strong> — "
      "<strong>Evidence Map is not proof</strong>。<br>"
      "• 実施例本文・論文本文を読んだことにはしません。"
    ),
    unsafe_allow_html=True,
  )


def _render_metrics(evidence_map: V8EvidenceMap) -> None:
  paper_count = sum(
    1 for l in evidence_map.links
    if l.support_type == "paper_support_candidate" or l.source_type == "paper"
  )
  web_count = sum(
    1 for l in evidence_map.links
    if l.support_type == "web_signal_candidate" or l.source_type == "web"
  )
  company_count = sum(
    1 for l in evidence_map.links
    if l.support_type == "company_signal_candidate" or l.source_type == "company"
  )
  review_count = sum(1 for l in evidence_map.links if l.human_review_required)
  manual_count = _count_manual_claims(evidence_map.links)
  c1, c2, c3, c4 = st.columns(4)
  c1.metric("claim_text_required", evidence_map.claim_text_required_count)
  c2.metric("manual_claim_count", manual_count)
  c3.metric("evidence_link_count", evidence_map.link_count)
  c4.metric("missing_evidence", evidence_map.missing_evidence_count)
  c5, c6, c7, c8 = st.columns(4)
  c5.metric("paper_candidate", paper_count)
  c6.metric("web_candidate", web_count)
  c7.metric("company_candidate", company_count)
  c8.metric("needs_human_review", review_count)


def _render_aggregation_chips(evidence_map: V8EvidenceMap) -> None:
  status = _claim_status_summary(evidence_map.links)
  st.markdown("**claim status summary:**")
  st.caption(
    f"not_loaded={status['not_loaded']} / manual_input={status['manual_input']} / "
    f"loaded={status['loaded']}"
  )
  pub_counts: dict[str, int] = {}
  for link in evidence_map.links:
    pub_counts[link.publication_number] = pub_counts.get(link.publication_number, 0) + 1
  if pub_counts:
    st.markdown("**patent 別 claim link count:**")
    for pub, count in sorted(pub_counts.items(), key=lambda x: (-x[1], x[0])):
      st.caption(f"- {pub}: {count}")
  if evidence_map.count_by_support_type:
    st.markdown("**support_type 別 candidate 集計:**")
    for key, val in sorted(evidence_map.count_by_support_type.items(), key=lambda x: -x[1]):
      st.caption(f"- {key}: {val}")
  if evidence_map.count_by_support_level:
    st.markdown("**support_level 別 candidate 集計:**")
    for key, val in sorted(evidence_map.count_by_support_level.items(), key=lambda x: -x[1]):
      st.caption(f"- {key}: {val}")


def _render_top_links_preview(links: list[V8EvidenceLink], *, limit: int = 20) -> None:
  if not links:
    return
  st.markdown(f"**Top evidence links preview（先頭 {min(limit, len(links))} / 全 {len(links)}）**")
  preview_cols = [
    "publication_number", "claim_no", "support_type", "support_level",
    "source_type", "source_title", "evidence_gap",
  ]
  rows = []
  for link in links[:limit]:
    rows.append({
      "publication_number": link.publication_number,
      "claim_no": link.claim_no,
      "support_type": link.support_type,
      "support_level": link.support_level,
      "source_type": link.source_type or "—",
      "source_title": (link.source_title or "—")[:60],
      "evidence_gap": (link.evidence_gap or "—")[:80],
    })
  st.dataframe(pd.DataFrame(rows, columns=preview_cols), width="stretch", hide_index=True)


def _render_link_detail(links: list[V8EvidenceLink], *, key_prefix: str) -> None:
  if not links:
    return
  labels = [f"{l.publication_number} / {l.support_type} / {l.source_title[:30] if l.source_title else 'no source'}" for l in links]
  idx = st.selectbox("詳細", range(len(links)), format_func=lambda i: labels[i], key=f"{key_prefix}_detail")
  detail = links[idx]
  if detail.support_type == "claim_text_required":
    st.markdown(render_warning_box("<strong>claim text required</strong> — 請求項本文が未取得です。"), unsafe_allow_html=True)
  st.caption(f"source_url: {detail.source_url or '（なし）'}")
  st.markdown(f"**caution_flags:** {', '.join(detail.caution_flags)}")
  st.caption(f"next_phase: Gap / Next Actions")


def render_v8_evidence_map_tab(*, project_root: Path | str) -> None:
  root = Path(project_root)
  render_judge_conclusion_card("evidence_map")
  render_judge_next_tab_hint("evidence_map")

  state = get_v8_input_state()
  default_case = str(state.get("selected_case_id") or st.session_state.get(STATE_V8_SELECTED_CASE) or "").strip()
  default_pub = str(st.session_state.get(STATE_V8_SELECTED_PUBLICATION) or "").strip()

  st.markdown("### Evidence Map｜裏取り候補")
  st.caption(
    "PDF解析・実施例ファクト抽出・claim-example対応候補は"
    f"「{V8_TAB_LABELS['patent_shortlist']}」タブの Top5 Deep Dive で実行します。"
    " claim-example対応候補は次Phaseで Evidence Map / Gap ロジックに反映予定です。"
    " ここでは裏取り候補の整理のみ表示します（確定Evidenceではありません）。"
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
      key="v8_evidence_map_case",
    )
  active_case = case_ids[1] if selected_case == "all" else selected_case
  if selected_case != "all":
    st.session_state[STATE_V8_SELECTED_CASE] = selected_case

  shortlist = build_patent_shortlist(case_id=active_case, top_n=5, project_root=root)
  top5_large = load_top5_publications(active_case, root)
  deep_dive = top5_large if top5_large else [p.publication_number for p in shortlist.patent_candidates]
  if top5_large:
    st.caption(f"Evidence Map 深掘り対象は Large Candidate Top5 のみ: {', '.join(top5_large)}")
  pub_options = ["（Top5 Deep Dive 全件）"] + deep_dive
  default_pub_idx = pub_options.index(default_pub) if default_pub in pub_options else 0
  with col2:
    selected_pub_label = st.selectbox(
      "特許（Top5 Deep Dive）",
      options=pub_options,
      index=default_pub_idx,
      key="v8_evidence_map_pub",
    )
  publication_number = None if selected_pub_label.startswith("（") else selected_pub_label
  if publication_number:
    st.session_state[STATE_V8_SELECTED_PUBLICATION] = publication_number

  claim_map_dir = find_latest_claim_map_dir(active_case, root)
  if claim_map_dir:
    with st.expander("artifact参照（開発者向け）", expanded=False):
      st.caption(f"Claim Map artifact: {claim_map_dir}")
  else:
    st.caption("Claim Map 未生成 — Generate 時に自動構築されます")

  input_mode = st.radio(
    "Evidence Map生成",
    options=["Claim Map artifactを使う", "Sources一覧を使う", "claim未取得でもGapとして作成"],
    horizontal=True,
    key="v8_evidence_map_mode",
  )
  include_unloaded = input_mode == "claim未取得でもGapとして作成" or input_mode == "Claim Map artifactを使う"

  refresh = st.button("Generate / Refresh Evidence Map", key="v8_evidence_map_refresh", type="primary")

  cache_key = f"{selected_case}:{publication_number}:{input_mode}"
  if refresh or st.session_state.get("v8_evidence_map_cache_key") != cache_key:
    if selected_case == "all":
      bundles: dict[str, dict] = {}
      for sample in V8_CASE_SAMPLES:
        cid = sample["case_id"]
        emap = build_evidence_map(
          case_id=cid,
          publication_number=None,
          project_root=root,
          include_unloaded_claim_gaps=include_unloaded,
        )
        export_result = export_evidence_map(emap, project_root=root)
        bundles[cid] = {"evidence_map": emap.to_dict(), "export": export_result.to_dict()}
      st.session_state[STATE_V8_EVIDENCE_MAP] = {"mode": "all", "bundles": bundles}
    else:
      emap = build_evidence_map(
        case_id=selected_case,
        publication_number=publication_number,
        project_root=root,
        include_unloaded_claim_gaps=include_unloaded,
      )
      export_result = export_evidence_map(emap, project_root=root)
      st.session_state[STATE_V8_EVIDENCE_MAP] = {
        "mode": "single",
        "evidence_map": emap.to_dict(),
        "export": export_result.to_dict(),
      }
    st.session_state["v8_evidence_map_cache_key"] = cache_key

  cached = st.session_state.get(STATE_V8_EVIDENCE_MAP)
  if not cached:
    render_evidence_executive_summary(None)
    render_evidence_how_to_read_section()
    with st.expander("詳細ガイド・注意事項", expanded=False):
      render_demo_flow_banner(
        project_root=root,
        current_tab="evidence_map",
        tab_purpose="supporting evidence candidate — 裏取り候補（証明ではない）",
        next_tab_key="gap_next_actions",
      )
      _render_how_to_read_card()
      st.markdown(
        render_caution_box(
          "<strong>裏取り候補（supporting evidence candidate）のみ — 証明ではありません。</strong> "
          " paper / web / company は確定 Evidence ではありません。"
          " 原典確認は人間が行います。FTO・侵害・有効性判断ではありません。"
        ),
        unsafe_allow_html=True,
      )
    st.info("「Generate / Refresh Evidence Map」を押してください。")
    st.markdown(
      render_next_action_box(f"先に「{V8_TAB_LABELS['claim_map']}」で Claim Map を生成してください。"),
      unsafe_allow_html=True,
    )
    return

  def _to_map(data: dict) -> V8EvidenceMap:
    return V8EvidenceMap(
      evidence_map_id=data["evidence_map_id"],
      case_id=data["case_id"],
      publication_number=data["publication_number"],
      generated_at=data["generated_at"],
      links=[V8EvidenceLink.from_dict(l) for l in data["links"]],
      link_count=data["link_count"],
      claim_count=data["claim_count"],
      source_count=data["source_count"],
      count_by_support_type=data.get("count_by_support_type", {}),
      count_by_support_level=data.get("count_by_support_level", {}),
      count_by_source_type=data.get("count_by_source_type", {}),
      missing_evidence_count=data.get("missing_evidence_count", 0),
      claim_text_required_count=data.get("claim_text_required_count", 0),
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
      emap = _to_map(bundle["evidence_map"])
      with st.expander(f"{sample['label']} — {emap.link_count} links", expanded=cid == active_case):
        render_evidence_executive_summary(emap)
        with st.expander("詳細メトリクス・集計", expanded=False):
          _render_metrics(emap)
          _render_aggregation_chips(emap)
        _render_top_links_preview(emap.links, limit=20)
    st.markdown(
      render_next_action_box(f"「{V8_TAB_LABELS['gap_next_actions']}」で Gap / Next Actions（Phase27G）へ進んでください。"),
      unsafe_allow_html=True,
    )
    return

  evidence_map = _to_map(cached["evidence_map"])
  export_info = cached.get("export") or {}
  render_evidence_executive_summary(evidence_map)
  render_evidence_how_to_read_section()
  with st.expander("詳細ガイド・注意事項", expanded=False):
    render_demo_flow_banner(
      project_root=root,
      current_tab="evidence_map",
      tab_purpose="supporting evidence candidate — 裏取り候補（証明ではない）",
      next_tab_key="gap_next_actions",
    )
    _render_how_to_read_card()
    st.markdown(
      render_caution_box(
        "<strong>裏取り候補（supporting evidence candidate）のみ — 証明ではありません。</strong> "
        " paper / web / company は確定 Evidence ではありません。"
        " 原典確認は人間が行います。FTO・侵害・有効性判断ではありません。"
      ),
      unsafe_allow_html=True,
    )
  with st.expander("詳細メトリクス・集計", expanded=False):
    st.caption("artifact missing と true zero を区別 — 未生成時は件数0として表示しません")
    _render_metrics(evidence_map)
    _render_aggregation_chips(evidence_map)
  _render_top_links_preview(evidence_map.links, limit=20)

  with st.expander("全Evidence links（フィルタ・link一覧・claim投入メモ）", expanded=False):
    loaded_links = [
      l for l in evidence_map.links
      if l.claim_text_status in {"manual_input", "loaded", "csv_imported", "artifact_imported"}
    ]
    if loaded_links:
      st.caption(f"claim本文投入済み: {len(loaded_links)} links")
    elif evidence_map.claim_text_required_count > 0:
      st.caption("claim 本文未投入 — Claim Map タブで投入してください")

    levels = ["（すべて）"] + sorted(evidence_map.count_by_support_level.keys())
    types = ["（すべて）"] + sorted(evidence_map.count_by_support_type.keys())
    stypes = ["（すべて）"] + sorted(evidence_map.count_by_source_type.keys())
    fl_level = st.selectbox("support_level", levels, key="v8_ev_filter_level")
    fl_type = st.selectbox("support_type", types, key="v8_ev_filter_type")
    fl_stype = st.selectbox("source_type", stypes, key="v8_ev_filter_stype")
    fl_review = st.selectbox("human_review_required", ["すべて", "はい"], key="v8_ev_filter_review")

    filtered = _apply_filters(
      evidence_map.links,
      filters={
        "support_level": fl_level,
        "support_type": fl_type,
        "source_type": fl_stype,
        "human_review": fl_review,
      },
    )
    _render_link_table(filtered[:20])
    _render_link_detail(filtered, key_prefix="v8_evidence_map")

  st.markdown("#### ダウンロード")
  st.download_button(
    "CSV", evidence_map_to_csv_text(evidence_map.links).encode("utf-8"),
    f"evidence_map_{selected_case}.csv", "text/csv", key="v8_ev_dl_csv",
  )
  st.download_button(
    "Markdown", evidence_map_to_markdown(evidence_map).encode("utf-8"),
    f"evidence_map_{selected_case}.md", "text/markdown", key="v8_ev_dl_md",
  )
  xlsx_path = Path(str(export_info.get("xlsx_path", "")))
  if xlsx_path.exists():
    st.download_button(
      "Excel", xlsx_path.read_bytes(), xlsx_path.name,
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="v8_ev_dl_xlsx",
    )
  with st.expander("export dir（開発者向け）", expanded=False):
    st.caption(f"export dir: {export_info.get('output_dir', '')}")

  st.markdown(
    render_next_action_box(
      f"次: 「{V8_TAB_LABELS['gap_next_actions']}」で Gap / Next Actions を確認。"
      " Gap は未確認事項（not invalidity / weakness）。Top 3 Next Actions を確認してください。"
    ),
    unsafe_allow_html=True,
  )
