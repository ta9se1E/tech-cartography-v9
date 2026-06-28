"""Executive Summary blocks for v8 tabs (Phase 27R.3) — display only, no LLM."""

from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st

from tech_cartography.ui.v8_judge_mode_copy import CASE_01_FUNNEL_DEFAULTS

if TYPE_CHECKING:
  from tech_cartography.runtime.v8_evidence_map_schema import V8EvidenceMap
  from tech_cartography.runtime.v8_gap_next_actions_schema import V8GapNextActionsReport

DEFAULT_FIRST_PATENT = "CN108286090A"

EVIDENCE_EXECUTIVE_TEMPLATE = (
  "Top5特許の35請求項を起点に、351件の裏取り候補リンクを整理しました。"
  " 現時点ではclaim本文不足は解消しており、次の確認対象は、"
  "論文・Web・企業情報の原典確認と、特許description/examplesに記載された"
  "実施例条件・物性値・比較例の有無です。"
  " Evidence Mapは証明ではなく、次に確認すべき候補の地図です。"
)

GAP_EXECUTIVE_TEMPLATE = (
  "106件の未確認事項を整理しました。"
  " 現在はclaim本文不足ではなく、Top5特許のdescription/examplesにある"
  "実施例条件・物性値・比較例の確認が最優先です。"
  " Gapは特許の弱点や無効理由ではなく、人間が次に確認すべき技術調査タスクです。"
)

WATCH_EXECUTIVE_SUMMARY = (
  "今回の未確認事項と次アクションを、次回の定点観測テーマに引き継ぎます。"
  " メール送信・定期実行・検索範囲拡張は運用機能として保持していますが、"
  " 更新や送信は人手承認後に行います。"
)

EXPORT_EXECUTIVE_SUMMARY = (
  "今回の分析結果を、研究チーム・知財部・弁理士相談用の共有資料として出力します。"
  " Top5、Claim Map、Evidence候補、Gap / Next Actions、Digest previewをまとめて引き継げます。"
)

EVIDENCE_HOW_TO_READ: tuple[str, ...] = (
  "どの請求項に候補情報が紐づいているか（publication_number / claim_no）",
  "paper / web / company のどの種類の候補があるか",
  "support_level は確定度ではなく、確認優先度の目安",
  "原典確認は人間が行う（裏取り候補であり証明ではない）",
  "全件は Top20 preview + ダウンロードで確認",
)

GAP_TYPE_GUIDE: tuple[tuple[str, str], ...] = (
  ("claim_text_required", "請求項本文が未取得 — Claim Map で投入"),
  ("example_support_missing", "特許 description / examples の実施例確認"),
  ("paper_support_missing", "論文原典・データの確認"),
  ("web_or_company_only", "Web / 企業情報の原典確認"),
  ("property_data_missing", "物性値・比較例の原典確認"),
)


def _first_top_action(report: V8GapNextActionsReport) -> str:
  if report.top_3_actions:
    return report.top_3_actions[0].action_type
  return str(CASE_01_FUNNEL_DEFAULTS.get("next_action", "check_patent_examples"))


def _first_read_patent(report: V8GapNextActionsReport | None) -> str:
  if report and report.gaps:
    for gap in report.gaps:
      if gap.publication_number:
        return gap.publication_number
  return DEFAULT_FIRST_PATENT


def render_evidence_executive_summary(evidence_map: V8EvidenceMap | None = None) -> None:
  if evidence_map is not None:
    review_count = sum(1 for l in evidence_map.links if l.human_review_required)
    loaded = evidence_map.claim_count - evidence_map.claim_text_required_count
    text = (
      f"Top5特許の{evidence_map.claim_count}請求項を起点に、"
      f"{evidence_map.link_count}件の裏取り候補リンクを整理しました。"
      f" claim_text_required={evidence_map.claim_text_required_count}。"
      " これは証明ではなく supporting evidence candidate / 裏取り候補です。"
      " 次に見るべきは Gap / Next Actions です。"
    )
    st.success(text)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("claims loaded", loaded)
    c2.metric("evidence candidate links", evidence_map.link_count)
    c3.metric("claim_text_required", evidence_map.claim_text_required_count)
    c4.metric("needs_human_review", review_count)
  else:
    st.info(EVIDENCE_EXECUTIVE_TEMPLATE)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("claims loaded", CASE_01_FUNNEL_DEFAULTS["claims"])
    c2.metric("evidence candidate links", CASE_01_FUNNEL_DEFAULTS["evidence_links"])
    c3.metric("claim_text_required", 0)
    c4.metric("needs_human_review", CASE_01_FUNNEL_DEFAULTS["evidence_links"])


def render_evidence_how_to_read_section() -> None:
  st.markdown("#### この画面で見ること")
  for item in EVIDENCE_HOW_TO_READ:
    st.markdown(f"- {item}")


def render_gap_executive_summary(report: V8GapNextActionsReport | None = None) -> None:
  if report is not None:
    ctr = report.count_by_gap_type.get("claim_text_required", 0)
    ex_missing = report.count_by_gap_type.get("example_support_missing", 0)
    top_action = _first_top_action(report)
    text = (
      f"{report.gap_count}件の未確認事項を整理しました。"
      f" claim_text_required={ctr}。"
      " 最大の未確認事項は実施例条件・物性値・比較例の確認です。"
      f" 最優先Actionは {top_action}。"
      " Gapは弱点・無効理由・侵害リスクではありません。"
    )
    st.success(text)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("gaps", report.gap_count)
    c2.metric("claim_text_required", ctr)
    c3.metric("example_support_missing", ex_missing)
    c4.metric("top action", top_action)
  else:
    st.info(GAP_EXECUTIVE_TEMPLATE)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("gaps", CASE_01_FUNNEL_DEFAULTS["gaps"])
    c2.metric("claim_text_required", 0)
    c3.metric("example_support_missing", 35)
    c4.metric("top action", CASE_01_FUNNEL_DEFAULTS["next_action"])


def render_gap_how_to_read_section(*, report: V8GapNextActionsReport | None = None) -> None:
  st.markdown("#### Gapの見方")
  for gap_type, desc in GAP_TYPE_GUIDE:
    count = report.count_by_gap_type.get(gap_type, 0) if report else "—"
    st.markdown(f"- **{gap_type}** ({count}): {desc}")
  first_patent = _first_read_patent(report)
  st.markdown(
    f"**最初に読むべきもの:** {first_patent} の description / examples"
    "（法的判断ではなく、実施例条件・物性値の原典確認）"
  )


def render_watch_executive_summary() -> None:
  st.success(WATCH_EXECUTIVE_SUMMARY)
  c1, c2 = st.columns(2)
  c1.metric("メール送信", "デモではOFF")
  c2.metric("Scheduler起動", "デモではOFF")


def render_export_executive_summary() -> None:
  st.info(EXPORT_EXECUTIVE_SUMMARY)
  st.markdown("**出力物の用途**")
  st.markdown("- 研究チーム: Top5 / Claim / Evidence / Gap の共有")
  st.markdown("- 知財部・弁理士相談: 未確認事項と次アクションの引き継ぎ")
  st.markdown("- 定点観測: Digest preview のベースライン")
