"""Streamlit UI for user theme validation (Phase 24.4A)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from tech_cartography.ui.easy_japanese_ui import (
  render_caution_box,
  render_info_box,
  render_small_table,
  render_success_box,
  render_warning_box,
)
from tech_cartography.validation.theme_validation import (
  THEME_VALIDATION_SAFETY_MESSAGES,
  ThemeValidationCase,
  ThemeValidationRunResult,
  build_theme_search_queries,
  create_manual_claims_template,
  parse_keyword_text,
  run_existing_outputs_validation,
  run_theme_patent_search,
  run_theme_validation_dry_run,
  save_theme_validation_result,
  slugify_theme_id,
  stage_status_display_class,
)

STATE_THEME_VALIDATION_RESULT = "tc_theme_validation_result"
STATE_THEME_VALIDATION_CASE = "tc_theme_validation_case"


def _project_root() -> Path:
  return Path(__file__).resolve().parents[3]


def _validation_output_dir(theme_id: str) -> Path:
  return _project_root() / "outputs" / "validation" / "theme_validation" / theme_id


def render_theme_validation_safety_messages() -> None:
  st.markdown("#### 安全上の注意")
  for message in THEME_VALIDATION_SAFETY_MESSAGES:
    st.markdown(render_caution_box(message), unsafe_allow_html=True)


def _build_case_from_inputs(
  *,
  theme_name: str,
  description: str,
  core_text: str,
  application_text: str,
  material_text: str,
  exclude_text: str,
  seed_text: str,
) -> ThemeValidationCase:
  theme_id = slugify_theme_id(theme_name)
  return ThemeValidationCase(
    theme_id=theme_id,
    theme_name=theme_name.strip(),
    description=description.strip(),
    core_keywords=parse_keyword_text(core_text),
    application_keywords=parse_keyword_text(application_text),
    material_or_process_keywords=parse_keyword_text(material_text),
    exclude_keywords=parse_keyword_text(exclude_text),
    seed_publication_numbers=parse_keyword_text(seed_text),
    validation_goal="user_theme_validation_ui",
  )


def _stage_matrix_dataframe(result: ThemeValidationRunResult) -> pd.DataFrame:
  rows: list[dict[str, Any]] = []
  for stage in result.stages:
    rows.append(
      {
        "stage": stage.stage,
        "status": stage.status,
        "reason": stage.reason,
        "next_action": stage.next_action,
        "output_path": stage.output_path,
        "display_class": stage_status_display_class(stage.status),
      },
    )
  return pd.DataFrame(rows)


def render_theme_validation_stage_matrix(result: ThemeValidationRunResult | None) -> None:
  if result is None:
    st.info("検証を実行すると Stage Matrix が表示されます。")
    return

  st.markdown(f"**mode:** `{result.mode}` / **created_at:** `{result.created_at}`")
  df = _stage_matrix_dataframe(result)
  if df.empty:
    st.info("Stage データがありません。")
    return

  def _color_rows(row: pd.Series) -> list[str]:
    cls = str(row.get("display_class", "info"))
    palette = {
      "success": "background-color: #dcfce7",
      "caution": "background-color: #fef9c3",
      "warning": "background-color: #fee2e2",
      "info": "background-color: #e0f2fe",
    }
    style = palette.get(cls, "")
    return [style] * len(row)

  display_df = df.drop(columns=["display_class"], errors="ignore")
  try:
    styled = display_df.style.apply(_color_rows, axis=1)
    st.dataframe(styled, width="stretch", hide_index=True)
  except Exception:
    render_small_table(display_df, height=420)

  if result.search_queries:
    st.markdown("**検索クエリ案**")
    for query in result.search_queries:
      st.code(query)

  if result.patent_candidates:
    st.markdown("**特許候補（外部検索）**")
    render_small_table(pd.DataFrame(result.patent_candidates).head(5), height=220)

  if result.warnings:
    for warning in result.warnings:
      st.markdown(render_info_box(warning), unsafe_allow_html=True)


def render_theme_validation_intro_card() -> None:
  st.markdown(
    render_info_box(
      "別テーマ検証: 炭素繊維以外のテーマでも、キーワード入力から検索計画・既存 outputs 検証まで確認できます。"
      " トップレベルタブ「別テーマ検証」から操作してください。"
    ),
    unsafe_allow_html=True,
  )


def render_theme_validation_tab_intro() -> None:
  st.markdown(
    render_info_box(
      "ここでは、炭素繊維以外の独自テーマでもTech Cartographyの流れが動くかを確認できます。"
    ),
    unsafe_allow_html=True,
  )
  st.markdown(
    render_caution_box(
      "まずはdry-runで検索計画だけを作成してください。外部APIは実行されません。"
    ),
    unsafe_allow_html=True,
  )
  st.markdown(
    render_caution_box("社外秘・未公開情報を入力しないでください。"),
    unsafe_allow_html=True,
  )


def render_theme_validation_section(*, key_prefix: str = "theme_validation") -> None:
  st.subheader("別テーマ検証 / Theme Validation")
  render_theme_validation_tab_intro()
  render_theme_validation_safety_messages()

  theme_name = st.text_input("テーマ名", value="", key=f"{key_prefix}_theme_name")
  description = st.text_area("テーマ説明", value="", key=f"{key_prefix}_description")
  core_text = st.text_area(
    "コアキーワード（カンマまたは改行区切り）",
    value="",
    key=f"{key_prefix}_core_keywords",
    placeholder="polymer film, heat treatment, crystallization",
  )
  application_text = st.text_area(
    "用途キーワード",
    value="",
    key=f"{key_prefix}_application_keywords",
    placeholder="battery separator, packaging film",
  )
  material_text = st.text_area(
    "材料・プロセスキーワード",
    value="",
    key=f"{key_prefix}_material_keywords",
  )
  exclude_text = st.text_area(
    "除外キーワード",
    value="",
    key=f"{key_prefix}_exclude_keywords",
    placeholder="medical film, photography",
  )
  seed_text = st.text_area(
    "seed publication numbers（カンマ区切り・任意）",
    value="",
    key=f"{key_prefix}_seed_publications",
    placeholder="US-12565719-B2",
  )

  if not theme_name.strip():
    st.caption("テーマ名を入力すると操作ボタンが有効になります。")
    return

  case = _build_case_from_inputs(
    theme_name=theme_name,
    description=description,
    core_text=core_text,
    application_text=application_text,
    material_text=material_text,
    exclude_text=exclude_text,
    seed_text=seed_text,
  )
  st.session_state[STATE_THEME_VALIDATION_CASE] = case

  col_a, col_b, col_c = st.columns(3)
  with col_a:
    dry_run_clicked = st.button("A. 検索計画を作成する（dry-run）", key=f"{key_prefix}_dry_run")
  with col_b:
    existing_clicked = st.button("B. 既存outputsだけで検証する", key=f"{key_prefix}_existing")
  with col_c:
    template_clicked = st.button("D. Manual Claimsテンプレートを作成する", key=f"{key_prefix}_template")

  st.markdown(
    render_warning_box(
      "C. 特許候補検索を実行する場合、入力キーワードが外部APIまたはBigQueryに送信される可能性があります。"
      " 社外秘情報を入れないでください。"
    ),
    unsafe_allow_html=True,
  )
  consent = st.checkbox(
    "外部検索を実行することに同意します",
    value=False,
    key=f"{key_prefix}_external_consent",
  )
  max_patents = st.number_input("max_patents", min_value=1, max_value=5, value=5, step=1, key=f"{key_prefix}_max_patents")
  external_clicked = st.button(
    "C. 特許候補検索を実行する",
    key=f"{key_prefix}_external_search",
    disabled=not consent,
  )

  save_clicked = st.button("E. 検証レポートを保存する", key=f"{key_prefix}_save_report")

  result: ThemeValidationRunResult | None = st.session_state.get(STATE_THEME_VALIDATION_RESULT)

  if dry_run_clicked:
    result = run_theme_validation_dry_run(case)
    st.session_state[STATE_THEME_VALIDATION_RESULT] = result
    st.markdown(render_success_box("dry-run 完了（外部API未実行）"), unsafe_allow_html=True)

  if existing_clicked:
    result = run_existing_outputs_validation(case, _project_root())
    st.session_state[STATE_THEME_VALIDATION_RESULT] = result
    st.markdown(render_success_box("既存 outputs 検証完了（外部API未実行）"), unsafe_allow_html=True)

  if template_clicked:
    seeds = case.seed_publication_numbers
    if not seeds:
      st.warning("seed publication number を指定してください。")
    else:
      out_dir = _validation_output_dir(case.theme_id)
      created: list[str] = []
      for pub in seeds:
        path = create_manual_claims_template(pub, out_dir, project_root=_project_root())
        created.append(str(path))
      st.markdown(
        render_success_box(
          "Manual Claims テンプレートを作成しました。"
          " claims_text に Claims を貼り付け、.json として保存すると次段階に進めます。"
        ),
        unsafe_allow_html=True,
      )
      for path in created:
        st.code(path)

  if external_clicked:
    if not consent:
      st.warning("外部検索の同意チェックが必要です。")
    else:
      result = run_theme_patent_search(
        case,
        project_root=_project_root(),
        max_patents=int(max_patents),
        execute=True,
      )
      st.session_state[STATE_THEME_VALIDATION_RESULT] = result
      patent_stage = next((s for s in result.stages if s.stage == "patent_candidates_available"), None)
      if patent_stage and patent_stage.status == "external_search_not_configured":
        st.warning("external_search_not_configured: BigQuery 未設定のため検索計画のみ保存しました。")
      else:
        st.markdown(render_success_box("外部検索フローを実行しました。"), unsafe_allow_html=True)

  if save_clicked:
    result = st.session_state.get(STATE_THEME_VALIDATION_RESULT)
    if result is None:
      result = run_theme_validation_dry_run(case)
      st.session_state[STATE_THEME_VALIDATION_RESULT] = result
    paths = save_theme_validation_result(result, _project_root() / "outputs" / "validation" / "theme_validation")
    st.markdown(render_success_box("検証レポートを保存しました。"), unsafe_allow_html=True)
    for label, path in paths.items():
      st.caption(f"{label}: {path}")

  render_theme_validation_stage_matrix(st.session_state.get(STATE_THEME_VALIDATION_RESULT))
