"""Judge Mode UI copy — display strings only (Phase 27R.1)."""

from __future__ import annotations

JUDGE_APP_TITLE = "Tech Cartography"
JUDGE_APP_SUBTITLE = "R&D Intelligence Agent"

JUDGE_CASE_01_LABEL = "Case 1: PAN系炭素繊維 / 前駆体・炭化・黒鉛化"

CASE_01_FUNNEL_DEFAULTS: dict[str, int | str] = {
  "candidates": 1000,
  "top5": 5,
  "claims": 35,
  "evidence_links": 351,
  "gaps": 106,
  "next_action": "check_patent_examples",
}

JUDGE_DEMO_SAFETY_LINES: tuple[str, ...] = (
  "BigQuery直接実行: OFF",
  "メール送信: OFF",
  "Scheduler起動: OFF",
)

DEEP_RESEARCH_DIFF = (
  "Deep Researchは一回の深い調査に強い。一方でTech Cartographyは、"
  "Claim / Evidence / Gap / Next Actionを構造化し、"
  "Watch Profileとして週次で追跡することに特化しています。"
)

THREE_MINUTE_DEMO_STEPS: tuple[str, ...] = (
  "1. はじめに — 3分で価値を把握",
  "2. 読むべき特許 — Top5選抜",
  "3. Claim Map — 請求項の技術要素整理",
  "4. Evidence Map — 裏取り候補",
  "5. Gap / Next Actions — 未確認事項",
  "6. 定点観測 — Weekly Watch（Digest preview）",
  "7. Export — 共有レポート",
)

JUDGE_NEXT_TAB: dict[str, str] = {
  "intro": "patent_shortlist",
  "patent_shortlist": "claim_map",
  "claim_map": "evidence_map",
  "evidence_map": "gap_next_actions",
  "gap_next_actions": "fixed_point_observation",
  "fixed_point_observation": "export",
  "export": "intro",
  "input": "sources",
  "sources": "patent_shortlist",
  "admin_settings": "intro",
}

JUDGE_CONCLUSION_CARDS: dict[str, str] = {
  "intro": (
    "Tech Cartographyは、研究テーマから「読むべき特許」「請求項構造」「裏取り候補」"
    "「未確認Gap」「次の確認タスク」を整理するR&D Intelligence Agentです。"
    " 本デモでは、PAN系炭素繊維テーマに対して、1,000件候補からTop5を選抜し、"
    "Top5全件の35請求項をユーザー提供claimとして投入しました。"
    " さらに351件の裏取り候補と106件の未確認事項を整理し、"
    "次に確認すべき最優先タスクとして「特許実施例の確認」を提示しています。"
  ),
  "patent_shortlist": (
    "1,000件の候補特許から、読む優先度が高いTop5を選抜しました。"
    " スコアは読む優先度の目安であり、法的価値や権利範囲の評価ではありません。"
    " Top5には中国企業・大学等の実在出願人を含み、炭素繊維領域の海外動向を確認できます。"
  ),
  "claim_map": (
    "Top5特許の請求項35件を投入済みです。"
    " このツールはAIで請求項本文を生成しません。ユーザーが一次情報から投入した実claimのみを、"
    "技術要素として整理します。Claim Mapは権利範囲解釈ではありません。"
  ),
  "evidence_map": (
    "35件の請求項を起点に、351件の裏取り候補リンクを整理しました。"
    " これは証明ではなく supporting evidence candidate / 裏取り候補です。"
    " 論文・Web・企業情報がどの請求項要素と関連しうるかを整理し、原典確認は人間が行います。"
  ),
  "gap_next_actions": (
    "106件の未確認事項を整理しました。"
    " Gapは弱点・無効理由・侵害リスクではありません。"
    " まだ人間が確認していない技術・実施例・エビデンスの一覧です。"
    " 最優先の確認タスクは、特許 description / examples の実施例確認です。"
  ),
  "fixed_point_observation": (
    "このケースを週次で追跡できます。"
    " 新しい特許・論文・Webシグナルが出たとき、差分をDigestとして確認できます。"
    " デモではDigest previewのみで、メール送信とScheduler起動はOFFです。"
  ),
  "export": (
    "今回の分析結果をMarkdown / CSV / Excel等で出力できます。"
    " 出力物は、Top5選抜結果、Claim Map、Evidence候補、Gap / Next Actions、"
    "Digest previewの共有に使います。"
  ),
  "input": (
    "研究テーマ・キーワード・seed publication numbers を設定します。"
    " 提出デモでは BigQuery 直接実行・外部API・メール・Scheduler は行いません。"
  ),
  "sources": (
    "候補特許・論文・Web等のデータ出自を確認します。"
    " 1,000件は母集団であり、Top5のみが深掘り対象です。"
  ),
  "admin_settings": (
    "提出デモの安全設定を確認します。"
    " 管理者機能はデフォルトOFF — 外部API・BigQuery・メール・Scheduler は実行しません。"
  ),
}
