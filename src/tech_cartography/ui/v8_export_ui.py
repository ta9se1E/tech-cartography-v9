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
from tech_cartography.runtime.v8_one_case_demo_schema import DEFAULT_ONE_CASE_INPUT_CSV, DEFAULT_ONE_CASE_ID
from tech_cartography.services.v8_one_case_demo_e2e import assess_one_case_demo_status
from tech_cartography.services.v8_cloud_run_readiness import build_cloud_run_readiness_report
from tech_cartography.services.v8_cloud_run_readiness_export import (
  export_cloud_run_readiness,
  find_latest_cloud_run_readiness_dir,
)
from tech_cartography.services.v8_demo_polish import build_demo_polish_report
from tech_cartography.services.v8_demo_polish_export import export_demo_polish, find_latest_demo_polish_dir
from tech_cartography.services.v8_bigquery_export import get_bigquery_runs_dir
from tech_cartography.services.v8_claim_batch_import import claim_batch_template_csv_text
from tech_cartography.services.v8_claim_batch_import_export import get_claim_batch_import_dir
from tech_cartography.services.v8_research_theme_defaults import load_research_theme_profile, research_theme_profile_path
from tech_cartography.services.v8_export_package import build_export_package, get_v8_export_packages_dir, records_to_csv_text, records_to_markdown
from tech_cartography.services.v8_large_candidate_shortlist import (
  find_latest_large_shortlist_dir,
  find_latest_large_shortlist_dirs_for_all_cases,
  safe_find_latest_large_shortlist_dir,
)
from tech_cartography.services.v8_manual_claim_refresh_export import find_latest_manual_claim_refresh_dir
from tech_cartography.services.v8_patent_shortlist_export import find_latest_patent_shortlist_dir
from tech_cartography.services.v8_sources_repository import filter_sources_table, load_sources_table, resolve_case_name
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box
from tech_cartography.ui.v8_input_ui import get_v8_input_state
from tech_cartography.ui.v8_executive_summary_ui import render_export_executive_summary
from tech_cartography.ui.v8_judge_mode_ui import render_judge_conclusion_card, render_judge_next_tab_hint
from tech_cartography.ui.v8_tab_config import STATE_V8_SELECTED_CASE, V8_CASE_SAMPLES


def _export_case_filter(export_case: str) -> str | None:
  return None if export_case == "all" else export_case


def _primary_case_id(export_case: str) -> str:
  if export_case != "all":
    return export_case
  return V8_CASE_SAMPLES[0]["case_id"]


def _artifact_link(path: Path | None, *, label: str = "") -> None:
  prefix = f"{label}: " if label else ""
  if path and path.exists():
    st.caption(f"{prefix}{path}")
  else:
    st.caption(f"{prefix}（未生成）")


def _render_large_candidate_pack_downloads(lc_case: str, lc_dir: Path, *, key_prefix: str) -> None:
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
  else:
    st.info(f"{lc_case}: manifest 未生成 — artifact missing（true zero ではありません）")

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
        key=f"v8_export_re_{key_prefix}_{fname}",
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
        key=f"v8_export_lc_{key_prefix}_{fname}",
      )


