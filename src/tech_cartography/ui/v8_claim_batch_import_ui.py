"""Claim batch import UI section (Phase 27Q.1)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from tech_cartography.runtime.v8_claim_batch_import_schema import VALID_DUPLICATE_MODES
from tech_cartography.services.v8_claim_batch_import import (
  apply_claim_batch_import,
  claim_batch_template_csv_text,
  validate_claim_batch_import,
)
from tech_cartography.services.v8_claim_batch_import_export import export_claim_batch_import_report
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box
from tech_cartography.ui.v8_text_rendering import render_next_action_card

STATE_V8_CLAIM_BATCH_RESULT = "v8_claim_batch_import_result"


def render_claim_batch_import_section(*, case_id: str, project_root: Path) -> None:
  st.markdown("#### 請求項CSV/Excelを一括投入 (Phase27Q.1)")
  st.markdown(
    render_caution_box(
      "<strong>claim 本文はユーザー提供のみ。</strong> システムは自動生成しません。"
      " JP/CN 特許の claim 本文は BigQuery から取得しません。"
    ),
    unsafe_allow_html=True,
  )

  st.download_button(
    "Top5 claim テンプレート CSV",
    data=claim_batch_template_csv_text().encode("utf-8"),
    file_name=f"top5_claims_template_{case_id}.csv",
    mime="text/csv",
    key="v8_claim_batch_dl_template",
  )

  duplicate_mode = st.selectbox(
    "既存行の扱い",
    options=list(VALID_DUPLICATE_MODES),
    index=0,
    format_func=lambda m: {"update": "上書き (update)", "skip": "スキップ (skip)", "append": "追加 (append)"}[m],
    key="v8_claim_batch_dup_mode",
  )
  if duplicate_mode == "update":
    st.caption("既存 manual_input を上書きする場合は内容を確認してから登録してください。")

  uploaded = st.file_uploader("CSV / Excel をアップロード", type=["csv", "xlsx"], key="v8_claim_batch_upload")

  if uploaded and st.button("プレビュー (validate)", key="v8_claim_batch_validate"):
    suffix = Path(uploaded.name).suffix or ".csv"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
      tmp.write(uploaded.getvalue())
      tmp_path = Path(tmp.name)
    report = validate_claim_batch_import(
      case_id=case_id,
      input_path=tmp_path,
      duplicate_mode=duplicate_mode,
      project_root=project_root,
    )
    out_dir = export_claim_batch_import_report(report, project_root=project_root)
    st.session_state[STATE_V8_CLAIM_BATCH_RESULT] = {**report.to_dict(), "export_dir": str(out_dir)}
    st.info(f"valid={report.valid_rows} / rejected={report.rejected_rows} / would_update={report.updated_rows}")

  cached = st.session_state.get(STATE_V8_CLAIM_BATCH_RESULT)
  if isinstance(cached, dict) and cached.get("case_id") == case_id:
    st.markdown(f"- **valid_rows**: {cached.get('valid_rows')}")
    st.markdown(f"- **rejected_rows**: {cached.get('rejected_rows')}")
    for row in (cached.get("rejected") or [])[:5]:
      st.caption(f"reject row {row.get('row_number')}: {row.get('reject_reason')}")

  if uploaded and st.button("claims_input.csv へ登録 (apply)", key="v8_claim_batch_apply", type="primary"):
    suffix = Path(uploaded.name).suffix or ".csv"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
      tmp.write(uploaded.getvalue())
      tmp_path = Path(tmp.name)
    report = apply_claim_batch_import(
      case_id=case_id,
      input_path=tmp_path,
      duplicate_mode=duplicate_mode,
      project_root=project_root,
    )
    out_dir = export_claim_batch_import_report(report, project_root=project_root)
    st.session_state[STATE_V8_CLAIM_BATCH_RESULT] = {**report.to_dict(), "export_dir": str(out_dir)}
    if report.applied_rows or report.updated_rows:
      st.success(f"登録完了 — applied={report.applied_rows} updated={report.updated_rows}")
      st.session_state["v8_claim_map_force_refresh"] = True
    else:
      st.warning("登録行がありません")

  st.markdown(
    render_next_action_card(
      "次にやること",
      [
        "Claim Map を再生成",
        "Evidence Map を再生成",
        "Gap / Next Actions を再生成",
      ],
    ),
    unsafe_allow_html=True,
  )
