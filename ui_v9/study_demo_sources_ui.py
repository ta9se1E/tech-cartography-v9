"""Study Demo information source tab — active run vs legacy sections."""

from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

from services_v9.study_demo_run_metrics import format_unknown_metric


def render_study_demo_active_run_section(
  *,
  source_info: Mapping[str, Any],
  theme_state: Mapping[str, Any] | None = None,
) -> None:
  st.markdown("### B. 現在の分析対象 / 保存済みrun")
  active_context = dict(source_info.get("active_context", {}) or {})
  metrics = dict(source_info.get("canonical_metrics", {}) or {})
  integration = dict(source_info.get("integration_summary", {}) or {})
  provider_status = dict(source_info.get("provider_status", {}) or {})

  if not active_context.get("active_search_run_id"):
    st.info("Active Context未設定です。上の一時検索フォームから分析対象を設定してください。")
    return

  st.write(f"- 現在のデータソース: **{source_info.get('label', '保存済み検索run')}**")
  st.write(f"- 作成経路: {source_info.get('creation_path_label', '—')}")
  st.write(f"- run_origin: `{active_context.get('run_origin', '—')}`")
  st.write(f"- context_type: `{active_context.get('context_type', '—')}`")
  st.write(f"- lineage_status: `{active_context.get('lineage_status', metrics.get('lineage_status', '—'))}`")
  st.write(f"- active run ID: `{active_context.get('active_search_run_id', '')}`")
  st.write(f"- Active Runテーマ: {active_context.get('theme', '')}")

  watch_profile = dict((theme_state or {}).get("watch_profile", {}) or {})
  if watch_profile.get("watch_profile_signature"):
    st.write(
      f"- Watch Profile signature: `{str(watch_profile.get('watch_profile_signature', ''))[:8]}` "
      f"(`{watch_profile.get('watch_profile_id', '')}`)"
    )
  elif active_context.get("source_watch_profile_signature"):
    st.write(f"- Watch Profile signature: `{str(active_context.get('source_watch_profile_signature', ''))[:8]}`")

  st.markdown("#### Provider status")
  st.caption("保存済み検索結果を表示しています。ページ表示では外部APIを実行しません。")
  for name, label in (("patent", "Patent"), ("paper", "Paper"), ("web", "Web")):
    item = dict(dict(metrics.get("provider_success", {}) or {}).get(name, {}) or {})
    if not item and provider_status.get(name):
      item = dict(provider_status.get(name, {}) or {})
    status = str(item.get("status", "") or "—")
    count = metrics.get("provider_counts", {}).get(name)
    count_text = format_unknown_metric(count)
    st.write(f"- {label}: {status} / {count_text}")

  active_sources = list(metrics.get("active_retrieval_sources", []) or integration.get("active_sources", []) or [])
  if active_sources:
    st.write(f"- active retrieval sources: {', '.join(str(s).title() for s in active_sources)}")

  st.markdown("#### 集計")
  provider_counts = dict(metrics.get("provider_counts", {}) or integration.get("provider_counts", {}) or {})
  st.write(
    f"- provider counts: Patent {format_unknown_metric(provider_counts.get('patent'))} / "
    f"Paper {format_unknown_metric(provider_counts.get('paper'))} / "
    f"Web {format_unknown_metric(provider_counts.get('web'))}"
  )
  st.write(f"- provider success rate: {format_unknown_metric(metrics.get('provider_success_rate'))}%")
  st.write(f"- saved count: {format_unknown_metric(metrics.get('saved_count'))}")
  st.write(f"- integrated count: {format_unknown_metric(metrics.get('integrated_count'))}")
  st.write(f"- ranked count: {format_unknown_metric(metrics.get('ranked_count'))}")

  tier_counts = dict(metrics.get("tier_counts", {}) or integration.get("tier_counts", {}) or {})
  if tier_counts:
    st.write(
      f"- Tier: A {tier_counts.get('A', 0)} / B {tier_counts.get('B', 0)} / "
      f"C {tier_counts.get('C', 0)} / D {tier_counts.get('D', 0)}"
    )

  inconsistencies = list(metrics.get("inconsistencies", []) or integration.get("metric_inconsistencies", []) or [])
  if inconsistencies:
    st.warning("保存済みrunの集計値に不整合があります。")
    with st.expander("技術情報（集計不整合）", expanded=False):
      for item in inconsistencies:
        st.write(f"- {item}")

  with st.expander("技術情報（内部メトリクス）", expanded=False):
    st.write(f"- search_run_count: {format_unknown_metric(metrics.get('search_run_count'))}")
    raw = dict(metrics.get("raw_provider_counts", {}) or {})
    stored = dict(metrics.get("stored_artifact_counts", {}) or {})
    st.write(
      f"- raw provider counts: patent={format_unknown_metric(raw.get('patent'))}, "
      f"paper={format_unknown_metric(raw.get('paper'))}, web={format_unknown_metric(raw.get('web'))}"
    )
    st.write(
      f"- stored artifact counts: patent={format_unknown_metric(stored.get('patent'))}, "
      f"paper={format_unknown_metric(stored.get('paper'))}, web={format_unknown_metric(stored.get('web'))}"
    )
    st.write(f"- metric sources: {dict(metrics.get('metric_sources', {}) or {})}")


