"""Tab renderers for the lightweight Tech Cartography v9 UI."""

from __future__ import annotations

from typing import Sequence

import streamlit as st

from services_v9.signal_models import Signal, WatchProfile
from services_v9.signal_scoring import (
  build_diversity_counts,
  format_score_delta,
  select_diverse_top_signals,
  select_top_reads,
  summarize_status_buckets,
)
from ui_v9.labels import (
  FORBIDDEN_UI_LABELS,
  V9_TAB_LABELS,
  action_label_ja,
  bool_label_ja,
  cadence_label_ja,
  data_source_mode_label_ja,
  source_mode_label_ja,
  status_label_ja,
  type_label_ja,
  watch_profile_suggestion_label_ja,
)

NOTICE_JA = (
  "v9は軽量なR&Dシグナル監視プレビューです。"
  "PDF/OCR深掘り、クレーム解釈、法的判断、FTO判断、侵害判断、"
  "特許性判断、技術的妥当性の証明は行いません。"
)


def render_notice() -> None:
  st.info(NOTICE_JA)


def _show_status_message(message: str | None, kind: str = "success") -> None:
  if not message:
    return
  if kind == "warning":
    st.warning(message)
  elif kind == "error":
    st.error(message)
  else:
    st.success(message)


def _render_profile_summary(summary: dict[str, object]) -> None:
  counts = dict(summary.get("counts", {}))
  st.markdown("### 入力サマリー")
  st.write(f"- コアキーワード: 英語 {counts.get('core_en', 0)}件 / 日本語 {counts.get('core_ja', 0)}件")
  st.write(
    f"- 用途キーワード: 英語 {counts.get('application_en', 0)}件 / 日本語 {counts.get('application_ja', 0)}件"
  )
  st.write(
    f"- 材料・プロセスキーワード: 英語 {counts.get('material_process_en', 0)}件 / "
    f"日本語 {counts.get('material_process_ja', 0)}件"
  )
  st.write(f"- 除外キーワード: 英語 {counts.get('exclude_en', 0)}件 / 日本語 {counts.get('exclude_ja', 0)}件")
  st.write(f"- Seed公報: {counts.get('seed_publications', 0)}件")
  st.write(f"- 追加候補公報: {counts.get('candidate_publications', 0)}件")


def render_theme_setup_tab(profile_summary: dict[str, object], profile_status_message: str | None = None) -> dict[str, bool]:
  st.subheader("Tech Cartography v9")
  st.caption("軽量R&Dシグナル監視エージェント")

  upper_left, upper_right = st.columns(2)
  with upper_left:
    st.text_input("テーマ名", key="ui_theme_name_input")
    st.text_area("テーマ説明", key="ui_theme_description_input", height=160)
    st.text_area(
      "コアキーワード 英語",
      key="ui_core_en_input",
      height=160,
      help="カンマ区切り・改行区切りのどちらでも入力できます。",
    )
    st.text_area(
      "用途キーワード 英語",
      key="ui_application_en_input",
      height=140,
      help="カンマ区切り・改行区切りのどちらでも入力できます。",
    )
    st.text_area(
      "材料・プロセスキーワード 英語",
      key="ui_material_process_en_input",
      height=180,
      help="カンマ区切り・改行区切りのどちらでも入力できます。",
    )
    st.text_area(
      "除外キーワード 英語",
      key="ui_exclude_en_input",
      height=120,
      help="カンマ区切り・改行区切りのどちらでも入力できます。",
    )
  with upper_right:
    st.checkbox("デモモード", key="ui_demo_mode_input")
    st.markdown("**外部API:** 停止中")
    st.markdown("**実行モード:** ローカルのデモデータ / アップロードCSV/JSONのみ")
    st.markdown("**メール / スケジューラ:** プレビューのみ / 停止中")
    st.caption("現在はローカル実行のみです。BigQuery、OpenAlex、Web検索、Gemini APIは実行しません。")
    st.text_area(
      "コアキーワード 日本語",
      key="ui_core_ja_input",
      height=160,
      help="カンマ区切り・改行区切りのどちらでも入力できます。",
    )
    st.text_area(
      "用途キーワード 日本語",
      key="ui_application_ja_input",
      height=140,
      help="カンマ区切り・改行区切りのどちらでも入力できます。",
    )
    st.text_area(
      "材料・プロセスキーワード 日本語",
      key="ui_material_process_ja_input",
      height=180,
      help="カンマ区切り・改行区切りのどちらでも入力できます。",
    )
    st.text_area(
      "除外キーワード 日本語",
      key="ui_exclude_ja_input",
      height=120,
      help="カンマ区切り・改行区切りのどちらでも入力できます。",
    )

  pub_left, pub_right = st.columns(2)
  with pub_left:
    st.text_area(
      "Seed publication numbers",
      key="ui_seed_publications_input",
      height=120,
      help="カンマ区切り・改行区切りのどちらでも入力できます。",
    )
  with pub_right:
    st.text_area(
      "追加候補 publication numbers",
      key="ui_candidate_publications_input",
      height=120,
      help="カンマ区切り・改行区切りのどちらでも入力できます。",
    )

  button_left, button_right = st.columns(2)
  with button_left:
    save_clicked = st.button("監視プロファイルを保存", key="btn_theme_save_profile", width="stretch")
  with button_right:
    load_clicked = st.button("保存済み監視プロファイルを読み込む", key="btn_theme_load_profile", width="stretch")

  _show_status_message(profile_status_message)
  _render_profile_summary(profile_summary)
  return {
    "save_profile": save_clicked,
    "load_profile": load_clicked,
  }


