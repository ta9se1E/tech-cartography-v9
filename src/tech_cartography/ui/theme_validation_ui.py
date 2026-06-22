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
from tech_cartography.ui.demo_safe_ui import format_display_path, is_developer_view
from tech_cartography.ui.analyst_mode_ui import (
  ANALYST_INPUT_KEY_PREFIX,
  build_final_validation_from_case,
  compute_analyst_workflow_snapshot,
  pan_theme_session_state_updates,
)
from tech_cartography.validation.seed_progress import (
  inspect_seed_progress_many,
  preferred_publication_for_evidence_map,
  preferred_publication_for_manual_claims,
  progress_to_display_dataframe,
  save_seed_progress_report,
  summarize_seed_progress_actions,
)
from tech_cartography.validation.manual_claims_evidence_builder import (
  SKELETON_CAUTION_JA,
  build_evidence_map_skeleton,
  evidence_map_output_dir,
  extract_claim_elements_from_text,
  load_manual_claims,
  save_evidence_map_skeleton,
)
from tech_cartography.validation.end_to_end_chain import (
  CHAIN_CAUTION,
  EndToEndChainConfig,
  EndToEndChainResult,
  end_to_end_output_dir,
  inspect_end_to_end_status,
  run_digest_step,
  run_link_candidate_step,
  run_paper_candidate_step,
  run_selected_chain_steps,
  run_strategic_watch_step,
  run_web_signal_candidate_step,
  save_end_to_end_chain_result,
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
STATE_SEED_PROGRESS = "theme_validation_seed_progress"
STATE_SEED_PROGRESS_THEME_ID = "theme_validation_seed_progress_theme_id"
STATE_SEED_PROGRESS_PUBLICATIONS = "theme_validation_seed_progress_publications"
STATE_END_TO_END_RESULT = "theme_validation_end_to_end_result"

END_TO_END_UI_NOTICES = (
  "JP Seed End-to-End Chain: Evidence Map skeleton 以降の Paper / Web / Link / Watch / Digest をつなげます。",
  "Paper候補は supporting evidence candidate であり、特許請求項の証明ではありません。",
  "Webシグナルは signal candidate です。直接関係を断定しません。",
  "Link Candidate は確認候補であり、直接リンクの証明ではありません。",
  "Strategic Watch は重点監視候補であり、最終結論ではありません。",
  "Digest は preview only です。outbound email は行いません。",
  "本ツールはFTO、侵害、有効性判断、法的見解には使用しません。",
)
END_TO_END_INTRO_LINES = (
  "Stage 4以降、つまりPaper候補、Webシグナル候補、Link Candidate、Strategic Watch、Digestまでを確認します。",
  "外部APIは明示同意がある場合のみ実行します。",
)

EVIDENCE_MAP_BUILDER_NOTICES = (
  "保存済みManual ClaimsからClaim Elementを抽出し、Evidence Map生成の準備を行います。",
  "この処理では外部APIは実行しません。",
  "論文候補やWebシグナルは確認候補であり、最終結論ではありません。",
  "本ツールはFTO、侵害、有効性判断、法的見解には使用しません。",
)


def _project_root() -> Path:
  return Path(__file__).resolve().parents[3]


def _show_output_path(label: str, path: Path | str | None) -> None:
  root = _project_root()
  if is_developer_view():
    st.caption(f"{label}: `{path}`")
  elif path:
    st.caption(f"{label}: `{format_display_path(path, project_root=root)}`")


def _validation_output_dir(theme_id: str) -> Path:
  return _project_root() / "outputs" / "validation" / "theme_validation" / theme_id


def render_theme_validation_safety_messages() -> None:
  st.caption(
    "利用上の注意は「はじめに」タブの「利用上の注意」を参照してください。"
    " 外部API実行時のみ、下記ボタン付近で同意確認があります。"
  )


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


def _get_seed_progress_list(seeds: list[str]) -> list:
  root = _project_root()
  return inspect_seed_progress_many(seeds, root)


def _sync_seed_progress_session(
  *,
  progress_list: list,
  theme_id: str,
  seeds: list[str],
) -> None:
  st.session_state[STATE_SEED_PROGRESS] = progress_list
  st.session_state[STATE_SEED_PROGRESS_THEME_ID] = theme_id
  st.session_state[STATE_SEED_PROGRESS_PUBLICATIONS] = list(seeds)


def _render_seed_progress_actions(progress_list: list) -> None:
  pending, completed = summarize_seed_progress_actions(progress_list)
  st.markdown("### 次にやること")
  if pending:
    for row in pending:
      st.markdown(render_warning_box(row), unsafe_allow_html=True)
  else:
    st.info("未完了の seed はありません。")

  st.markdown("### 完了済みseed")
  if completed:
    for row in completed:
      st.markdown(render_success_box(row), unsafe_allow_html=True)
  else:
    st.info("Stage 3 まで完了した seed はまだありません。")


def render_seed_progress_dashboard(
  *,
  seeds: list[str],
  theme_id: str,
  key_prefix: str,
) -> list:
  st.markdown("#### Seed別 検証進捗 / Seed Validation Progress")
  st.markdown(
    render_info_box(
      "seed publication numbersごとに、Manual Claims保存状況、Evidence Map skeleton有無、"
      "Stage 2/3の状態を確認します。外部APIは実行しません。"
    ),
    unsafe_allow_html=True,
  )

  col_update, col_save = st.columns(2)
  with col_update:
    update_clicked = st.button("Seed進捗を更新する", key=f"{key_prefix}_seed_progress_update")
  with col_save:
    save_clicked = st.button("Seed進捗レポートを保存する", key=f"{key_prefix}_seed_progress_save")

  if not seeds:
    st.info("seed publication numbersを入力してください")
    return []

  root = _project_root()
  seeds_key = tuple(seeds)
  cached_pubs = tuple(st.session_state.get(STATE_SEED_PROGRESS_PUBLICATIONS, []))
  progress_list = st.session_state.get(STATE_SEED_PROGRESS)

  should_refresh = (
    update_clicked
    or progress_list is None
    or cached_pubs != seeds_key
    or st.session_state.get(STATE_SEED_PROGRESS_THEME_ID) != theme_id
  )
  if should_refresh:
    progress_list = _get_seed_progress_list(seeds)
    _sync_seed_progress_session(progress_list=progress_list, theme_id=theme_id, seeds=seeds)

  if save_clicked:
    progress_list = _get_seed_progress_list(seeds)
    _sync_seed_progress_session(progress_list=progress_list, theme_id=theme_id, seeds=seeds)
    report_theme_id = theme_id or "custom_theme"
    paths = save_seed_progress_report(
      progress_list,
      root / "outputs" / "validation" / "theme_validation",
      report_theme_id,
    )
    st.markdown(render_success_box("Seed進捗レポートを保存しました。"), unsafe_allow_html=True)
    for label, path in paths.items():
      _show_output_path(label, path)

  if progress_list:
    render_small_table(progress_to_display_dataframe(progress_list), height=280)
    _render_seed_progress_actions(progress_list)

  return progress_list or []


def _default_publication_with_manual_claims(
  case: ThemeValidationCase,
  root: Path,
  progress_list: list | None = None,
) -> str:
  items = progress_list or _get_seed_progress_list(case.seed_publication_numbers)
  preferred = preferred_publication_for_manual_claims(items)
  if preferred:
    return preferred
  for pub in case.seed_publication_numbers:
    if has_manual_claims(pub, root)[0]:
      return pub
  return case.seed_publication_numbers[0] if case.seed_publication_numbers else ""


def render_manual_claims_editor(
  *,
  case: ThemeValidationCase,
  key_prefix: str,
  progress_list: list | None = None,
  on_revalidate: bool = False,
) -> bool:
  """Render Manual Claims editor. Returns True if re-validation was requested."""
  st.markdown("#### Manual Claims入力 / Manual Claims Editor")
  for notice in MANUAL_CLAIMS_EDITOR_NOTICES:
    st.markdown(render_caution_box(notice), unsafe_allow_html=True)

  seeds = list(case.seed_publication_numbers)
  root = _project_root()
  items = progress_list or _get_seed_progress_list(seeds)
  default_pub = _default_publication_with_manual_claims(case, root, items)
  if seeds:
    default_index = seeds.index(default_pub) if default_pub in seeds else 0
    publication_number = st.selectbox(
      "publication number",
      options=seeds,
      index=default_index,
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
      _show_output_path("manual claims", saved_path)
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
  progress_list: list | None = None,
) -> None:
  st.markdown("#### Evidence Map生成準備 / Evidence Map Builder")
  for notice in EVIDENCE_MAP_BUILDER_NOTICES:
    st.markdown(render_caution_box(notice), unsafe_allow_html=True)

  root = _project_root()
  seeds = list(case.seed_publication_numbers)
  items = progress_list or _get_seed_progress_list(seeds)
  default_pub = preferred_publication_for_evidence_map(items) or _default_publication_with_manual_claims(case, root, items)
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
        _show_output_path(label, path)
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
      _show_output_path(label, path)

  skeleton_json = evidence_map_output_dir(root, pub) / "evidence_map_skeleton.json" if pub else None
  if skeleton_json and skeleton_json.exists():
    st.caption(f"既存 skeleton: `{skeleton_json}`")


def _end_to_end_display_dataframe(result: EndToEndChainResult) -> pd.DataFrame:
  rows: list[dict[str, str]] = []
  for seed in result.seed_statuses:
    rows.append(
      {
        "publication_number": seed.publication_number,
        "Stage 2": seed.stage2_manual_claims,
        "Stage 3": seed.stage3_evidence_skeleton,
        "Stage 4 Paper": seed.stage4_paper_candidates,
        "Stage 5 Web": seed.stage5_web_signals,
        "Stage 6 Link": seed.stage6_link_candidates,
        "Stage 7 Watch": seed.stage7_strategic_watch,
        "Stage 8 Digest": seed.stage8_digest,
        "overall_status": seed.overall_status,
        "next_action": seed.next_action,
      },
    )
  return pd.DataFrame(rows)


def render_end_to_end_chain_section(
  *,
  case: ThemeValidationCase,
  key_prefix: str,
  progress_list: list | None = None,
) -> None:
  st.divider()
  st.markdown("#### JP Seed End-to-End Chain / 最後までつなぐ検証")
  for line in END_TO_END_INTRO_LINES:
    st.markdown(render_info_box(line), unsafe_allow_html=True)
  for notice in END_TO_END_UI_NOTICES:
    st.markdown(render_caution_box(notice), unsafe_allow_html=True)

  root = _project_root()
  seeds = list(case.seed_publication_numbers)
  items = progress_list or _get_seed_progress_list(seeds)
  stage3_ready = [item.publication_number for item in items if item.stage3_status == "pass"]
  default_selection = stage3_ready or seeds
  seeds_ready = bool(seeds)

  if not seeds_ready:
    st.info("seed publication numbersを入力してください")

  selected_pubs: list[str] = []
  if seeds_ready:
    selected_pubs = st.multiselect(
      "publication numbers",
      options=seeds,
      default=default_selection,
      key=f"{key_prefix}_e2e_pubs",
    )
  else:
    st.caption("publication multiselect: seed publication numbers 入力後に表示されます。")

  col1, col2, col3 = st.columns(3)
  with col1:
    max_papers = st.number_input(
      "max_papers",
      min_value=1,
      max_value=20,
      value=5,
      key=f"{key_prefix}_e2e_max_papers",
      disabled=not seeds_ready,
    )
  with col2:
    max_web_signals = st.number_input(
      "max_web_signals",
      min_value=1,
      max_value=20,
      value=10,
      key=f"{key_prefix}_e2e_max_web",
      disabled=not seeds_ready,
    )
  with col3:
    cache_first = st.checkbox(
      "cache_first",
      value=True,
      key=f"{key_prefix}_e2e_cache",
      disabled=not seeds_ready,
    )

  dry_run = st.checkbox(
    "dry_run",
    value=True,
    key=f"{key_prefix}_e2e_dry_run",
    disabled=not seeds_ready,
  )
  from tech_cartography.runtime.cloud_run_config import is_external_api_disabled
  from tech_cartography.runtime.external_api_guard import external_api_ui_messages, resolve_allow_external_api
  from tech_cartography.ui.login_ui import can_use_production_features

  external_api_locked = is_external_api_disabled() or not can_use_production_features()
  allow_external_api = st.checkbox(
    "allow_external_api",
    value=False,
    key=f"{key_prefix}_e2e_allow_api",
    help="チェックしない限り OpenAlex/Tavily/BigQuery は実行しません。",
    disabled=not seeds_ready or external_api_locked,
  )
  run_openalex = st.checkbox(
    "run_openalex",
    value=False,
    key=f"{key_prefix}_e2e_openalex",
    disabled=not seeds_ready or external_api_locked,
  )
  run_tavily = st.checkbox(
    "run_tavily",
    value=False,
    key=f"{key_prefix}_e2e_tavily",
    disabled=not seeds_ready or external_api_locked,
  )
  run_bigquery = st.checkbox(
    "run_bigquery",
    value=False,
    key=f"{key_prefix}_e2e_bigquery",
    disabled=not seeds_ready or external_api_locked,
  )
  if external_api_locked and not is_external_api_disabled():
    st.caption("外部API実行はログイン後に利用できます。")
  for message in external_api_ui_messages():
    st.caption(message)
  if external_api_locked and is_external_api_disabled():
    allow_external_api = False
    run_openalex = False
    run_tavily = False
    run_bigquery = False
  effective_allow_external_api, _guard_reasons = resolve_allow_external_api(
    allow_checkbox=allow_external_api,
    run_openalex=run_openalex,
    run_tavily=run_tavily,
    run_bigquery=run_bigquery,
  )
  if allow_external_api and not effective_allow_external_api:
    allow_external_api = False

  st.markdown(
    render_warning_box(
      "OpenAlex/Tavily/BigQueryを実行する場合、入力キーワードやクエリが外部サービスに送信されます。"
      "社外秘情報を含めないでください。"
    ),
    unsafe_allow_html=True,
  )

  actions_enabled = seeds_ready and bool(selected_pubs)

  btn_cols = st.columns(5)
  with btn_cols[0]:
    inspect_clicked = st.button(
      "End-to-End状態を確認する",
      key=f"{key_prefix}_e2e_inspect",
      disabled=not actions_enabled,
    )
  with btn_cols[1]:
    paper_plan_clicked = st.button(
      "Paper Query Planを作る",
      key=f"{key_prefix}_e2e_paper_plan",
      disabled=not actions_enabled,
    )
  with btn_cols[2]:
    paper_fetch_clicked = st.button(
      "Paper候補を取得する",
      key=f"{key_prefix}_e2e_paper_fetch",
      disabled=not actions_enabled,
    )
  with btn_cols[3]:
    web_plan_clicked = st.button(
      "Web Signal Query Planを作る",
      key=f"{key_prefix}_e2e_web_plan",
      disabled=not actions_enabled,
    )
  with btn_cols[4]:
    web_fetch_clicked = st.button(
      "Web Signal候補を取得する",
      key=f"{key_prefix}_e2e_web_fetch",
      disabled=not actions_enabled,
    )

  btn_cols2 = st.columns(5)
  with btn_cols2[0]:
    link_clicked = st.button(
      "Link Candidateを生成する",
      key=f"{key_prefix}_e2e_link",
      disabled=not actions_enabled,
    )
  with btn_cols2[1]:
    watch_clicked = st.button(
      "Strategic Watch Briefを生成する",
      key=f"{key_prefix}_e2e_watch",
      disabled=not actions_enabled,
    )
  with btn_cols2[2]:
    digest_clicked = st.button(
      "Digest Previewを生成する",
      key=f"{key_prefix}_e2e_digest",
      disabled=not actions_enabled,
    )
  with btn_cols2[3]:
    all_steps_clicked = st.button(
      "選択したseedの全ステップを実行する",
      key=f"{key_prefix}_e2e_all",
      disabled=not actions_enabled,
    )
  with btn_cols2[4]:
    save_report_clicked = st.button(
      "End-to-Endレポートを保存する",
      key=f"{key_prefix}_e2e_save",
      disabled=not actions_enabled,
    )

  if not actions_enabled:
    result = st.session_state.get(STATE_END_TO_END_RESULT)
    if result is not None and seeds_ready:
      st.markdown("**End-to-End Stage 表（前回結果）**")
      st.dataframe(_end_to_end_display_dataframe(result), use_container_width=True, hide_index=True)
    st.caption(CHAIN_CAUTION)
    return

  config = EndToEndChainConfig(
    theme_id=case.theme_id,
    theme_name=case.theme_name,
    publication_numbers=selected_pubs,
    output_root=str(root),
    max_papers=int(max_papers),
    max_web_signals=int(max_web_signals),
    run_openalex=run_openalex,
    run_tavily=run_tavily,
    run_bigquery=run_bigquery,
    cache_first=cache_first,
    dry_run=dry_run,
    allow_external_api=effective_allow_external_api,
    created_by="streamlit_ui",
  )

  result: EndToEndChainResult | None = st.session_state.get(STATE_END_TO_END_RESULT)

  if inspect_clicked:
    result = inspect_end_to_end_status(config)
    st.session_state[STATE_END_TO_END_RESULT] = result
    st.markdown(render_success_box("End-to-End 状態を更新しました。"), unsafe_allow_html=True)

  if paper_plan_clicked:
    for pub in selected_pubs:
      run_paper_candidate_step(config, pub, query_plan_only=True)
    result = inspect_end_to_end_status(config)
    st.session_state[STATE_END_TO_END_RESULT] = result
    st.markdown(render_success_box("Paper Query Plan を保存しました（外部API未実行）。"), unsafe_allow_html=True)

  if paper_fetch_clicked:
    for pub in selected_pubs:
      run_paper_candidate_step(config, pub, query_plan_only=False)
    result = inspect_end_to_end_status(config)
    st.session_state[STATE_END_TO_END_RESULT] = result
    if allow_external_api and run_openalex and not dry_run:
      st.markdown(render_success_box("Paper 候補取得を実行しました。"), unsafe_allow_html=True)
    else:
      st.markdown(render_info_box("外部API未実行: query_plan のみ生成しました。"), unsafe_allow_html=True)

  if web_plan_clicked:
    for pub in selected_pubs:
      run_web_signal_candidate_step(config, pub, query_plan_only=True)
    result = inspect_end_to_end_status(config)
    st.session_state[STATE_END_TO_END_RESULT] = result
    st.markdown(render_success_box("Web Signal Query Plan を保存しました。"), unsafe_allow_html=True)

  if web_fetch_clicked:
    for pub in selected_pubs:
      run_web_signal_candidate_step(config, pub, query_plan_only=False)
    result = inspect_end_to_end_status(config)
    st.session_state[STATE_END_TO_END_RESULT] = result
    if allow_external_api and run_tavily and not dry_run:
      st.markdown(render_success_box("Web Signal 候補取得を実行しました。"), unsafe_allow_html=True)
    else:
      st.markdown(render_info_box("外部API未実行: query_plan のみ生成しました。"), unsafe_allow_html=True)

  if link_clicked:
    for pub in selected_pubs:
      run_link_candidate_step(config, pub)
    result = inspect_end_to_end_status(config)
    st.session_state[STATE_END_TO_END_RESULT] = result
    st.markdown(render_success_box("Link Candidate 生成を試行しました。"), unsafe_allow_html=True)

  if watch_clicked:
    for pub in selected_pubs:
      run_strategic_watch_step(config, pub)
    result = inspect_end_to_end_status(config)
    st.session_state[STATE_END_TO_END_RESULT] = result
    st.markdown(render_success_box("Strategic Watch Brief を生成しました。"), unsafe_allow_html=True)

  if digest_clicked:
    for pub in selected_pubs:
      run_digest_step(config, pub)
    result = inspect_end_to_end_status(config)
    st.session_state[STATE_END_TO_END_RESULT] = result
    st.markdown(render_success_box("Digest Preview を生成しました（送信なし）。"), unsafe_allow_html=True)

  if all_steps_clicked:
    steps = [
      "paper_query_plan",
      "paper_candidates",
      "web_signal_query_plan",
      "web_signals",
      "link_candidates",
      "strategic_watch",
      "digest",
    ]
    result = run_selected_chain_steps(config, steps)
    st.session_state[STATE_END_TO_END_RESULT] = result
    st.markdown(render_success_box("選択 seed の全ステップを実行しました。"), unsafe_allow_html=True)

  if save_report_clicked:
    result = st.session_state.get(STATE_END_TO_END_RESULT) or inspect_end_to_end_status(config)
    out_dir = end_to_end_output_dir(root, case.theme_id)
    paths = save_end_to_end_chain_result(result, out_dir)
    st.session_state[STATE_END_TO_END_RESULT] = result
    st.markdown(render_success_box("End-to-End レポートを保存しました。"), unsafe_allow_html=True)
    for label, path in paths.items():
      _show_output_path(label, path)

  result = st.session_state.get(STATE_END_TO_END_RESULT)
  if result is not None:
    st.markdown("**End-to-End Stage 表**")
    st.dataframe(_end_to_end_display_dataframe(result), use_container_width=True, hide_index=True)
    _show_output_path("保存先", end_to_end_output_dir(root, case.theme_id))
    st.caption(CHAIN_CAUTION)


def render_theme_validation_intro_card() -> None:
  st.markdown(
    render_info_box(
      "本番実行: 新しいテーマで分析する場合は「入力・実行」タブからテーマ入力・Manual Claims・E2E Chain を利用してください。"
    ),
    unsafe_allow_html=True,
  )


def render_theme_validation_tab_intro() -> None:
  st.markdown(
    render_info_box(
      "新しいテーマで Tech Cartography の流れ（検索計画・Manual Claims・Evidence Map・E2E Chain）を実行します。"
      " まずは dry-run で検索計画のみ作成してください。"
    ),
    unsafe_allow_html=True,
  )


def render_analyst_workflow_step_cards(
  snapshot,
) -> None:
  cols = st.columns(2)
  for index, step in enumerate(snapshot.steps):
    with cols[index % 2]:
      st.markdown(f"**{step.label}**")
      st.caption(step.status)


def render_pan_theme_loader_button(*, key_prefix: str) -> None:
  if st.button(
    "PAN前駆体欠陥制御テーマを読み込む",
    key=f"{key_prefix}_load_pan_theme",
    type="primary",
  ):
    for key, value in pan_theme_session_state_updates(key_prefix=key_prefix).items():
      st.session_state[key] = value
    st.success("PAN前駆体テーマを読み込みました。")
    st.rerun()


def _render_theme_seed_input_block(*, key_prefix: str) -> tuple[str, str, str, str, str, str, str, list[str], str, ThemeValidationCase]:
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
    placeholder="JP2022090764A, JP2023163084A, JP2018084002A",
  )

  seed_publications = parse_keyword_text(seed_text)
  progress_theme_id = build_theme_id(
    theme_name or "custom_theme",
    theme_id_override=theme_id_value,
    core_keywords=parse_keyword_text(core_text),
  )
  progress_list = render_seed_progress_dashboard(
    seeds=seed_publications,
    theme_id=progress_theme_id,
    key_prefix=key_prefix,
  )

  case = _build_case_from_inputs(
    theme_name=theme_name.strip() or "（テーマ名未入力）",
    theme_id_override=theme_id_value or progress_theme_id,
    description=description,
    core_text=core_text,
    application_text=application_text,
    material_text=material_text,
    exclude_text=exclude_text,
    seed_text=seed_text,
  )
  return (
    theme_name,
    core_text,
    theme_id_value,
    description,
    application_text,
    material_text,
    exclude_text,
    seed_text,
    seed_publications,
    progress_theme_id,
    progress_list,
    case,
  )