def render_study_demo_legacy_sources_section(
  *,
  retrieval_reload_state: Mapping[str, Any],
  retrieval_manifest_status_message: str | None,
  csv_template_text: str,
  json_template_text: str,
) -> dict[str, bool]:
  st.markdown("### C. 手動投入・旧データソース")
  st.caption(
    "現在の保存済み標準検索runとは別機能です。通常のハッカソンデモでは操作不要です。"
  )
  legacy_expander = st.expander("手動アップロード・旧データ投入機能", expanded=False)
  events = {
    "save_retrieval_manifest": False,
    "load_saved_retrieval_manifest": False,
  }
  with legacy_expander:
    st.caption("legacy manifest / session retrieval は現在のActive Run表示には使用しません。")
    if retrieval_manifest_status_message:
      st.caption(str(retrieval_manifest_status_message))
    manifest_summary = dict(retrieval_reload_state.get("manifest_summary", {}) or {})
    current_run_ids = dict(retrieval_reload_state.get("current_run_ids", {}) or {})
    with st.expander("技術情報（legacy retrieval / manifest）", expanded=False):
      st.write(
        f"- legacy Watch Profile signature: "
        f"`{str(retrieval_reload_state.get('watch_profile_signature', '') or '')[:8]}`"
      )
      st.write(f"- session patent run ID: `{current_run_ids.get('patent', '') or 'なし'}`")
      st.write(f"- session paper run ID: `{current_run_ids.get('paper', '') or 'なし'}`")
      st.write(f"- session web run ID: `{current_run_ids.get('web_company', '') or 'なし'}`")
      if manifest_summary.get("checked"):
        availability_label = "あり" if bool(manifest_summary.get("available")) else "なし"
        st.write(f"- legacy manifest: `{availability_label}` / status `{manifest_summary.get('status', 'none')}`")
      else:
        st.write("- legacy manifest: 未使用（現在のActive Runでは使用しません）")
    retrieval_cols = st.columns(2)
    events["save_retrieval_manifest"] = retrieval_cols[0].button(
      "現在の取得runを保存", key="btn_legacy_save_retrieval_manifest", use_container_width=True
    )
    events["load_saved_retrieval_manifest"] = retrieval_cols[1].button(
      "最新の保存済み取得結果を読み込む", key="btn_legacy_load_retrieval_manifest", use_container_width=True
    )
    upload_left, upload_right = st.columns(2)
    with upload_left:
      st.markdown("#### CSVアップロード")
      st.file_uploader("CSVファイル", type=["csv"], key="ui_csv_upload")
      st.download_button(
        "CSVテンプレートをダウンロード",
        data=csv_template_text,
        file_name="v9_signal_upload_template.csv",
        mime="text/csv",
        use_container_width=True,
        key="study_demo_download_sources_csv_template",
      )
    with upload_right:
      st.markdown("#### JSONアップロード")
      st.file_uploader("JSONファイル", type=["json"], key="ui_json_upload")
      st.download_button(
        "JSONテンプレートをダウンロード",
        data=json_template_text,
        file_name="v9_signal_upload_template.json",
        mime="application/json",
        use_container_width=True,
        key="study_demo_download_sources_json_template",
      )
  return events


__all__ = [
  "render_study_demo_active_run_section",
  "render_study_demo_legacy_sources_section",
]