def render_sources_tab(
  source_rows: Sequence[dict[str, object]],
  operation_rows: Sequence[dict[str, str]],
  source_info: dict[str, object],
  csv_template_text: str,
  json_template_text: str,
) -> None:
  st.subheader("情報源")
  st.caption("特許・論文・Web情報・企業情報を、軽量なローカル / 準備中データとして表示します。")
  st.radio(
    "データ投入モード",
    options=["demo", "csv", "json"],
    format_func=data_source_mode_label_ja,
    key="ui_data_source_mode",
    horizontal=True,
  )
  st.caption(f"現在のデータ投入モード: {data_source_mode_label_ja(str(source_info['requested_mode']))}")
  st.info(
    "このPhaseでは外部検索は実行しません。アップロードされたCSV/JSONを注目シグナルとして読み込み、"
    "Watch Profileに基づく仮スコアを付けます。"
  )

  upload_left, upload_right = st.columns(2)
  with upload_left:
    st.markdown("### CSVアップロード")
    st.file_uploader("CSVファイル", type=["csv"], key="ui_csv_upload")
    st.download_button(
      "CSVテンプレートをダウンロード",
      data=csv_template_text,
      file_name="v9_signal_upload_template.csv",
      mime="text/csv",
      use_container_width=True,
    )
  with upload_right:
    st.markdown("### JSONアップロード")
    st.file_uploader("JSONファイル", type=["json"], key="ui_json_upload")
    st.download_button(
      "JSONテンプレートをダウンロード",
      data=json_template_text,
      file_name="v9_signal_upload_template.json",
      mime="application/json",
      use_container_width=True,
    )

  st.write(f"- 現在のデータソース: {source_info['label']}")
  st.write(f"- 読み込み件数: {source_info['loaded_count']}件")
  if source_info.get("provisional_scoring"):
    st.caption("アップロードデータは Watch Profile に基づく仮スコアリング済みです。既存スコアがある場合はその値を尊重します。")
  warnings = list(source_info.get("warnings", []))
  if warnings:
    st.markdown("### 読み込み警告")
    for warning in warnings:
      st.warning(str(warning))

  for row in source_rows:
    st.markdown(
      f"- **{type_label_ja(str(row['source_type']))}** | "
      f"有効/無効: `{bool_label_ja(bool(row['enabled']))}` | "
      f"モード: `{source_mode_label_ja(str(row['mode']))}` | "
      f"取得件数: `{row['top_n']}` | 最終更新: `{row['last_updated']}` | メモ: {row['note']}"
    )

  st.markdown("### 個別ステータス")
  for item in operation_rows:
    label = type_label_ja(item["label"]) if item["label"] in {"patent", "paper", "web", "company"} else item["label"]
    st.write(f"- {label}: {source_mode_label_ja(item['mode'])}")