def _render_theme_validation_actions(
  *,
  key_prefix: str,
  case: ThemeValidationCase,
  has_theme_name: bool,
) -> None:
  dry_run_clicked = False
  existing_clicked = False
  template_clicked = False
  external_clicked = False
  save_clicked = False
  consent = False
  max_patents = 5

  if has_theme_name:
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
    max_patents = st.number_input(
      "max_patents", min_value=1, max_value=5, value=5, step=1, key=f"{key_prefix}_max_patents",
    )
    external_clicked = st.button(
      "C. 特許候補検索を実行する",
      key=f"{key_prefix}_external_search",
      disabled=not consent,
    )
    save_clicked = st.button("E. 検証レポートを保存する", key=f"{key_prefix}_save_report")

  result: ThemeValidationRunResult | None = st.session_state.get(STATE_THEME_VALIDATION_RESULT)

  if has_theme_name and dry_run_clicked:
    result = run_theme_validation_dry_run(case)
    st.session_state[STATE_THEME_VALIDATION_RESULT] = result
    st.markdown(render_success_box("dry-run 完了（外部API未実行）"), unsafe_allow_html=True)

  if has_theme_name and existing_clicked:
    result = run_existing_outputs_validation(case, _project_root())
    st.session_state[STATE_THEME_VALIDATION_RESULT] = result
    st.markdown(render_success_box("既存 outputs 検証完了（外部API未実行）"), unsafe_allow_html=True)

  if has_theme_name and template_clicked:
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
        _show_output_path("template", path)

  if has_theme_name and external_clicked:
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

  if has_theme_name and save_clicked:
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
      _show_output_path(label, path)

  if has_theme_name:
    render_theme_validation_stage_matrix(st.session_state.get(STATE_THEME_VALIDATION_RESULT))


