"""BigQuery admin UI section (Phase 27Q.1)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from tech_cartography.auth.basic_auth import is_login_required
from tech_cartography.runtime.v8_research_theme_schema import ResearchThemeProfile
from tech_cartography.services.v8_bigquery_runner import run_bigquery_candidate_search
from tech_cartography.services.v8_bigquery_safety import BigQuerySafetyConfig, can_show_bigquery_admin
from tech_cartography.services.v8_research_theme_defaults import load_research_theme_profile
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_warning_box
from tech_cartography.ui.login_ui import can_use_admin_features

STATE_V8_BQ_MANIFEST = "v8_last_bigquery_manifest"


def render_bigquery_admin_section(*, case_id: str, project_root: Path) -> None:
  st.markdown("#### BigQuery候補抽出 (Phase27Q.1)")
  cfg = BigQuerySafetyConfig.from_env()
  st.markdown(
    render_caution_box(
      "この公開デモでは、BigQueryの直接実行は通常OFFです。"
      " 管理者環境でのみ、dry run と max bytes billed 付きで実行できます。"
      " JP/CN claim 本文は BigQuery から取得しません — 候補メタデータ抽出のみ。"
    ),
    unsafe_allow_html=True,
  )
  st.caption(
    f"ENABLE_BIGQUERY_RUN={cfg.enable_bigquery_run} / "
    f"SHOW_BIGQUERY_ADMIN={cfg.show_bigquery_admin} / "
    f"BIGQUERY_ALLOW_EXECUTE={cfg.bigquery_allow_execute}"
  )

  profile = load_research_theme_profile(case_id, project_root)

  if st.button("SQL を生成", key="v8_bq_generate_sql", type="primary"):
    try:
      manifest = run_bigquery_candidate_search(
        case_id=case_id,
        theme_profile=profile,
        mode="generate_sql",
        project_root=project_root,
        config=cfg,
      )
      st.session_state[STATE_V8_BQ_MANIFEST] = manifest.to_dict()
      st.success("SQL 生成完了")
    except Exception as exc:
      st.error(str(exc))

  manifest = st.session_state.get(STATE_V8_BQ_MANIFEST)
  if isinstance(manifest, dict):
    sql_path = Path(str(manifest.get("sql_path", "")))
    if sql_path.exists():
      st.download_button(
        "generated_query.sql をダウンロード",
        data=sql_path.read_bytes(),
        file_name="generated_query.sql",
        mime="text/plain",
        key="v8_bq_dl_sql",
      )
      st.caption(f"output_dir: {manifest.get('output_dir')}")

  st.info(
    "通常フロー: SQL をダウンロード → BigQuery Console で実行 → "
    "結果 CSV を「1000件候補CSV/Excel」として取り込んでください。"
  )

  admin_ok = (
    can_show_bigquery_admin(cfg)
    and is_login_required()
    and can_use_admin_features()
  )
  if not admin_ok:
    st.caption("Dry Run / Execute は管理者 + ENABLE_BIGQUERY_RUN=true のときのみ表示されます。")
    return

  st.markdown(render_warning_box("<strong>管理者 BigQuery 実行</strong> — コストに注意"), unsafe_allow_html=True)
  if st.button("Dry Run", key="v8_bq_dry_run"):
    try:
      manifest = run_bigquery_candidate_search(
        case_id=case_id,
        theme_profile=profile,
        mode="dry_run",
        project_root=project_root,
        config=cfg,
      )
      st.session_state[STATE_V8_BQ_MANIFEST] = manifest.to_dict()
      st.success("Dry Run 完了")
    except PermissionError as exc:
      st.error(str(exc))
    except Exception as exc:
      st.error(str(exc))

  if st.button("Execute → Large Candidate CSV", key="v8_bq_execute"):
    try:
      manifest = run_bigquery_candidate_search(
        case_id=case_id,
        theme_profile=profile,
        mode="execute",
        project_root=project_root,
        config=cfg,
      )
      st.session_state[STATE_V8_BQ_MANIFEST] = manifest.to_dict()
      st.success("Execute 完了 — source_candidates_large.csv 生成")
    except PermissionError as exc:
      st.error(str(exc))
    except Exception as exc:
      st.error(str(exc))

  if isinstance(manifest, dict) and manifest.get("large_candidate_csv_path"):
    lc_path = Path(str(manifest["large_candidate_csv_path"]))
    if lc_path.exists():
      st.download_button(
        "source_candidates_large.csv",
        data=lc_path.read_bytes(),
        file_name=lc_path.name,
        mime="text/csv",
        key="v8_bq_dl_lc",
      )
