# Phase 24.1 — Weekly Digest Email Outbox

## 目的

Phase 24.0 で作成した Weekly Digest Preview / Intelligence Report / Digest Diff を、実運用に近いメール連絡形式へ改善します。

- Weekly Digest 本文の読みやすさ改善（日本語中心）
- Top 3 Watch Items の重複抑制
- 文章の途中切れ防止
- Email Outbox による Draft 管理
- **明示オプション付きの安全な送信準備**（`--send-email` のみ）

## Digest polish の内容

### Top 3 重複抑制

`select_diverse_top_watch_items()` が以下を避けて多様な 3 件を選びます。

- 同じ `watch_theme` の連続採用
- 同じ `related_web_signal_title`
- 同じ `related_paper_title`
- 可能なら `watch_type` の分散（national_project_signal / patent_paper_web_signal / money_signal 等）

見出しは `build_digest_item_title()` で NEDO/JST/METI 等のソースタイトルを優先表示します。

### 文章の途中切れ防止

`truncate_at_sentence_boundary()` が句点（`。` / `.`）または語境界で切り、末尾に `（要確認）` を付けます。

### 日本語メール本文

主な見出し:

- `# Tech Cartography Weekly Digest`
- `## 今週の差分`
- `## 今週の重点監視候補 Top 3`
- `## 新規・更新シグナル`
- `## Evidence Gaps`
- `## Next Verification Actions`
- `## Important Caveats`

英語補足行（`_English supplement: ..._`）を必要箇所に残します。

## Email Outbox の仕組み

保存先: `outputs/delivery/email_outbox/`

| ファイル | 内容 |
|---------|------|
| `email_draft_{pub}.md` | Draft サマリー + 本文プレビュー |
| `email_draft_{pub}.html` | HTML 本文 |
| `email_draft_{pub}.json` | EmailDraft メタデータ |
| `outbox_index.json` | Outbox インデックス |

### EmailDraft schema

- `draft_id`, `created_at`, `publication_number`
- `to`, `cc`, `subject`
- `markdown_body`, `html_body`, `attachments`
- `status`: `preview_only` / `draft_saved` / `blocked_missing_recipient` / `blocked_missing_adapter` / `sent` / `failed`
- `caveats`

## Draft only / Preview only / Send explicit

| モード | 条件 | status |
|--------|------|--------|
| Preview only | `--build-email-draft` なし | digest のみ `preview_only` |
| Draft saved | `--build-email-draft --email-to ...`（`--send-email` なし） | `draft_saved` |
| Blocked recipient | `--send-email` だが `--email-to` なし | `blocked_missing_recipient` |
| Blocked adapter | `--send-email` だが SMTP 未設定 | `blocked_missing_adapter` |
| Sent | `--send-email` + SMTP 設定済み | `sent` |

## SMTP 環境変数（optional）

```
TC_SMTP_HOST
TC_SMTP_PORT
TC_SMTP_USER
TC_SMTP_PASSWORD
TC_SMTP_FROM
```

未設定時は送信せず `blocked_missing_adapter` とします。パスワードはログ・出力に保存しません。

Gmail API / OAuth は **この Phase では実装しません**（次 Phase 以降の optional integration）。

## UI では送信しない理由

Streamlit UI からの誤送信を防ぐため、Email Draft Preview のみ表示し、実送信は CLI の `--send-email` 明示時のみとします。

UI 表示: *"Email sending is disabled from the UI. Use CLI with --send-email for explicit sending."*

## CLI 実行例

### Draft only

```bash
python scripts/build_delivery_package.py \
  --publication-number US-12565719-B2 \
  --output-dir outputs/delivery \
  --include-zip \
  --build-email-draft \
  --email-to reviewer@example.com
```

### Send 明示（SMTP 設定済みの場合のみ）

```bash
python scripts/build_delivery_package.py \
  --publication-number US-12565719-B2 \
  --output-dir outputs/delivery \
  --include-zip \
  --build-email-draft \
  --email-to reviewer@example.com \
  --send-email
```

### Dry run

```bash
python scripts/build_delivery_package.py \
  --publication-number US-12565719-B2 \
  --dry-run
```

## 注意事項

- FTO / 侵害 / 有効性判断ではありません
- Web signals are signal candidates, not final conclusions
- Papers are supporting evidence candidates, not proof of patent claims
- Strategic Watch is not final conclusion
- Synthetic demo signal must be clearly labeled
- 金額の断定表示なし
- high confidence の自動付与なし
