"""Tab overview descriptions for Intelligence Delivery Hub (Phase 24.0)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

DELIVERY_CAUTION = (
  "Web signals are signal candidates, not final conclusions. "
  "Papers are supporting evidence candidates, not proof of patent claims. "
  "Strategic Watch Brief items are monitoring candidates, not final conclusions. "
  "This is not FTO, infringement, or validity analysis."
)


@dataclass
class TabOverviewItem:
  tab_name: str
  display_name: str
  purpose: str
  what_you_can_learn: list[str]
  main_outputs: list[str]
  typical_user_action: str
  caveat: str

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


def build_tab_overviews() -> list[TabOverviewItem]:
  return [
    TabOverviewItem(
      tab_name="start",
      display_name="はじめる",
      purpose="Tech Cartographyの全体像、デモの見方、現在の分析状態を理解する。",
      what_you_can_learn=[
        "このツールが何をするか",
        "Evidence Mapとは何か",
        "デモで見る順番",
        "現在どこまで分析済みか",
      ],
      main_outputs=[
        "デモストーリーカード",
        "Reproducibility brief",
        "Weekly Digest Preview（旧）",
        "パイプライン stage status",
      ],
      typical_user_action="初回はここから全体像を把握し、デモモードで Evidence Map を読み込む。",
      caveat=DELIVERY_CAUTION,
    ),
    TabOverviewItem(
      tab_name="patents",
      display_name="特許候補",
      purpose="多数の特許候補から、Deep Diveすべき対象を確認する。",
      what_you_can_learn=[
        "読むべき特許候補",
        "技術テーマ",
        "ランクやクラスタ",
        "次に全文確認すべき対象",
      ],
      main_outputs=[
        "ranked_patents.csv",
        "strategic_watch_candidates.csv",
        "cluster_summary.csv",
      ],
      typical_user_action="Deep Dive対象の特許を1件選び、全文確認タブへ進む。",
      caveat="候補リストは自動ランキングであり、最終選定ではありません。",
    ),
    TabOverviewItem(
      tab_name="fulltext",
      display_name="全文確認",
      purpose="対象特許のclaims/descriptionが取得できているか確認する。",
      what_you_can_learn=[
        "BigQuery fulltextが使えるか",
        "claims/description欠落の有無",
        "Manual Claims Routeが必要か",
        "manual投入済みか",
      ],
      main_outputs=[
        "fulltext_retrieval_status.csv",
        "manual_fulltext JSON",
        "fulltext_execute_summary",
      ],
      typical_user_action="claims欠落があれば Manual Claims Route で手動投入を検討する。",
      caveat="全文取得の成否はパイプライン状態であり、特許の価値判断ではありません。",
    ),
    TabOverviewItem(
      tab_name="evidence",
      display_name="技術の裏取り",
      purpose="請求項の技術要素、論文候補、Evidence Gap、Next Actionsを確認する。",
      what_you_can_learn=[
        "Claim Element",
        "Selected Evidence Papers",
        "Claim × Paper Links",
        "Evidence Gap",
        "技術者レビューすべき点",
      ],
      main_outputs=[
        "evidence_map_synthesis.md",
        "evidence_map_items.csv",
        "selected_evidence_papers.csv",
        "claim_paper_candidate_links.csv",
      ],
      typical_user_action="Claim Element と論文候補の対応を確認し、Evidence Gap を埋める次アクションを決める。",
      caveat="論文は supporting evidence candidate であり、特許主張の証明ではありません。",
    ),
    TabOverviewItem(
      tab_name="market",
      display_name="企業・市場シグナル",
      purpose="Web情報、公的プロジェクト、IR、企業ニュース、Strategic Watch候補を確認する。",
      what_you_can_learn=[
        "NEDO/JST/METIなど公的シグナル",
        "Money / National Project候補",
        "Web Signal Review",
        "Patent × Paper × Web Signal Link Candidate",
        "Strategic Watch Brief",
      ],
      main_outputs=[
        "web_signal_review_summary.md",
        "web_signal_link_candidates.csv",
        "strategic_watch_brief.md",
      ],
      typical_user_action="高品質ソースの原文を開き、特許・論文との関係を人間が確認する。",
      caveat="Web signals are signal candidates, not final conclusions. IR/disclosure requires document-level verification.",
    ),
    TabOverviewItem(
      tab_name="reports",
      display_name="レポート",
      purpose="各分析結果をMarkdownでまとめて読み、共有する。",
      what_you_can_learn=[
        "Evidence Map Synthesis",
        "Reproducibility Summary",
        "Strategic Watch Brief",
        "Weekly Digest Preview",
        "Export Report / ZIP bundle",
      ],
      main_outputs=[
        "intelligence_report markdown",
        "weekly_digest_preview markdown/html",
        "digest_diff markdown",
        "tech_cartography_report_bundle.zip",
      ],
      typical_user_action="Intelligence Report をダウンロードし、チーム共有や週次レビューに使う。",
      caveat="レポートは候補整理であり、FTO・侵害・有効性判断ではありません。",
    ),
    TabOverviewItem(
      tab_name="settings",
      display_name="設定",
      purpose="ローカル設定、メール設定、API設定の確認。",
      what_you_can_learn=[
        "weekly digest設定",
        "APIキー設定の有無",
        "出力先",
        "送信ON/OFF状態",
      ],
      main_outputs=[
        "watch profile",
        "user settings",
        "weekly email preferences",
      ],
      typical_user_action="監視テーマと週次メール設定を確認する（送信は Phase24.0 では無効）。",
      caveat="メール送信は Preview only。実送信は今後の Phase で opt-in 実装予定。",
    ),
  ]


def render_overview_page_md(items: list[TabOverviewItem] | None = None) -> str:
  tabs = items or build_tab_overviews()
  lines = [
    "# Tech Cartography — まとめページ",
    "",
    "初見ユーザー向け: 各タブで何が分かるか、どこを見ればよいかを整理します。",
    "",
    "## Important",
    "",
    DELIVERY_CAUTION,
    "",
  ]
  for tab in tabs:
    lines.extend(
      [
        f"## {tab.display_name}",
        "",
        f"**目的**: {tab.purpose}",
        "",
        "**分かること**:",
        "",
      ],
    )
    for item in tab.what_you_can_learn:
      lines.append(f"- {item}")
    lines.extend(["", "**主な成果物**:", ""])
    for output in tab.main_outputs:
      lines.append(f"- {output}")
    lines.extend(
      [
        "",
        f"**典型的な次アクション**: {tab.typical_user_action}",
        "",
        f"**注意**: {tab.caveat}",
        "",
      ],
    )
  return "\n".join(lines)