def render_final_validation_builder(*, case: ThemeValidationCase, key_prefix: str) -> None:
  st.caption(
    "Final Validation Summary は seed ごとの Stage 2〜8 と成果物有無を集計します。外部APIは実行しません。"
  )
  build_clicked = st.button(
    "Final Validation Summaryを生成する",
    key=f"{key_prefix}_build_final_validation",
  )
  if build_clicked:
    if not case.seed_publication_numbers:
      st.warning("seed publication numbers を入力してください。")
      return
    paths = build_final_validation_from_case(case, project_root=_project_root())
    st.markdown(render_success_box("Final Validation Summary を生成しました。"), unsafe_allow_html=True)
    for label, path in paths.items():
      _show_output_path(label, path)


def render_analyst_input_execution_section(*, key_prefix: str = ANALYST_INPUT_KEY_PREFIX) -> None:
  from tech_cartography.ui.login_ui import can_use_production_features, render_production_access_blocked

  st.subheader("本番実行 / 新しいテーマで分析")
  if not can_use_production_features():
    render_production_access_blocked("本番実行")
    return
  st.caption(
    "新しい技術テーマとseed公報を入力し、Manual ClaimsからEvidence Map、Paper/Web、Link、Watch、Digestまで順番に生成します。"
  )
  from tech_cartography.ui.live_operation_console_ui import render_live_operation_console_section

  render_live_operation_console_section(project_root=_project_root(), key_prefix=f"{key_prefix}_live_operation_console")
  from tech_cartography.ui.live_web_signal_pack_ui import render_live_web_signal_pack_section

  render_live_web_signal_pack_section(project_root=_project_root(), key_prefix=f"{key_prefix}_live_web_signal_pack")
  from tech_cartography.ui.live_artifact_storage_ui import render_live_artifact_storage_expander

  render_live_artifact_storage_expander(project_root=_project_root(), key=f"{key_prefix}_live_artifact_storage")
  from tech_cartography.ui.live_digest_preview_ui import render_live_digest_preview_section

  render_live_digest_preview_section(project_root=_project_root(), key_prefix=f"{key_prefix}_live_digest_preview")
  from tech_cartography.ui.live_email_send_ui import render_live_email_send_section

  render_live_email_send_section(project_root=_project_root(), key_prefix=f"{key_prefix}_live_email_send")
  from tech_cartography.ui.live_approved_member_email_send_ui import render_live_approved_member_email_send_section

  render_live_approved_member_email_send_section(
    project_root=_project_root(),
    key_prefix=f"{key_prefix}_live_approved_member_email_send",
  )
  from tech_cartography.ui.live_watch_expansion_ui import render_live_watch_expansion_section

  render_live_watch_expansion_section(project_root=_project_root(), key_prefix=f"{key_prefix}_live_watch_expansion")
  from tech_cartography.ui.live_next_cycle_search_ui import render_live_next_cycle_search_section

  render_live_next_cycle_search_section(project_root=_project_root(), key_prefix=f"{key_prefix}_live_next_cycle_search")
  from tech_cartography.ui.live_run_history_ui import render_run_history_section

  render_run_history_section(project_root=_project_root(), key_prefix=f"{key_prefix}_live_run_history")
  from tech_cartography.ui.auth_status_ui import render_auth_status_expander

  render_auth_status_expander(project_root=_project_root(), key=f"{key_prefix}_auth_status", expanded=False)
  render_pan_theme_loader_button(key_prefix=key_prefix)
  render_theme_validation_safety_messages()

  from tech_cartography.ui.analyst_mode_ui import case_from_session_widgets

  preview_case = case_from_session_widgets(key_prefix=key_prefix)
  snapshot = compute_analyst_workflow_snapshot(preview_case, project_root=_project_root())
  st.markdown("### 実行ステップ")
  render_analyst_workflow_step_cards(snapshot)

  with st.expander("1. テーマ・seed入力", expanded=snapshot.steps[0].status == "次にやる"):
    (
      theme_name,
      _core_text,
      _theme_id_value,
      _description,
      _application_text,
      _material_text,
      _exclude_text,
      _seed_text,
      _seed_publications,
      _progress_theme_id,
      progress_list,
      case,
    ) = _render_theme_seed_input_block(key_prefix=key_prefix)
    has_theme_name = bool(theme_name.strip())
    if not has_theme_name:
      st.caption("テーマ名を入力すると dry-run などの操作ボタンが有効になります。")
    else:
      st.session_state[STATE_THEME_VALIDATION_CASE] = case
      if is_developer_view():
        st.caption(f"theme_id: `{case.theme_id}`")
      _render_theme_validation_actions(key_prefix=key_prefix, case=case, has_theme_name=has_theme_name)

  if preview_case is None:
    return

  case = preview_case
  progress_list = _get_seed_progress_list(case.seed_publication_numbers) if case.seed_publication_numbers else []

  with st.expander("2. Manual Claims", expanded=snapshot.steps[2].status == "次にやる"):
    render_manual_claims_editor(case=case, key_prefix=key_prefix, progress_list=progress_list)

  with st.expander("3. Evidence Map生成", expanded=snapshot.steps[3].status == "次にやる"):
    render_evidence_map_builder(case=case, key_prefix=key_prefix, progress_list=progress_list)

  with st.expander("4. Paper/Web/Link/Watch/Digest", expanded=snapshot.steps[4].status == "次にやる"):
    render_end_to_end_chain_section(case=case, key_prefix=key_prefix, progress_list=progress_list)

  with st.expander("5. Final Validation", expanded=snapshot.steps[6].status == "次にやる"):
    render_final_validation_builder(case=case, key_prefix=key_prefix)


def render_theme_validation_section(*, key_prefix: str = "theme_validation") -> None:
  render_analyst_input_execution_section(key_prefix=key_prefix)
