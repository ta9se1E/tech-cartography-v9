"""Streamlit UI for user theme validation (Phase 24.4A / 24.4A.2 / 24.4A.3)."""

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
from tech_cartography.validation.manual_claims_evidence_builder import (
  SKELETON_CAUTION_JA,
  build_evidence_map_skeleton,
  evidence_map_output_dir,
  extract_claim_elements_from_text,
  load_manual_claims,
  save_evidence_map_skeleton,
)
from tech_cartography.validation.theme_validation import (
  MANUAL_CLAIMS_EDITOR_NOTICES,
  THEME_VALIDATION_SAFETY_MESSAGES,
  ThemeValidationCase,
  ThemeValidationRunResult,
  build_theme_id,
  build_theme_search_queries,
  create_manual_claims_template,
  has_manual_claims,
  manual_claims_json_path,
  parse_keyword_text,
  run_existing_outputs_validation,
  run_theme_patent_search,
  run_theme_validation_dry_run,
  save_theme_validation_result,
  save_user_manual_claims,
  stage_status_display_class,
)

STATE_THEME_VALIDATION_RESULT = "tc_theme_validation_result"
STATE_THEME_VALIDATION_CASE = "tc_theme_validation_case"
STATE_MANUAL_CLAIMS_LOADED = "tc_manual_claims_loaded"
STATE_CLAIM_ELEMENTS = "tc_claim_elements"
STATE_EVIDENCE_SKELETON = "tc_evidence_skeleton"