def render_v8_export_tab(*, project_root: Path | str) -> None:
  root = Path(project_root)
  render_judge_conclusion_card("export")
  render_judge_next_tab_hint("export")

  state = get_v8_input_state()
  default_case = str(state.get("selected_case_id") or st.session_state.get(STATE_V8_SELECTED_CASE) or "").strip()

  st.markdown("### Export｜共有レポート")
  render_export_executive_summary()

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

  with st.expander("Sources Export・Export Package（詳細）", expanded=False):
    st.markdown(
      render_caution_box(
        "candidate information only / human review required。"
        " FTO、侵害、有効性判断、法的結論は行いません。"
        " secret 値は表示しません。"
      ),
      unsafe_allow_html=True,
    )
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
      with st.expander("直近 Export Package（artifact path）", expanded=False):
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

  st.markdown("#### 共有レポート（主要 artifact）")
  st.markdown("##### Patent Shortlist")
  shortlist_dir = find_latest_patent_shortlist_dir(
    _export_case_filter(export_case),
    root,
  )
  if shortlist_dir and shortlist_dir.exists():
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

  st.markdown("##### Claim Map")
  claim_map_dir = find_latest_claim_map_dir(
    _export_case_filter(export_case),
    root,
  )
  if claim_map_dir and claim_map_dir.exists():
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

  st.markdown("##### Evidence Map（裏取り候補）")
  evidence_map_dir = find_latest_evidence_map_dir(
    _export_case_filter(export_case),
    root,
  )
  if evidence_map_dir and evidence_map_dir.exists():
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

  st.markdown("##### Gap / Next Actions（未確認事項）")
  gap_dir = find_latest_gap_next_actions_dir(
    _export_case_filter(export_case),
    root,
  )
  if gap_dir and gap_dir.exists():
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

  st.markdown("##### 定点観測（Digest preview）")
  fp_dir = find_latest_fixed_point_observation_dir(
    _export_case_filter(export_case),
    root,
  )
  if fp_dir and fp_dir.exists():
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

  with st.expander("詳細 Export・開発者向け Pack", expanded=False):
    st.markdown(render_info_box(FIXED_POINT_OBSERVATION_NOTE), unsafe_allow_html=True)
    st.markdown("#### Large Candidate Pack (Phase27J.0 / 27J.1)")
    st.caption(
      "1000件は母集団。Top5 のみ Deep Dive。Ranking explanation は読む優先度の説明であり、"
      "技術的正しさ・特許価値・法的価値ではありません。"
      " Cloud Build / 外部 API / BigQuery 実行は行いません。"
    )
    if export_case == "all":
      all_packs = find_latest_large_shortlist_dirs_for_all_cases(root)
      if not all_packs:
        st.info(
          "Large Candidate Pack 未生成 — artifact missing（true zero ではありません）。"
          " 入力タブで取り込み後、読むべき特許で Top5 を生成してください。"
        )
      else:
        st.caption(f"全 {len(all_packs)} 案件に Large Candidate Pack あり（最新順）")
        for lc_case, lc_dir in sorted(all_packs, key=lambda item: item[1].stat().st_mtime, reverse=True):
          st.markdown(f"##### {lc_case}")
          _render_large_candidate_pack_downloads(lc_case, lc_dir, key_prefix=lc_case)
    else:
      lc_dir = find_latest_large_shortlist_dir(export_case, root)
      if lc_dir and lc_dir.exists():
        _render_large_candidate_pack_downloads(export_case, lc_dir, key_prefix=export_case)
      else:
        st.info(
          "Large Candidate Pack 未生成 — artifact missing（true zero ではありません）。"
          " 入力タブで取り込み後、読むべき特許で Top5 を生成してください。"
        )

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
      "Demo Polish Pack / Demo Readiness Pack / Cloud Run Readiness Pack / One Case Real Demo E2E"
    )

    st.markdown("#### One Case Real Demo E2E (Phase27N.5)")
    st.caption(
      f"Case 1 ({DEFAULT_ONE_CASE_ID}) — 実在 CSV で E2E。"
      " claim 自動生成なし / Cloud Build・Cloud Run deploy なし。"
    )
    try:
      oc_status = assess_one_case_demo_status(case_id=DEFAULT_ONE_CASE_ID, project_root=root)
      st.markdown(f"- **overall_status**: {oc_status.overall_status}")
      st.markdown(f"- **input_csv_exists**: {oc_status.input_csv_exists}")
      if not oc_status.input_csv_exists:
        st.warning(
          f"実在特許 CSV を配置してください: `{DEFAULT_ONE_CASE_INPUT_CSV}` — "
          "入力タブまたは docs/one_case_real_demo_runbook.md を参照"
        )
      if oc_status.top5_count is not None:
        st.markdown(f"- **top5_count**: {oc_status.top5_count}")
      if oc_status.top5_publication_numbers:
        st.markdown(f"- **top5_publication_numbers**: {', '.join(oc_status.top5_publication_numbers)}")
      st.markdown(f"- **manual_claim_count**: {oc_status.manual_claim_count}")
      st.markdown(f"- **demo_readiness_status**: {oc_status.demo_readiness_status or '—'}")
      st.caption(f"next: {oc_status.next_user_action}")
      if oc_status.manual_claim_count < 35 and oc_status.top5_publication_numbers:
        st.info(
          "Claim Map タブで Top5 全件の claim 本文を手動投入してください（Case 1 は35請求項）。"
          " システムは claim を生成しません。"
        )
      if oc_status.demo_polish_pack_path:
        st.caption(f"demo polish: {oc_status.demo_polish_pack_path}")
    except Exception as exc:
      st.warning(f"One Case E2E 状態取得エラー: {exc}")

    st.markdown("#### Cloud Run Readiness Pack (Phase27N)")
    st.caption(
      "Cloud Run deploy 前の構成点検 — Secret 値は表示しません。"
      " この Phase では Cloud Build / Cloud Run deploy を実行しません。"
    )
    if st.button("Generate Cloud Run Readiness Pack", key="v8_export_cloud_run_readiness", type="primary"):
      cr_report = build_cloud_run_readiness_report(project_root=root)
      cr_export = export_cloud_run_readiness(cr_report, project_root=root)
      st.session_state["v8_last_cloud_run_readiness"] = {
        "report": cr_report.to_dict(),
        "export": cr_export.to_dict(),
      }
      st.success(f"Cloud Run Readiness Pack 生成 — overall={cr_report.overall_status}")

    cached_cr = st.session_state.get("v8_last_cloud_run_readiness")
    cr_dir = find_latest_cloud_run_readiness_dir(root)
    if isinstance(cached_cr, dict):
      cr_report = cached_cr.get("report") or {}
      st.markdown(f"- **overall_status**: {cr_report.get('overall_status', '—')}")
      st.markdown(f"- **app_entrypoint**: {cr_report.get('app_entrypoint_status', '—')}")
      st.markdown(f"- **streamlit_command**: {cr_report.get('streamlit_command_status', '—')}")
      st.markdown(f"- **demo_data**: {cr_report.get('demo_data_status', '—')}")
      st.markdown(f"- **output_artifact_policy**: {cr_report.get('output_artifact_policy_status', '—')}")
      blockers = cr_report.get("known_blockers") or []
      if blockers:
        st.markdown("- **known_blockers**:")
        for b in blockers[:5]:
          st.caption(f"  - {b}")
      else:
        st.caption("known_blockers: (none)")
      cr_dl_dir = Path(str((cached_cr.get("export") or {}).get("output_dir", "")))
    elif cr_dir and cr_dir.exists():
      st.caption(f"latest cloud run readiness: {cr_dir}")
      cr_dl_dir = cr_dir
    else:
      st.caption("Cloud Run Readiness Pack 未生成")
      cr_dl_dir = None

    if cr_dl_dir and cr_dl_dir.exists():
      for fname, mime in (
        ("cloud_run_readiness_report.md", "text/markdown"),
        ("cloud_run_readiness_report.json", "application/json"),
        ("deploy_preparation_checklist.md", "text/markdown"),
        ("demo_data_checklist.md", "text/markdown"),
        ("operator_checklist.md", "text/markdown"),
        ("env_var_template.md", "text/markdown"),
        ("artifact_policy.md", "text/markdown"),
        ("cloud_run_readiness_manifest.json", "application/json"),
      ):
        path = cr_dl_dir / fname
        if path.exists():
          st.download_button(
            f"Download {fname}",
            data=path.read_bytes(),
            file_name=path.name,
            mime=mime,
            key=f"v8_export_cr_{fname}",
          )

    st.markdown("#### Demo Polish Pack (Phase27L)")
    st.caption(
      "Evidence Map / Gap / Next Actions をデモ向けに要約。"
      " Evidence Map is not proof / Gap is not invalidity / weakness。"
      " Cloud Build / メール送信 / Scheduler 起動は行いません。"
    )
    polish_case = _primary_case_id(export_case)
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
      _export_case_filter(export_case),
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

    st.markdown("#### Phase27Q.1 — Research Theme / BigQuery / Claim Batch")
    st.caption("BigQuery 実行 artifact と claim batch import report — Secret 値は表示しません。")
    q_case = export_case if export_case != "all" else V8_CASE_SAMPLES[0]["case_id"]
    theme_path = research_theme_profile_path(q_case, root)
    if theme_path.exists():
      st.download_button(
        "Research Theme Profile JSON",
        data=theme_path.read_bytes(),
        file_name=theme_path.name,
        mime="application/json",
        key="v8_export_theme_profile",
      )
    bq_base = get_bigquery_runs_dir(root) / q_case
    if bq_base.is_dir():
      packs = sorted((p for p in bq_base.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True)
      if packs:
        latest_bq = packs[0]
        for fname, mime in (
          ("generated_query.sql", "text/plain"),
          ("dry_run_report.json", "application/json"),
          ("dry_run_report.md", "text/markdown"),
          ("bigquery_results_raw.csv", "text/csv"),
          ("source_candidates_large.csv", "text/csv"),
          ("query_manifest.json", "application/json"),
        ):
          path = latest_bq / fname
          if path.exists():
            st.download_button(f"Download {fname}", data=path.read_bytes(), file_name=path.name, mime=mime, key=f"v8_export_bq_{fname}")
    else:
      st.caption("BigQuery run artifact 未生成 — 入力タブで SQL 生成してください。")

    batch_base = get_claim_batch_import_dir(root) / q_case
    if batch_base.is_dir():
      batch_dirs = sorted(
        (p for p in batch_base.iterdir() if p.is_dir()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
      )
      if batch_dirs:
        latest_batch = batch_dirs[0]
        for fname, mime in (
          ("claim_batch_import_report.json", "application/json"),
          ("claim_batch_import_report.md", "text/markdown"),
          ("claim_batch_import_preview.csv", "text/csv"),
          ("rejected_rows.csv", "text/csv"),
        ):
          path = latest_batch / fname
          if path.exists():
            st.download_button(
              f"Download {fname}",
              data=path.read_bytes(),
              file_name=path.name,
              mime=mime,
              key=f"v8_export_batch_{fname}",
            )
      else:
        st.caption("Claim batch import 履歴はまだ出力がありません。")
    else:
      st.caption("Claim batch import 履歴はまだ出力がありません。")
    st.download_button(
      "Top5 claim template CSV",
      data=claim_batch_template_csv_text().encode("utf-8"),
      file_name=f"top5_claims_template_{q_case}.csv",
      mime="text/csv",
      key="v8_export_claim_template",
    )

    st.markdown("#### 既存 artifact 参照")
    _artifact_link(find_latest_evidence_gap_path(root), label="evidence_gap")
    _artifact_link(
      find_latest_gap_next_actions_dir(_export_case_filter(export_case), root),
      label="gap_next_actions",
    )
    _artifact_link(
      find_latest_fixed_point_observation_dir(_export_case_filter(export_case), root),
      label="fixed_point_observation",
    )
    _artifact_link(find_latest_validation_pack_dir(root), label="validation_pack")
    _artifact_link(find_latest_manual_claim_refresh_dir(root), label="manual_claim_refresh")
    _artifact_link(find_latest_demo_readiness_dir(root), label="demo_readiness")
    _artifact_link(
      find_latest_demo_polish_dir(_export_case_filter(export_case), root),
      label="demo_polish",
    )
    _artifact_link(
      safe_find_latest_large_shortlist_dir(_export_case_filter(export_case), root),
      label="large_shortlist",
    )
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
