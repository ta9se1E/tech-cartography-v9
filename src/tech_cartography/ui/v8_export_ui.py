"""v8 Export tab (Phase 27C)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from tech_cartography.runtime.v8_sources_schema import FIXED_POINT_OBSERVATION_NOTE, SAFETY_EXPORT_NOTICES
from tech_cartography.services.live_evidence_gap_builder import find_latest_evidence_gap_path
from tech_cartography.services.live_strategic_watch_brief import find_latest_strategic_watch_brief_path
from tech_cartography.services.live_weekly_decision_cockpit import find_latest_weekly_decision_cockpit_path
from tech_cartography.services.v8_case_validation_export import (
  export_validation_pack,
  find_latest_validation_pack_dir,
)
from tech_cartography.services.v8_case_validation_pack import build_three_case_validation_pack
from tech_cartography.services.v8_claim_map_export import find_latest_claim_map_dir
from tech_cartography.services.v8_evidence_map_export import find_latest_evidence_map_dir
from tech_cartography.services.v8_gap_next_actions_export import find_latest_gap_next_actions_dir
from tech_cartography.services.v8_fixed_point_observation_export import find_latest_fixed_point_observation_dir
from tech_cartography.services.v8_demo_readiness import build_demo_readiness_report
from tech_cartography.services.v8_demo_readiness_export import export_demo_readiness, find_latest_demo_readiness_dir
from tech_cartography.services.v8_demo_polish import build_demo_polish_report
from tech_cartography.services.v8_demo_polish_export import export_demo_polish, find_latest_demo_polish_dir
from tech_cartography.services.v8_export_package import build_export_package, get_v8_export_packages_dir, records_to_csv_text, records_to_markdown
from tech_cartography.services.v8_large_candidate_shortlist import find_latest_large_shortlist_dir
from tech_cartography.services.v8_manual_claim_refresh_export import find_latest_manual_claim_refresh_dir
from tech_cartography.services.v8_patent_shortlist_export import find_latest_patent_shortlist_dir
from tech_cartography.services.v8_sources_repository import filter_sources_table, load_sources_table, resolve_case_name
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box
from tech_cartography.ui.v8_input_ui import get_v8_input_state
from tech_cartography.ui.v8_tab_config import STATE_V8_SELECTED_CASE, V8_CASE_SAMPLES


def _artifact_link(path: Path | None) -> None:
  if path and path.exists():
    st.caption(str(path))
  else:
    st.caption("（未生成）")


def render_v8_export_tab(*, project_root: Path | str) -> None:
  root = Path(project_root)
  state = get_v8_input_state()
  default_case = str(state.get("selected_case_id") or st.session_state.get(STATE_V8_SELECTED_CASE) or "").strip()

  st.markdown("### Export")
  st.markdown(
    render_caution_box(
      "candidate information only / human review required。"
      " FTO、侵害、有効性判断、法的結論は行いません。"
      " secret 値は表示しません。"
    ),
    unsafe_allow_html=True,
  )

  case_options = [("all", "All cases")] + [(s["case_id"], s["label"]) for s in V8_CASE_SAMPLES]
  case_ids = [c for c, _ in case_options]
  labels = {c: label for c, label in case_options}
  default_idx = case_ids.index(default_case) if default_case in case_ids else 0
  export_case = st.selectbox(
    "Export対象案件",
    options=case_ids,
    index=default_idx,
    format_func=lambda cid: labels[cid],
    key="v8_export_case_select",
  )

  base_table = load_sources_table(case_id=None if export_case == "all" else export_case, project_root=root)
  filtered = filter_sources_table(base_table, case_id=export_case)
  case_name = resolve_case_name(export_case, root)

  st.markdown("#### Sources Export")
  if filtered.records:
    st.download_button(
      "Sources CSV",
      data=records_to_csv_text(filtered.records).encode("utf-8"),
      file_name=f"sources_{export_case}.csv",
      mime="text/csv",
      key="v8_export_dl_csv",
    )
    st.download_button(
      "Sources Markdown",
      data=records_to_markdown(filtered.records, case_name=case_name, table=filtered).encode("utf-8"),
      file_name=f"sources_{export_case}.md",
      mime="text/markdown",
      key="v8_export_dl_md",
    )
  else:
    st.caption("Sources データなし")

  if st.button("Export Package を生成", key="v8_export_build_package", type="primary"):
    package = build_export_package(filtered, case_id=export_case, project_root=root)
    st.session_state["v8_last_export_package"] = package.to_dict()
    st.success("Export Package を生成しました。")

  pkg = st.session_state.get("v8_last_export_package")
  if isinstance(pkg, dict):
    st.markdown("#### 直近 Export Package")
    st.caption(f"output_dir: {pkg.get('output_dir')}")
    st.caption(f"manifest: {pkg.get('manifest_path')}")
    st.caption(f"export_summary: {pkg.get('export_summary_path')}")
    for label, key in (
      ("sources.csv", "sources_csv_path"),
      ("sources.md", "sources_md_path"),
      ("sources.xlsx", "sources_xlsx_path"),
    ):
      path = Path(str(pkg.get(key) or ""))
      if path.exists():
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if path.suffix == ".xlsx" else "text/plain"
        st.download_button(f"Download {label}", data=path.read_bytes(), file_name=path.name, mime=mime, key=f"v8_export_pkg_{key}")
    if pkg.get("excel_warning"):
      st.caption(str(pkg.get("excel_warning")))

  st.markdown("#### Patent Shortlist Export (Phase27D)")
  st.caption(
    "Export Package には今後 patent_shortlist.csv / md / xlsx / manifest を同梱する予定です。"
    " スコアは読む優先度の暫定値であり、特許価値・権利価値・法的判断ではありません。"
  )
  shortlist_dir = find_latest_patent_shortlist_dir(
    None if export_case == "all" else export_case,
    root,
  )
  if shortlist_dir and shortlist_dir.exists():
    st.caption(f"latest patent shortlist: {shortlist_dir}")
    for fname, mime in (
      ("patent_shortlist.csv", "text/csv"),
      ("patent_shortlist.md", "text/markdown"),
      ("patent_shortlist.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
      ("patent_shortlist_manifest.json", "application/json"),
    ):
      path = shortlist_dir / fname
      if path.exists():
        st.download_button(f"Download {fname}", data=path.read_bytes(), file_name=path.name, mime=mime, key=f"v8_export_shortlist_{fname}")
  else:
    st.caption("Patent Shortlist は未生成 — 「読むべき特許」タブで Generate してください。")

  st.markdown("#### Claim Map Export (Phase27E)")
  st.caption(
    "Export Package には今後 claim_map.csv / md / xlsx / manifest を同梱する予定です。"
    " Claim Map は技術整理であり、権利範囲解釈・法的判断ではありません。"
  )
  claim_map_dir = find_latest_claim_map_dir(
    None if export_case == "all" else export_case,
    root,
  )
  if claim_map_dir and claim_map_dir.exists():
    st.caption(f"latest claim map: {claim_map_dir}")
    for fname, mime in (
      ("claim_map.csv", "text/csv"),
      ("claim_map.md", "text/markdown"),
      ("claim_map.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
      ("claim_map_manifest.json", "application/json"),
    ):
      path = claim_map_dir / fname
      if path.exists():
        st.download_button(
          f"Download {fname}",
          data=path.read_bytes(),
          file_name=path.name,
          mime=mime,
          key=f"v8_export_claim_map_{fname}",
        )
  else:
    st.caption("Claim Map は未生成 — 「Claim Map」タブで Generate してください。")

  st.markdown("#### Evidence Map Export (Phase27F)")
  st.caption(
    "Export Package には今後 evidence_map.csv / md / xlsx / manifest を同梱する予定です。"
    " Evidence Map は裏付け候補であり証明ではありません。"
  )
  evidence_map_dir = find_latest_evidence_map_dir(
    None if export_case == "all" else export_case,
    root,
  )
  if evidence_map_dir and evidence_map_dir.exists():
    st.caption(f"latest evidence map: {evidence_map_dir}")
    for fname, mime in (
      ("evidence_map.csv", "text/csv"),
      ("evidence_map.md", "text/markdown"),
      ("evidence_map.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
      ("evidence_map_manifest.json", "application/json"),
    ):
      path = evidence_map_dir / fname
      if path.exists():
        st.download_button(
          f"Download {fname}",
          data=path.read_bytes(),
          file_name=path.name,
          mime=mime,
          key=f"v8_export_evidence_map_{fname}",
        )
  else:
    st.caption("Evidence Map は未生成 — 「Evidence Map」タブで Generate してください。")

  st.markdown("#### Gap / Next Actions Export (Phase27G)")
  st.caption(
    "Export Package には今後 gap_next_actions.csv / md / xlsx / manifest / "
    "watch_profile_update_proposal.md / digest_summary.md を同梱する予定です。"
    " Gap は未確認事項であり、特許の弱点・無効性・侵害可能性ではありません。"
    " Next Action は人間の確認作業であり、法的判断ではありません。"
  )
  gap_dir = find_latest_gap_next_actions_dir(
    None if export_case == "all" else export_case,
    root,
  )
  if gap_dir and gap_dir.exists():
    st.caption(f"latest gap / next actions: {gap_dir}")
    for fname, mime in (
      ("gap_next_actions.csv", "text/csv"),
      ("gap_next_actions.md", "text/markdown"),
      ("gap_next_actions.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
      ("gap_next_actions_manifest.json", "application/json"),
      ("watch_profile_update_proposal.md", "text/markdown"),
      ("digest_summary.md", "text/markdown"),
    ):
      path = gap_dir / fname
      if path.exists():
        st.download_button(
          f"Download {fname}",
          data=path.read_bytes(),
          file_name=path.name,
          mime=mime,
          key=f"v8_export_gap_{fname}",
        )
  else:
    st.caption("Gap / Next Actions は未生成 — 「Gap / Next Actions」タブで Generate してください。")

  st.markdown(render_info_box(FIXED_POINT_OBSERVATION_NOTE), unsafe_allow_html=True)

  st.markdown("#### Fixed Point Observation Export (Phase27H)")
  st.caption(
    "Export Package には今後 fixed_point_observation.json / md / xlsx / manifest / "
    "watch_profile_update_proposal.md / scheduler_followup_plan.md / email_digest_plan.md "
    "を同梱する予定です。"
    " メール送信と Scheduler は必須機能として残します（本 Phase では送信・起動しません）。"
    " Watch Profile 更新は人手承認後に行います。"
  )
  fp_dir = find_latest_fixed_point_observation_dir(
    None if export_case == "all" else export_case,
    root,
  )
  if fp_dir and fp_dir.exists():
    st.caption(f"latest fixed point observation: {fp_dir}")
    for fname, mime in (
      ("fixed_point_observation.json", "application/json"),
      ("fixed_point_observation.md", "text/markdown"),
      ("fixed_point_observation.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
      ("fixed_point_observation_manifest.json", "application/json"),
      ("watch_profile_update_proposal.md", "text/markdown"),
      ("scheduler_followup_plan.md", "text/markdown"),
      ("email_digest_plan.md", "text/markdown"),
    ):
      path = fp_dir / fname
      if path.exists():
        st.download_button(
          f"Download {fname}",
          data=path.read_bytes(),
          file_name=path.name,
          mime=mime,
          key=f"v8_export_fp_{fname}",
        )
  else:
    st.caption("Fixed Point Observation は未生成 — 「定点観測」タブで Generate してください。")

  st.markdown("#### Large Candidate Pack (Phase27J.0 / 27J.1)")
  st.caption(
    "1000件は母集団。Top5 のみ Deep Dive。Ranking explanation は読む優先度の説明であり、"
    "技術的正しさ・特許価値・法的価値ではありません。"
    " Cloud Build / 外部 API / BigQuery 実行は行いません。"
  )
  lc_case = export_case if export_case != "all" else V8_CASE_SAMPLES[0]["case_id"]
  lc_dir = find_latest_large_shortlist_dir(lc_case, root)
  if lc_dir and lc_dir.exists():
    import json as _json

    manifest_path = lc_dir / "large_candidate_shortlist_manifest.json"
    if manifest_path.exists():
      manifest = _json.loads(manifest_path.read_text(encoding="utf-8"))
      sel = manifest.get("selection") or {}
      st.markdown(f"- **case_id**: {lc_case}")
      st.markdown(f"- **triage_engine**: {manifest.get('triage_engine', '—')}")
      st.markdown(f"- **ranking_policy**: {manifest.get('ranking_policy', '—')}")
      st.markdown(f"- imported: {sel.get('population_count', '—')}")
      st.markdown(f"- deduped: {sel.get('deduped_count', '—')}")
      st.markdown(f"- Top100: {sel.get('top100_count', '—')}")
      st.markdown(f"- Top20: {sel.get('top20_count', '—')}")
      st.markdown(f"- Top5: {sel.get('top5_count', '—')}")
      re_info = manifest.get("ranking_explanation") or {}
      if re_info.get("common_selection_reasons"):
        st.markdown("**common_selection_reasons:**")
        for r in re_info["common_selection_reasons"][:5]:
          st.caption(f"- {r}")
      if re_info.get("common_exclusion_reasons"):
        st.markdown("**common_exclusion_reasons:**")
        for r in re_info["common_exclusion_reasons"][:5]:
          st.caption(f"- {r}")

    st.markdown("##### Ranking Explanation Pack")
    for fname, mime in (
      ("ranking_explanation.md", "text/markdown"),
      ("ranking_explanation.json", "application/json"),
      ("ranking_explanation.csv", "text/csv"),
      ("top5_ranking_explanation.md", "text/markdown"),
      ("dropped_candidate_summary.md", "text/markdown"),
    ):
      path = lc_dir / fname
      if path.exists():
        st.download_button(
          f"Download {fname}",
          data=path.read_bytes(),
          file_name=path.name,
          mime=mime,
          key=f"v8_export_re_{fname}",
        )

    for fname, mime in (
      ("large_candidate_population.csv", "text/csv"),
      ("large_candidate_deduped.csv", "text/csv"),
      ("large_candidate_scored.csv", "text/csv"),
      ("large_candidate_top100.csv", "text/csv"),
      ("large_candidate_top20.csv", "text/csv"),
      ("large_candidate_top5.csv", "text/csv"),
      ("large_candidate_shortlist_summary.md", "text/markdown"),
      ("large_candidate_shortlist_manifest.json", "application/json"),
    ):
      path = lc_dir / fname
      if path.exists():
        st.download_button(
          f"Download {fname}",
          data=path.read_bytes(),
          file_name=path.name,
          mime=mime,
          key=f"v8_export_lc_{fname}",
        )
  else:
    st.caption("Large Candidate Pack 未生成 — 入力タブで取り込み後、読むべき特許で Top5 を生成してください。")

  st.markdown("#### Demo Readiness Pack (Phase27M)")
  st.caption(
    "3案件の Demo Readiness — artifact missing と true zero を区別。"
    " Cloud Build / Cloud Run deploy はまだ実行しません。"
  )
  if st.button("Generate Demo Readiness Pack", key="v8_export_demo_readiness", type="primary"):
    report = build_demo_readiness_report(project_root=root)
    export_result = export_demo_readiness(report, project_root=root)
    st.session_state["v8_last_demo_readiness"] = {
      "report": report.to_dict(),
      "export": export_result.to_dict(),
    }
    st.success(f"Demo Readiness Pack 生成 — overall={report.overall_status}")

  cached_readiness = st.session_state.get("v8_last_demo_readiness")
  readiness_dir = find_latest_demo_readiness_dir(root)
  if isinstance(cached_readiness, dict):
    report = cached_readiness.get("report") or {}
    st.markdown(f"- **overall_status**: {report.get('overall_status', '—')}")
    for case in report.get("cases") or []:
      ev = case.get("evidence_link_count")
      gap = case.get("gap_count")
      ev_label = ev if ev is not None else "artifact_missing"
      gap_label = gap if gap is not None else "artifact_missing"
      st.markdown(
        f"- **{case.get('case_id')}**: {case.get('overall_status')} — "
        f"next={case.get('current_recommended_step')} / evidence={ev_label} / gap={gap_label}"
      )
    for action in (report.get("common_next_actions") or [])[:3]:
      st.caption(f"next: {action}")
    dl_dir = Path(str((cached_readiness.get("export") or {}).get("output_dir", "")))
  elif readiness_dir and readiness_dir.exists():
    st.caption(f"latest demo readiness: {readiness_dir}")
    dl_dir = readiness_dir
  else:
    st.caption("Demo Readiness Pack 未生成")
    dl_dir = None

  if dl_dir and dl_dir.exists():
    for fname, mime in (
      ("demo_readiness_report.md", "text/markdown"),
      ("demo_readiness_report.json", "application/json"),
      ("demo_operator_checklist.md", "text/markdown"),
      ("cloud_preparation_checklist.md", "text/markdown"),
      ("demo_readiness_manifest.json", "application/json"),
    ):
      path = dl_dir / fname
      if path.exists():
        st.download_button(
          f"Download {fname}",
          data=path.read_bytes(),
          file_name=path.name,
          mime=mime,
          key=f"v8_export_dr_{fname}",
        )

  st.markdown("#### デモ提出用 — 最低限の Pack")
  st.caption(
    "Large Candidate Pack / Ranking Explanation / Manual Claim Refresh / "
    "Demo Polish Pack / Demo Readiness Pack"
  )

  st.markdown("#### Demo Polish Pack (Phase27L)")
  st.caption(
    "Evidence Map / Gap / Next Actions をデモ向けに要約。"
    " Evidence Map is not proof / Gap is not invalidity / weakness。"
    " Cloud Build / メール送信 / Scheduler 起動は行いません。"
  )
  polish_case = export_case if export_case != "all" else V8_CASE_SAMPLES[0]["case_id"]
  if st.button("Generate Demo Polish Pack", key="v8_export_demo_polish", type="primary"):
    report = build_demo_polish_report(case_id=polish_case, project_root=root)
    export_result = export_demo_polish(report, project_root=root)
    st.session_state["v8_last_demo_polish"] = {
      "report": report.to_dict(),
      "export": export_result.to_dict(),
    }
    st.success("Demo Polish Pack を生成しました。")

  cached_polish = st.session_state.get("v8_last_demo_polish")
  polish_dir = find_latest_demo_polish_dir(
    None if export_case == "all" else export_case,
    root,
  )
  if isinstance(cached_polish, dict):
    report = cached_polish.get("report") or {}
    export_info = cached_polish.get("export") or {}
    ev = report.get("evidence_demo_status") or {}
    gap = report.get("gap_demo_status") or {}
    st.markdown(f"- **case_id**: {report.get('case_id', '—')}")
    st.markdown(f"- **publication_number**: {report.get('publication_number', '—')}")
    st.markdown(f"- **claim_text_required_count**: {ev.get('claim_text_required_count', '—')}")
    st.markdown(f"- **manual_claim_count**: {ev.get('manual_claim_count', '—')}")
    st.markdown(f"- **evidence_link_count**: {ev.get('evidence_link_count', '—')}")
    st.markdown(f"- **gap_count**: {gap.get('gap_count', '—')}")
    for action in (gap.get("top_3_next_actions") or [])[:3]:
      st.caption(f"next: {action}")
    for lim in (report.get("remaining_limitations") or [])[:5]:
      st.caption(f"limitation: {lim}")
    dl_dir = Path(str(export_info.get("output_dir", "")))
  elif polish_dir and polish_dir.exists():
    st.caption(f"latest demo polish: {polish_dir}")
    dl_dir = polish_dir
  else:
    st.caption("Demo Polish Pack 未生成 — Generate ボタンを押してください。")
    dl_dir = None

  if dl_dir and dl_dir.exists():
    for fname, mime in (
      ("demo_polish_report.md", "text/markdown"),
      ("demo_polish_report.json", "application/json"),
      ("demo_story_cards.csv", "text/csv"),
      ("demo_narrative.md", "text/markdown"),
      ("demo_caveats.md", "text/markdown"),
      ("demo_polish_manifest.json", "application/json"),
    ):
      path = dl_dir / fname
      if path.exists():
        st.download_button(
          f"Download {fname}",
          data=path.read_bytes(),
          file_name=path.name,
          mime=mime,
          key=f"v8_export_dp_{fname}",
        )

  st.markdown("#### Manual Claim Refresh Pack (Phase27K)")
  st.caption(
    "claim 本文はユーザー提供のみ。システムは生成しません。"
    " Cloud Build / メール送信 / Scheduler 起動は行いません。"
  )
  refresh_dir = find_latest_manual_claim_refresh_dir(root)
  cached_refresh = st.session_state.get("v8_manual_claim_refresh_result")
  if isinstance(cached_refresh, dict):
    report = cached_refresh.get("report") or {}
    export_info = cached_refresh.get("export") or {}
    st.markdown(f"- **case_id**: {report.get('case_id', '—')}")
    st.markdown(f"- **publication_number**: {report.get('publication_number', '—')}")
    inj = report.get("claim_injection_result") or {}
    st.markdown(f"- **claim_text_status**: {inj.get('claim_text_status', 'loaded')}")
    st.markdown(
      f"- **claim_text_required_count**: {report.get('claim_text_required_count_before', '—')} → "
      f"{report.get('claim_text_required_count_after', '—')}"
    )
    st.markdown(
      f"- **validation_readiness**: {report.get('validation_readiness_before')} → "
      f"{report.get('validation_readiness_after')}"
    )
    for issue in (report.get("remaining_blocking_issues") or [])[:5]:
      st.caption(f"blocking: {issue}")
    for action in (report.get("next_human_actions") or [])[:3]:
      st.caption(f"next: {action}")
    dl_dir = Path(str(export_info.get("output_dir", "")))
  elif refresh_dir and refresh_dir.exists():
    st.caption(f"latest manual claim refresh: {refresh_dir}")
    dl_dir = refresh_dir
  else:
    st.caption("Manual Claim Refresh Pack 未生成 — Claim Map タブで claim 投入後に再生成してください。")
    dl_dir = None

  if dl_dir and dl_dir.exists():
    for fname, mime in (
      ("manual_claim_refresh_report.md", "text/markdown"),
      ("manual_claim_refresh_report.json", "application/json"),
      ("refreshed_artifact_trace.md", "text/markdown"),
      ("manual_claim_refresh_manifest.json", "application/json"),
    ):
      path = dl_dir / fname
      if path.exists():
        st.download_button(
          f"Download {fname}",
          data=path.read_bytes(),
          file_name=path.name,
          mime=mime,
          key=f"v8_export_mcr_{fname}",
        )

  st.markdown("#### 3案件検証パック (Phase27I)")
  st.caption(
    "Cloud Build はまだ実行しません。claim 本文未取得は needs_claim_text として正しく評価します。"
    " 架空 claim は生成しません。FTO/侵害/有効性判断ではありません。"
  )
  if st.button("Generate Three Case Validation Pack", key="v8_export_validation_pack", type="primary"):
    pack = build_three_case_validation_pack(project_root=root, ensure_artifacts=True)
    export_result = export_validation_pack(pack, project_root=root)
    st.session_state["v8_last_validation_pack"] = {
      "pack": pack.to_dict(),
      "export": export_result.to_dict(),
    }
    st.success(f"Validation Pack 生成完了 — overall_status={pack.overall_status}")

  cached_pack = st.session_state.get("v8_last_validation_pack")
  val_dir = find_latest_validation_pack_dir(root)
  if isinstance(cached_pack, dict):
    pack_data = cached_pack.get("pack") or {}
    st.markdown(f"- **overall_status**: {pack_data.get('overall_status', '—')}")
    for case in pack_data.get("cases") or []:
      st.markdown(
        f"- **{case.get('case_id')}**: readiness={case.get('readiness_for_demo')} "
        f"({case.get('overall_status')})"
      )
    for issue in (pack_data.get("common_blocking_issues") or [])[:5]:
      st.caption(f"blocking: {issue}")
    for action in (pack_data.get("common_next_actions") or [])[:3]:
      st.caption(f"next: {action}")
  elif val_dir and val_dir.exists():
    st.caption(f"latest validation pack: {val_dir}")

  dl_dir = Path(str((cached_pack or {}).get("export", {}).get("output_dir", ""))) if cached_pack else val_dir
  if dl_dir and dl_dir.exists():
    for fname, mime in (
      ("three_case_validation_pack.md", "text/markdown"),
      ("three_case_validation_pack.json", "application/json"),
      ("three_case_validation_pack.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
      ("three_case_validation_manifest.json", "application/json"),
      ("demo_readiness_summary.md", "text/markdown"),
      ("cloud_readiness_summary.md", "text/markdown"),
    ):
      path = dl_dir / fname
      if path.exists():
        st.download_button(
          f"Download {fname}",
          data=path.read_bytes(),
          file_name=path.name,
          mime=mime,
          key=f"v8_export_val_{fname}",
        )

  st.markdown("#### 既存 artifact 参照")
  _artifact_link(find_latest_evidence_gap_path(root))
  _artifact_link(find_latest_gap_next_actions_dir(None if export_case == "all" else export_case, root))
  _artifact_link(find_latest_fixed_point_observation_dir(None if export_case == "all" else export_case, root))
  _artifact_link(find_latest_validation_pack_dir(root))
  _artifact_link(find_latest_manual_claim_refresh_dir(root))
  _artifact_link(find_latest_demo_readiness_dir(root))
  _artifact_link(find_latest_demo_polish_dir(None if export_case == "all" else export_case, root))
  _artifact_link(find_latest_large_shortlist_dir(None if export_case == "all" else export_case, root))
  brief_path = find_latest_strategic_watch_brief_path(root)
  _artifact_link(brief_path)
  if brief_path and brief_path.exists():
    md_path = brief_path.with_suffix(".md")
    if md_path.exists():
      st.download_button("Strategic Watch Brief Markdown", data=md_path.read_bytes(), file_name=md_path.name, mime="text/markdown", key="v8_export_brief_md")
  _artifact_link(find_latest_weekly_decision_cockpit_path(root))

  st.markdown("#### 今後追加予定")
  for item in (
    "Export Package への Validation Pack 同梱",
    "Watch Profile 自動反映（人手承認後）",
  ):
    st.markdown(f"- {item}")

  st.caption(f"export packages root: {get_v8_export_packages_dir(root)}")
  st.markdown(render_info_box(SAFETY_EXPORT_NOTICES[2]), unsafe_allow_html=True)