EVIDENCE_MAP_BUILDER_NOTICES = (
  "保存済みManual ClaimsからClaim Elementを抽出し、Evidence Map生成の準備を行います。",
  "この処理では外部APIは実行しません。",
  "論文候補やWebシグナルは確認候補であり、最終結論ではありません。",
  "本ツールはFTO、侵害、有効性判断、法的見解には使用しません。",
)


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
  theme_id_override: str,
  description: str,
  core_text: str,
  application_text: str,
  material_text: str,
  exclude_text: str,
  seed_text: str,
) -> ThemeValidationCase:
  core_keywords = parse_keyword_text(core_text)
  theme_id = build_theme_id(
    theme_name,
    theme_id_override=theme_id_override,
    core_keywords=core_keywords,
  )
  return ThemeValidationCase(
    theme_id=theme_id,
    theme_name=theme_name.strip(),
    description=description.strip(),
    core_keywords=core_keywords,
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

  fulltext_stage = next(
    (stage for stage in (result.stages or []) if stage.stage == "fulltext_or_manual_claims_available"),
    None,
  )
  evidence_stage = next(
    (stage for stage in (result.stages or []) if stage.stage == "evidence_map_available_or_buildable"),
    None,
  )
  if fulltext_stage and fulltext_stage.status == "pass" and evidence_stage and evidence_stage.status == "output_missing":
    st.markdown(
      render_info_box(
        "Manual Claimsは保存されました。次はClaim Element抽出 / Evidence Map生成ルートを実行する必要があります。"
      ),
      unsafe_allow_html=True,
    )


def render_manual_claims_editor(
  *,
  case: ThemeValidationCase,
  key_prefix: str,
  on_revalidate: bool = False,
) -> bool:
  """Render Manual Claims editor. Returns True if re-validation was requested."""
  st.markdown("#### Manual Claims入力 / Manual Claims Editor")
  for notice in MANUAL_CLAIMS_EDITOR_NOTICES:
    st.markdown(render_caution_box(notice), unsafe_allow_html=True)

  seeds = list(case.seed_publication_numbers)
  if seeds:
    publication_number = st.selectbox(
      "publication number",
      options=seeds,
      key=f"{key_prefix}_manual_claims_pub",
    )
  else:
    publication_number = st.text_input(
      "publication number",
      value="",
      key=f"{key_prefix}_manual_claims_pub_text",
      placeholder="JP2022090764A",
    )

  claims_text = st.text_area(
    "claims_text",
    value="",
    height=400,
    key=f"{key_prefix}_manual_claims_text",
    placeholder=(
      "公報原文の請求項をここに貼り付けてください。"
      "AIで作成した請求項や要約は入力しないでください。"
    ),
  )
  source_url = st.text_input(
    "source_url（任意）",
    value="",
    key=f"{key_prefix}_manual_claims_source_url",
    placeholder="Google Patents / J-PlatPat URL",
  )
  source_note = st.text_area(
    "source_note（任意）",
    value="",
    key=f"{key_prefix}_manual_claims_source_note",
    placeholder="Google Patentsから請求項1〜10をコピー",
  )
  language = st.selectbox(
    "language",
    options=["ja", "en", "other"],
    index=0,
    key=f"{key_prefix}_manual_claims_language",
  )

  root = _project_root()
  pub = str(publication_number or "").strip()
  existing_path = manual_claims_json_path(root, pub) if pub else None
  if existing_path and existing_path.exists():
    st.warning(f"既存ファイルがあります: {existing_path}")
    overwrite = st.checkbox(
      "既存の Manual Claims ファイルを上書きする",
      value=False,
      key=f"{key_prefix}_manual_claims_overwrite",
    )
  else:
    overwrite = True

  save_claims_clicked = st.button(
    "Manual Claimsを保存する",
    key=f"{key_prefix}_manual_claims_save",
  )
  revalidate_clicked = st.button(
    "保存後に既存outputs検証を再実行する",
    key=f"{key_prefix}_manual_claims_revalidate",
  )

  if save_claims_clicked:
    saved_path, warnings = save_user_manual_claims(
      publication_number=pub,
      claims_text=claims_text,
      output_dir=root,
      source_url=source_url,
      source_note=source_note,
      language=language,
      overwrite=overwrite,
    )
    for warning in warnings:
      if saved_path is None and "上書き" in warning:
        st.warning(warning)
      elif "短すぎる" in warning:
        st.warning(warning)
      else:
        st.error(warning)
    if saved_path is not None:
      st.markdown(render_success_box("Manual Claims を保存しました。"), unsafe_allow_html=True)
      st.code(str(saved_path))
      st.markdown(
        render_info_box(
          "保存後、「既存outputs検証を再実行する」を押すと Stage 2（fulltext_or_manual_claims_available）が pass になるか確認できます。"
        ),
        unsafe_allow_html=True,
      )

  if revalidate_clicked or on_revalidate:
    result = run_existing_outputs_validation(case, root)
    st.session_state[STATE_THEME_VALIDATION_RESULT] = result
    fulltext_stage = next(
      (stage for stage in result.stages if stage.stage == "fulltext_or_manual_claims_available"),
      None,
    )
    if fulltext_stage and fulltext_stage.status == "pass":
      st.markdown(render_success_box("Stage 2（fulltext_or_manual_claims_available）が pass になりました。"), unsafe_allow_html=True)
    else:
      st.warning("Stage 2 はまだ pass ではありません。Manual Claims の保存内容を確認してください。")
    evidence_stage = next(
      (stage for stage in result.stages if stage.stage == "evidence_map_available_or_buildable"),
      None,
    )
    if evidence_stage and evidence_stage.status == "output_missing":
      st.markdown(
        render_info_box(
          "Manual Claimsは保存されました。次はClaim Element抽出 / Evidence Map生成ルートを実行する必要があります。"
        ),
        unsafe_allow_html=True,
      )
    return True
  return False


def _default_publication_with_manual_claims(case: ThemeValidationCase, root: Path) -> str:
  for pub in case.seed_publication_numbers:
    if has_manual_claims(pub, root)[0]:
      return pub
  return case.seed_publication_numbers[0] if case.seed_publication_numbers else ""


def _show_stage_delta(result: ThemeValidationRunResult | None) -> None:
  if result is None:
    return
  stage_map = {stage.stage: stage for stage in result.stages}
  for label, key in (
    ("Stage 2", "fulltext_or_manual_claims_available"),
    ("Stage 3", "evidence_map_available_or_buildable"),
    ("Stage 4", "paper_candidates_available"),
  ):
    stage = stage_map.get(key)
    if stage:
      st.caption(f"{label} (`{key}`): **{stage.status}** — {stage.reason}")


def render_evidence_map_builder(
  *,
  case: ThemeValidationCase,
  key_prefix: str,
) -> None:
  st.markdown("#### Evidence Map生成準備 / Evidence Map Builder")
  for notice in EVIDENCE_MAP_BUILDER_NOTICES:
    st.markdown(render_caution_box(notice), unsafe_allow_html=True)

  root = _project_root()
  seeds = list(case.seed_publication_numbers)
  default_pub = _default_publication_with_manual_claims(case, root)
  if seeds:
    default_index = seeds.index(default_pub) if default_pub in seeds else 0
    publication_number = st.selectbox(
      "publication number",
      options=seeds,
      index=default_index,
      key=f"{key_prefix}_evidence_pub",
    )
  else:
    publication_number = st.text_input(
      "publication number",
      value=default_pub,
      key=f"{key_prefix}_evidence_pub_text",
      placeholder="JP2022090764A",
    )

  pub = str(publication_number or "").strip()
  claims_path = manual_claims_json_path(root, pub) if pub else None
  if claims_path and claims_path.exists():
    st.caption(f"manual claims file: `{claims_path}`")
  else:
    st.warning("Manual Claims ファイルが見つかりません。先に Manual Claims Editor で保存してください。")

  evidence_map_mode = st.selectbox(
    "evidence map mode",
    options=["local_skeleton", "query_plan_only"],
    index=0,
    key=f"{key_prefix}_evidence_mode",
  )

  load_clicked = st.button("Manual Claimsを読み込む", key=f"{key_prefix}_evidence_load")
  extract_clicked = st.button("Claim Elementを抽出する", key=f"{key_prefix}_evidence_extract")
  skeleton_clicked = st.button(
    "Evidence Map skeletonを生成する",
    key=f"{key_prefix}_evidence_skeleton",
  )
  revalidate_clicked = st.button(
    "生成後に既存outputs検証を再実行する",
    key=f"{key_prefix}_evidence_revalidate",
  )
  save_report_clicked = st.button(
    "検証レポートを保存する",
    key=f"{key_prefix}_evidence_save_report",
  )

  if load_clicked and pub:
    try:
      payload = load_manual_claims(pub, root)
      st.session_state[STATE_MANUAL_CLAIMS_LOADED] = payload
      st.markdown(render_success_box("Manual Claims を読み込みました。"), unsafe_allow_html=True)
      st.caption(f"claims_text length: {len(payload.get('claims_text', ''))}")
    except (FileNotFoundError, ValueError) as exc:
      st.error(str(exc))

  loaded = st.session_state.get(STATE_MANUAL_CLAIMS_LOADED)
  if extract_clicked and pub:
    try:
      if not loaded or str(loaded.get("publication_number", pub)) != pub:
        loaded = load_manual_claims(pub, root)
        st.session_state[STATE_MANUAL_CLAIMS_LOADED] = loaded
      elements = extract_claim_elements_from_text(pub, str(loaded.get("claims_text", "")))
      st.session_state[STATE_CLAIM_ELEMENTS] = [element.to_dict() for element in elements]
      st.markdown(
        render_success_box(f"Claim Element を {len(elements)} 件抽出しました（rule-based）。"),
        unsafe_allow_html=True,
      )
      if elements:
        render_small_table(
          pd.DataFrame([element.to_dict() for element in elements])[
            ["claim_number", "keywords", "material_terms", "process_terms", "property_terms"]
          ],
          height=240,
        )
    except (FileNotFoundError, ValueError) as exc:
      st.error(str(exc))

  if skeleton_clicked and pub and claims_path and claims_path.exists():
    try:
      skeleton = build_evidence_map_skeleton(pub, claims_path)
      if evidence_map_mode == "query_plan_only":
        skeleton.evidence_gaps.append("local_skeleton mode not selected; only query_plan artifacts saved.")
      paths = save_evidence_map_skeleton(skeleton, root)
      st.session_state[STATE_EVIDENCE_SKELETON] = skeleton.to_dict()
      st.session_state[STATE_CLAIM_ELEMENTS] = [element.to_dict() for element in skeleton.claim_elements]
      st.markdown(
        render_success_box("Manual ClaimsからClaim Element候補とEvidence Map skeletonを生成しました。"),
        unsafe_allow_html=True,
      )
      for label, path in paths.items():
        st.caption(f"{label}: {path}")
      st.markdown(render_info_box(SKELETON_CAUTION_JA), unsafe_allow_html=True)
      for message in (
        "次に論文候補を取得するにはOpenAlex等の外部API実行が必要です。",
        "次にWebシグナル候補を取得するにはTavily等の外部API実行が必要です。",
        "この段階では、論文・Webシグナルによる裏取りは未完了です。",
      ):
        st.markdown(render_info_box(message), unsafe_allow_html=True)
    except (FileNotFoundError, ValueError) as exc:
      st.error(str(exc))

  if revalidate_clicked:
    result = run_existing_outputs_validation(case, root)
    st.session_state[STATE_THEME_VALIDATION_RESULT] = result
    evidence_stage = next(
      (stage for stage in result.stages if stage.stage == "evidence_map_available_or_buildable"),
      None,
    )
    if evidence_stage and evidence_stage.status == "pass":
      st.markdown(
        render_success_box("Stage 3（evidence_map_available_or_buildable）が pass になりました。"),
        unsafe_allow_html=True,
      )
    else:
      st.warning("Stage 3 はまだ pass ではありません。Evidence Map skeleton の生成を確認してください。")
    _show_stage_delta(result)

  if save_report_clicked:
    result = st.session_state.get(STATE_THEME_VALIDATION_RESULT)
    if result is None:
      result = run_existing_outputs_validation(case, root)
      st.session_state[STATE_THEME_VALIDATION_RESULT] = result
    paths = save_theme_validation_result(
      result,
      root / "outputs" / "validation" / "theme_validation",
      project_root=root,
    )
    st.markdown(render_success_box("検証レポートを保存しました。"), unsafe_allow_html=True)
    for label, path in paths.items():
      st.caption(f"{label}: {path}")

  skeleton_json = evidence_map_output_dir(root, pub) / "evidence_map_skeleton.json" if pub else None
  if skeleton_json and skeleton_json.exists():
    st.caption(f"既存 skeleton: `{skeleton_json}`")


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
  core_text = st.text_area(
    "コアキーワード（カンマまたは改行区切り）",
    value="",
    key=f"{key_prefix}_core_keywords",
    placeholder="polymer film, heat treatment, crystallization",
  )
  auto_theme_id = build_theme_id(
    theme_name,
    core_keywords=parse_keyword_text(core_text),
  ) if theme_name.strip() else ""
  theme_id_value = st.text_input(
    "保存用テーマID",
    value=auto_theme_id,
    key=f"{key_prefix}_theme_id",
    help="検証レポートの保存フォルダ名です。短すぎるID（例: pan）は避け、テーマ内容が分かるIDを推奨します。",
    placeholder="pan_precursor_surface_internal_defects",
  )
  description = st.text_area("テーマ説明", value="", key=f"{key_prefix}_description")
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
    theme_id_override=theme_id_value,
    description=description,
    core_text=core_text,
    application_text=application_text,
    material_text=material_text,
    exclude_text=exclude_text,
    seed_text=seed_text,
  )
  st.session_state[STATE_THEME_VALIDATION_CASE] = case
  st.caption(f"theme_id: `{case.theme_id}`")

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

  render_manual_claims_editor(case=case, key_prefix=key_prefix)
  render_evidence_map_builder(case=case, key_prefix=key_prefix)

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
    paths = save_theme_validation_result(
      result,
      _project_root() / "outputs" / "validation" / "theme_validation",
      project_root=_project_root(),
    )
    st.markdown(render_success_box("検証レポートを保存しました。"), unsafe_allow_html=True)
    for label, path in paths.items():
      st.caption(f"{label}: {path}")

  render_theme_validation_stage_matrix(st.session_state.get(STATE_THEME_VALIDATION_RESULT))