def render_top_signals_tab(
  signals: Sequence[Signal],
  source_info: dict[str, object],
  snapshot_status_message: str | None = None,
) -> dict[str, bool]:
  st.subheader("注目シグナル")
  top_signals = select_diverse_top_signals(signals, top_n=10, max_per_type=4)
  top_reads = select_top_reads(top_signals, limit=3)
  diversity_counts = build_diversity_counts(signals)
  st.caption(f"現在のデータソース: {source_info['label']} | 読み込み件数: {source_info['loaded_count']}件")
  if source_info.get("provisional_scoring"):
    st.info("アップロードデータは仮スコアリング済みです。これは外部APIなしの簡易評価です。")

  st.markdown("### 今週まず読むべき3件")
  if not top_reads:
    st.info("今週優先して読む候補はまだありません。")
  else:
    columns = st.columns(len(top_reads))
    for column, signal in zip(columns, top_reads):
      with column:
        st.markdown(f"**{signal.title}**")
        st.caption(
          f"{type_label_ja(signal.type)} | スコア {signal.score:.2f} | "
          f"{status_label_ja(signal.status)} | {action_label_ja(signal.action)}"
        )
        st.write(signal.why_read)
        st.write(f"確認すべき点: {signal.what_to_check}")
        st.write(f"次の行動: {signal.next_action}")
        st.markdown(f"[出典URLを開く]({signal.source_url})")

  available_types = sorted({signal.type for signal in top_signals})
  available_statuses = ["New", "Rising", "Dropped", "Stable"]
  available_actions = ["Read Now", "Watch", "Ignore"]

  filter_left, filter_mid, filter_right = st.columns(3)
  with filter_left:
    selected_types = st.multiselect(
      "種別フィルター",
      available_types,
      default=available_types,
      format_func=type_label_ja,
      key="ui_type_filter",
    )
  with filter_mid:
    selected_statuses = st.multiselect(
      "変化フィルター",
      available_statuses,
      default=available_statuses,
      format_func=status_label_ja,
      key="ui_status_filter",
    )
  with filter_right:
    selected_actions = st.multiselect(
      "判断フィルター",
      available_actions,
      default=available_actions,
      format_func=action_label_ja,
      key="ui_action_filter",
    )

  filtered = [
    signal for signal in top_signals
    if signal.type in selected_types and signal.status in selected_statuses and signal.action in selected_actions
  ]

  diversity_text = " / ".join(
    f"{type_label_ja(signal_type)}: {count}" for signal_type, count in diversity_counts.items()
  )
  st.caption("同じ種別に偏りすぎないように、特許・論文・Web情報・企業情報をバランスよく表示します。")
  st.caption(f"簡易的な多様性制御: {diversity_text}")

  if not filtered:
    st.warning("現在のフィルター条件に一致するシグナルはありません。")
  else:
    st.markdown("### 注目シグナル一覧")
    for index, signal in enumerate(filtered, start=1):
      st.markdown(f"#### {index}. {signal.title}")
      st.caption(
        f"種別: {type_label_ja(signal.type)} | スコア: {signal.score:.2f} | "
        f"変化: {status_label_ja(signal.status)} | 判断: {action_label_ja(signal.action)} | "
        f"公開日: {signal.published_date}"
      )
      st.write(f"**なぜ読むべきか:** {signal.why_read}")
      st.write(f"**確認すべき点:** {signal.what_to_check}")
      st.write(f"**次の行動:** {signal.next_action}")
      st.write(f"**出典名:** {signal.source_name}")
      st.write(f"**タグ:** {', '.join(signal.tags) if signal.tags else 'なし'}")
      st.write(f"**関連企業:** {', '.join(signal.companies) if signal.companies else 'なし'}")
      st.markdown(f"[出典URLを開く]({signal.source_url})")

  st.text_input("実行メモ", key="ui_snapshot_run_note")
  save_snapshot_clicked = st.button("現在のスナップショットを保存", key="btn_save_snapshot", width="stretch")
  _show_status_message(snapshot_status_message)
  return {"save_snapshot": save_snapshot_clicked}


