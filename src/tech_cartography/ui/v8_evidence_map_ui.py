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
  if evidence_map.count_by_source_type:
    st.markdown("**source_type 別 candidate 集計:**")
    for key, val in sorted(evidence_map.count_by_source_type.items(), key=lambda x: -x[1]):
      st.caption(f"- {key}: {val}")
  if evidence_map.count_by_support_level:
    st.markdown("**support_level 別 candidate 集計:**")
    for key, val in sorted(evidence_map.count_by_support_level.items(), key=lambda x: -x[1]):
      st.caption(f"- {key}: {val}")


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
  state = get_v8_input_state()
  default_case = str(state.get("selected_case_id") or st.session_state.get(STATE_V8_SELECTED_CASE) or "").strip()
  default_pub = str(st.session_state.get(STATE_V8_SELECTED_PUBLICATION) or "").strip()

  st.markdown("### Evidence Map v2")
  _render_how_to_read_card()
  st.markdown(
    render_caution_box(
      "<strong>supporting evidence candidate のみ — Evidence Map is not proof。</strong> "
      "paper / web / company は確定 Evidence ではありません。"
      " claim 本文未投入の場合は深掘り不足として claim_text_required 扱いです。"
      " FTO・侵害・有効性判断ではありません。"
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
        _render_metrics(emap)
        _render_link_table(emap.links)
    st.markdown(
      render_next_action_box(f"「{V8_TAB_LABELS['gap_next_actions']}」で Gap / Next Actions（Phase27G）へ進んでください。"),
      unsafe_allow_html=True,
    )
    return

  evidence_map = _to_map(cached["evidence_map"])
  export_info = cached.get("export") or {}
  _render_metrics(evidence_map)
  _render_aggregation_chips(evidence_map)

  loaded_links = [
    l for l in evidence_map.links
    if l.claim_text_status in {"manual_input", "loaded", "csv_imported", "artifact_imported"}
  ]
  if loaded_links:
    st.markdown("🏷️ **claim本文投入済み** — manual_input / loaded claim あり")
    st.markdown(
      render_info_box(
        f"<strong>manual claim 投入後の Evidence Map</strong> — "
        f"loaded/manual_input claims: {len(loaded_links)}。"
        " paper / web / company は引き続き <strong>supporting evidence candidate</strong>（not proof）。"
      ),
      unsafe_allow_html=True,
    )
  elif evidence_map.claim_text_required_count > 0:
    st.markdown(
      render_warning_box(
        "<strong>claim 本文を投入すると Evidence Map が具体化します。</strong> "
        "Claim Map タブで一次情報から claim 本文を手動投入してください。"
      ),
      unsafe_allow_html=True,
    )
    for link in loaded_links[:5]:
      st.caption(
        f"- {link.publication_number} claim {link.claim_no}: "
        f"status={link.claim_text_status}, axis={link.primary_axis}, "
        f"evidence_needed={', '.join(link.evidence_needed[:3])}"
      )

  refresh_cached = st.session_state.get("v8_manual_claim_refresh_result")
  if isinstance(refresh_cached, dict):
    report = refresh_cached.get("report") or {}
    before = report.get("claim_text_required_count_before")
    after = report.get("claim_text_required_count_after")
    if before is not None and after is not None and before != after:
      st.success(f"claim_text_required_count 改善: {before} → {after}")

  if evidence_map.claim_text_required_count > 0:
    st.markdown(
      render_warning_box(
        f"{evidence_map.claim_text_required_count} claim は claim text required — 裏取り候補は未確認です。"
        " Gap / Next Actions タブでは claim_text_required を最優先 Gap として集約します。"
      ),
      unsafe_allow_html=True,
    )
  if evidence_map.missing_evidence_count > 0:
    st.markdown(
      render_info_box(
        f"missing_evidence_count={evidence_map.missing_evidence_count} — "
        "Gap / Next Actions で example/paper/property 不足を分類し Top 3 Actions を生成します。"
      ),
      unsafe_allow_html=True,
    )

  fcol1, fcol2, fcol3, fcol4 = st.columns(4)
  levels = ["（すべて）"] + sorted(evidence_map.count_by_support_level.keys())
  types = ["（すべて）"] + sorted(evidence_map.count_by_support_type.keys())
  stypes = ["（すべて）"] + sorted(evidence_map.count_by_source_type.keys())
  with fcol1:
    fl_level = st.selectbox("support_level", levels, key="v8_ev_filter_level")
  with fcol2:
    fl_type = st.selectbox("support_type", types, key="v8_ev_filter_type")
  with fcol3:
    fl_stype = st.selectbox("source_type", stypes, key="v8_ev_filter_stype")
  with fcol4:
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
  display_links = filtered[:50]
  if len(filtered) > 50:
    st.caption(f"表示: 先頭 50 / 全 {len(filtered)} links — 全件は CSV ダウンロードを利用")
  _render_link_table(display_links)
  st.markdown("#### 選択 link の詳細")
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
  st.caption(f"export dir: {export_info.get('output_dir', '')}")

  st.markdown(
    render_next_action_box(
      f"次: 「{V8_TAB_LABELS['gap_next_actions']}」で Gap / Next Actions を確認。"
      " Gap は未確認事項（not invalidity / weakness）。Top 3 Next Actions を確認してください。"
    ),
    unsafe_allow_html=True,
  )
