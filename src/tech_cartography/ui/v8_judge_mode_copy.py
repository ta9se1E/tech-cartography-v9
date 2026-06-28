"""Judge Mode UI copy — display strings only (Phase 27R.1 / 27R.2)."""

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

THREE_MINUTE_DEMO_STEPS: tuple[str, ...] = (
  "1. はじめに — 概要と成果ファネルを確認",
  "2. 読むべき特許 — Top5選抜",
  "3. Claim Map — 請求項の技術要素整理",
  "4. Evidence Map — 裏取り候補",
  "5. Gap / Next Actions — 未確認事項",
  "6. 定点観測 — Weekly Watch（Digest preview）",
  "7. Export — 共有レポート",
)

V8_EXECUTION_FLOW_LINES: tuple[str, ...] = THREE_MINUTE_DEMO_STEPS

JUDGE_NEXT_TAB: dict[str, str] = {
  "intro": "input",
  "input": "sources",
  "sources": "patent_shortlist",
  "patent_shortlist": "claim_map",
  "claim_map": "evidence_map",
  "evidence_map": "gap_next_actions",
  "gap_next_actions": "fixed_point_observation",
  "fixed_point_observation": "export",
  "export": "intro",
  "admin_settings": "intro",
}

TAB_DO_THIS: dict[str, str] = {
  "intro": "このページの概要を確認し、「入力・テーマ設定」に進んでください。",
  "input": "研究テーマ、検索キーワード、CSV/Excel取込、PDF入力口を確認してください。",
  "sources": "取り込まれた候補特許データの出自と件数を確認してください。",
  "patent_shortlist": "1000件候補から選ばれたTop5と、なぜ読むべきかを確認してください。",
  "claim_map": "Top5特許の請求項35件が投入済みであることと、技術要素整理を確認してください。",
  "evidence_map": "請求項に紐づく裏取り候補リンクと、その見方を確認してください。",
  "gap_next_actions": "未確認事項と、人間が次に確認すべき実施例確認タスクを確認してください。",
  "fixed_point_observation": "今回のGapを次回以降のWatch ProfileやDigestにつなげる流れを確認してください。",
  "export": "分析結果を共有用ファイルとして出力してください。",
  "admin_settings": "管理者向け設定です。通常デモでは操作不要です。",
}

TAB_DO_NEXT: dict[str, str] = {
  "intro": "入力・テーマ設定でテーマと候補データ取込を確認",
  "input": "Sources｜データ出自で候補母集団の件数を確認",
  "sources": "読むべき特許｜Top5で選抜結果を確認",
  "patent_shortlist": "Claim Map｜請求項の技術整理で35請求項の整理を確認",
  "claim_map": "Evidence Map｜裏取り候補で351 linksを確認",
  "evidence_map": "Gap / Next Actions｜未確認事項で106件と次タスクを確認",
  "gap_next_actions": "定点観測｜Weekly WatchでDigest previewを確認",
  "fixed_point_observation": "Export｜共有レポートで出力物を確認",
  "export": "はじめにに戻るか、必要なタブを再確認",
  "admin_settings": "はじめに｜Judge Overviewに戻る",
}

INTRO_SERVICE_SUMMARY = (
  "Tech Cartographyは、研究テーマから「読むべき特許」「請求項構造」「裏取り候補」"
  "「未確認Gap」「次の確認タスク」を整理するR&D Intelligence Agentです。"
)

INTRO_FUNNEL_SUMMARY = (
  "本デモ（Case 1）: 1,000件候補 → Top5選抜 → 35請求項投入済 → "
  "351件の裏取り候補 → 106件の未確認事項。"
  " 最優先の確認タスクは特許実施例の確認です。"
)

INTRO_SAFETY_NOTICES: tuple[str, ...] = (
  "スコア・整理結果は読む優先度・技術整理の目安であり、FTO・侵害・有効性判断ではありません。",
  "Evidence Mapは裏取り候補の整理であり、証明ではありません。",
  "Gapは未確認事項であり、弱点・無効理由・侵害リスクではありません。",
)

CLAIM_INPUT_GUIDE_NOT_LOADED = (
  "一次情報から請求項本文をコピーし、manual claimとして登録してください。"
  " AIはclaim本文を生成しません。"
)

CLAIM_INPUT_GUIDE_LOADED = (
  "Top5全件の請求項本文は投入済みです。"
  " Claim Mapを再生成すると、技術要素整理とEvidence Mapへの接続に進めます。"
)

CLAIM_INPUT_GUIDE_COMMON = (
  "Claim Mapは権利範囲解釈ではなく、請求項本文を技術要素として整理するものです。"
)

JUDGE_CONCLUSION_CARDS: dict[str, str] = {
  "intro": INTRO_SERVICE_SUMMARY + " " + INTRO_FUNNEL_SUMMARY,
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
    "研究テーマと検索キーワードを設定し、候補特許のCSV/Excel取込やPDF入力口を確認します。"
  ),
  "sources": (
    "候補特許・論文・Web等のデータ出自を確認します。"
    " 1,000件は母集団であり、Top5のみが深掘り対象です。"
  ),
  "admin_settings": (
    "管理者向け設定です。通常の提出デモでは操作不要です。"
  ),
}

PDF_UPLOAD_HELP = (
  "Top5公報PDFをアップロードしてください。"
  " 次Phaseでは、PDFから description / examples / comparative examples を抽出し、"
  " 実施例条件・物性値・比較例を構造化します。"
  " 現時点では手動確認・将来のPDF解析連携用として保持しています。"
)

PDF_TEXT_EXTRACT_HELP = (
  "アップロード済みのTop5公報PDFから本文テキストを抽出します。"
  " この段階ではOCRやGemini抽出は行わず、読めるPDFかどうかを判定します。"
  " 実施例抽出・物性値抽出・claim-example対応は次Phaseです。"
)