def render_weekly_updates_tab(
  signals: Sequence[Signal],
  source_info: dict[str, object],
  snapshot_options: Sequence[str],
  diff_result: dict | None,
  drift: dict[str, object],
  history_rows: Sequence[dict[str, str]],
  previous_snapshot_info: dict | None,
  compare_status_message: str | None = None,
) -> dict[str, bool]:
  st.subheader("週次更新")
  st.caption(f"現在の比較対象データ: {source_info['label']} | 読み込み件数: {source_info['loaded_count']}件")
  st.selectbox(
    "前回スナップショット選択",
    options=list(snapshot_options) if snapshot_options else ["利用可能なスナップショットはありません"],
    key="ui_previous_snapshot_choice",
  )

  button_left, button_right = st.columns(2)
  with button_left:
    load_clicked = st.button("前回スナップショットを読み込む", key="btn_load_previous_snapshot", width="stretch")
  with button_right:
    compare_clicked = st.button("現在データと比較", key="btn_compare_snapshot", width="stretch")

  _show_status_message(compare_status_message)
  if previous_snapshot_info:
    st.caption(
      f"読み込み中の前回スナップショット: {previous_snapshot_info.get('snapshot_id', 'n/a')} "
      f"（{previous_snapshot_info.get('created_at', 'n/a')}）"
    )

  if diff_result:
    counts = diff_result["counts"]
    metrics = st.columns(4)
    for column, status in zip(metrics, ("New", "Rising", "Dropped", "Stable")):
      column.metric(status_label_ja(status), counts.get(status, 0))

    st.markdown("### 前回Digestとの差分サマリー")
    st.write(diff_result["summary"])
    for status in ("New", "Rising", "Dropped", "Stable"):
      items = diff_result["buckets"].get(status, [])
      if not items:
        st.write(f"- **{status_label_ja(status)}**: 0件")
        continue
      lead = items[0]
      title = lead.get("title", "タイトルなし")
      score_text = ""
      if "score" in lead:
        try:
          signal = Signal.from_dict(lead)
          score_text = f" | {format_score_delta(signal)}"
        except Exception:
          score_text = ""
      st.write(f"- **{status_label_ja(status)}**: {len(items)}件 | 代表シグナル: {title}{score_text}")

    st.markdown("### 前回から消えたシグナル")
    missing_signals = diff_result.get("missing_signals", [])
    if not missing_signals:
      st.write("- 前回から消えたシグナルはありません。")
    else:
      for item in missing_signals:
        st.write(f"- {item.get('title', 'タイトルなし')} | 前回スコア: {item.get('score', 'n/a')}")
  else:
    buckets = summarize_status_buckets(signals)
    metrics = st.columns(4)
    for column, status in zip(metrics, ("New", "Rising", "Dropped", "Stable")):
      column.metric(status_label_ja(status), len(buckets[status]))
    st.info("前回スナップショットを読み込んで比較すると、差分サマリーを表示できます。")

  st.markdown("### テーマずれアラート")
  if drift["level"] == "warning":
    st.warning(str(drift["message"]))
  elif drift["level"] == "success":
    st.success(str(drift["message"]))
  else:
    st.info(str(drift["message"]))
  if drift["examples"]:
    st.caption("監視キーワードとの一致が弱い例: " + " / ".join(str(item) for item in drift["examples"]))

  st.markdown("### 週次run履歴")
  if not history_rows:
    st.write("- 保存済みrun履歴はまだありません。")
  else:
    for row in history_rows:
      st.write(f"- {row['snapshot_id']} | {row['created_at']} | メモ: {row['run_note'] or 'なし'}")

  return {
    "load_previous_snapshot": load_clicked,
    "compare_snapshot": compare_clicked,
  }


