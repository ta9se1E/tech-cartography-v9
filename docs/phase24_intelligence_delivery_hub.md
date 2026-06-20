# Phase 24.0 — Intelligence Delivery Hub

## 目的

Evidence Map / Reproducibility / Web Signal / Strategic Watch Brief の成果を、ユーザーが迷わず理解・共有・定期報告できる形に整理します。

- 各タブの意味を説明する「まとめページ」
- 統合 Markdown レポート
- Streamlit ダウンロード
- 週次 Digest Preview（差分強調）
- メール送信は **Preview only**（この Phase では実行しない）

## まとめページ

7タブ（はじめる / 特許候補 / 全文確認 / 技術の裏取り / 企業・市場シグナル / レポート / 設定）それぞれの目的・分かること・成果物・次アクションを説明します。

## Intelligence Report

既存 outputs を読み込み、1つの Markdown に統合します。

```
# Tech Cartography Intelligence Report
## 1. Executive Summary
...
## 13. Source Artifacts
```

## Weekly Digest Preview

週次メール向け本文の Preview。件名例:

`[Tech Cartography] Weekly Intelligence Digest - US-12565719-B2 - 2026-06-19`

## 差分だけ強調する理由

全量を毎週送るとノイズが多いため、前回 Snapshot との diff で **New / Changed** のみ強調します。

## Snapshot / Diff の仕組み

1. `build_digest_snapshot()` で watch/web/paper/link IDs を収集
2. `snapshots/{timestamp}_{pub}.json` に保存
3. 前回 snapshot と `compare_digest_snapshots()` で diff
4. 初回は **Initial Snapshot** として digest 生成

## 実行コマンド

```bash
python scripts/build_delivery_package.py \
  --publication-number US-12565719-B2 \
  --output-dir outputs/delivery \
  --include-zip
```

Dry run:

```bash
python scripts/build_delivery_package.py \
  --publication-number US-12565719-B2 \
  --dry-run
```

## 出力ファイル

```
outputs/delivery/
  overview_page.md
  intelligence_report_US-12565719-B2.md
  weekly_digest_preview_US-12565719-B2.md
  weekly_digest_preview_US-12565719-B2.html
  digest_diff_US-12565719-B2.md
  latest_snapshot.json
  snapshots/{timestamp}_US-12565719-B2.json
  tech_cartography_report_bundle_US-12565719-B2.zip
```

## UI 表示場所

- **レポート**タブ最上部: Intelligence Delivery / Export
- **はじめる**タブ下部: 簡易版タブ説明

## なぜこの Phase ではメール送信しないか（Phase 24.0）

実メール送信は誤送信・断定表示のリスクがあるため、Preview とファイル出力までに留めました。

## Phase 24.1 — Email Outbox への接続

Phase 24.1 で以下を追加しました。

- Weekly Digest 本文の日本語整形・Top 3 重複抑制
- `outputs/delivery/email_outbox/` への Email Draft 保存
- CLI `--build-email-draft` / `--send-email` による明示送信ガード
- UI では Email Draft Preview のみ（送信ボタンなし）

詳細: [phase24_weekly_digest_email_outbox.md](./phase24_weekly_digest_email_outbox.md)

## 今後の Phase

- Phase 24.2: scheduled weekly digest
- Phase 24.3: Gmail API integration with explicit opt-in

## 注意事項

- This report is not a final conclusion.
- Web signals are signal candidates, not final conclusions.
- Papers are supporting evidence candidates, not proof of patent claims.
- Strategic Watch is not final conclusion.
- This is not FTO, infringement, or validity analysis.
- Preview only. Email sending is disabled in this phase.

## 関連モジュール

- `src/tech_cartography/delivery/`
- `src/tech_cartography/ui/delivery_ui.py`
- `scripts/build_delivery_package.py`