def render_watch_profile_tab(
  watch_profile: WatchProfile,
  profile_summary: dict[str, object],
  query_previews: dict[str, str],
  suggestions: Sequence[str],
  profile_status_message: str | None = None,
) -> dict[str, bool]:
  st.subheader("監視プロファイル")

  st.text_area(
    "注目企業",
    key="ui_target_companies_input",
    height=90,
    help="カンマ区切り・改行区切りのどちらでも入力できます。",
  )
  st.text_input("対象国", key="ui_countries_input")
  st.multiselect(
    "情報源タイプ",
    options=["patent", "paper", "web", "company"],
    format_func=type_label_ja,
    key="ui_source_types_input",
  )
  st.selectbox(
    "更新頻度",
    options=["weekly", "biweekly", "monthly"],
    format_func=cadence_label_ja,
    key="ui_cadence_input",
  )
  st.text_area(
    "優先ルール",
    key="ui_priority_rules_input",
    height=120,
    help="1行に1件ずつ入力してください。",
  )

  _show_status_message(profile_status_message)

  st.markdown("### 現在の監視プロファイル")
  st.write(f"**テーマ名:** {profile_summary.get('theme_name') or '未設定'}")
  st.write(f"**テーマ説明:** {profile_summary.get('theme_description') or '未設定'}")
  st.write(f"**注目企業:** {', '.join(profile_summary.get('target_companies', [])) or 'なし'}")
  st.write(f"**対象国:** {', '.join(watch_profile.countries) if watch_profile.countries else 'なし'}")
  st.write(f"**情報源タイプ:** {', '.join(type_label_ja(item) for item in watch_profile.source_types)}")
  st.write(f"**更新頻度:** {cadence_label_ja(watch_profile.cadence)}")

  _render_profile_summary(profile_summary)

  st.markdown("### Seed publication numbers")
  if watch_profile.seed_publications:
    for item in watch_profile.seed_publications:
      st.write(f"- {item}")
  else:
    st.write("- なし")

  st.markdown("### 追加候補 publication numbers")
  if watch_profile.candidate_publications:
    for item in watch_profile.candidate_publications:
      st.write(f"- {item}")
  else:
    st.write("- なし")

  st.markdown("### 監視プロファイル更新提案")
  for index, suggestion in enumerate(suggestions, start=1):
    st.write(f"提案{index}: {watch_profile_suggestion_label_ja(suggestion)}")

  st.markdown("### 簡易検索クエリPreview")
  st.caption("これは検索実行ではなくPreviewです。外部APIや外部検索は実行しません。")
  for label, key in [
    ("特許検索Preview", "patent"),
    ("論文検索Preview", "paper"),
    ("Web検索Preview", "web"),
    ("企業情報検索Preview", "company"),
  ]:
    with st.expander(label):
      st.code(query_previews.get(key, "Previewを生成できませんでした。"))

  button_left, button_mid, button_right = st.columns(3)
  with button_left:
    load_clicked = st.button("保存済み監視プロファイルを読み込む", key="btn_profile_load", width="stretch")
  with button_mid:
    save_clicked = st.button("監視プロファイルを保存", key="btn_profile_save", width="stretch")
  with button_right:
    apply_clicked = st.button("デモ提案を反映", key="btn_profile_apply", width="stretch")

  return {
    "save_profile": save_clicked,
    "load_profile": load_clicked,
    "apply_suggestions": apply_clicked,
  }


def render_digest_export_tab(
  markdown_text: str,
  csv_text: str,
  json_text: str,
  source_info: dict[str, object],
  digest_status_message: str | None = None,
) -> dict[str, bool]:
  st.subheader("ダイジェスト / エクスポート")
  st.caption("メール配信: プレビューのみ / 停止中")
  st.caption(f"現在のデータソース: {source_info['label']} | 読み込み件数: {source_info['loaded_count']}件")
  st.markdown(markdown_text)

  button_left, button_mid, button_right = st.columns(3)
  with button_left:
    st.download_button(
      "Markdownをダウンロード",
      data=markdown_text,
      file_name="tech_cartography_v9_weekly_digest.md",
      mime="text/markdown",
      use_container_width=True,
    )
  with button_mid:
    st.download_button(
      "CSVをダウンロード",
      data=csv_text,
      file_name="tech_cartography_v9_top_signals.csv",
      mime="text/csv",
      use_container_width=True,
    )
  with button_right:
    st.download_button(
      "JSONをダウンロード",
      data=json_text,
      file_name="tech_cartography_v9_signal_watch.json",
      mime="application/json",
      use_container_width=True,
    )

  save_digest_clicked = st.button("ダイジェストファイルを保存", key="btn_save_digest_files", width="stretch")
  _show_status_message(digest_status_message)
  return {"save_digest_files": save_digest_clicked}
