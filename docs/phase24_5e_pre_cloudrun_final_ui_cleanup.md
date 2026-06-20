# Phase 24.5E — Pre-Cloud Run Final UI Cleanup

## 目的

Cloud Run 最小デプロイ前に、審査員・初見ユーザー向け画面から開発者向けノイズを除去する。

## 再現性確認ブロック

「再現性確認の現在地」（Evidence Map ready / Manual Claims Route required 等）は開発・検証用のため、Demo / 本番実行の通常表示から削除した。

- **はじめる** / **技術の裏取り** タブ下部の brief カードを非表示
- **開発者向け** モード選択時のみ、レポートタブの「開発者向け情報 / 詳細レポート」内で `render_reproducibility_smoke_section` として参照可能

Evidence Map Summary / Selected Evidence Papers / Evidence Gaps / Next Actions は従来どおり表示。

## 開発者向けモード

ローカル開発では run_id・outputs path・validation paths・scheduler・send log 等の確認に利用する。Cloud Run 提出画面では非表示を推奨。

## SHOW_DEVELOPER_MODE

| 値 | 挙動 |
|----|------|
| 未設定 | **false 相当** — 「開発者向け」をサイドバーに出さない |
| `false` / `0` / 空 | 同上 |
| `true` / `1` / `yes` / `on` | 「開発者向け」をサイドバーに表示 |

ローカルでのみ `.env` に設定:

```bash
SHOW_DEVELOPER_MODE=true
```

Cloud Run では **未設定のまま**（= false）でデプロイしてください。

## SHOW_DEVELOPER_MODE=false 時

- サイドバー: デモを見る / 本番実行 のみ
- run_id / outputs path / validation paths / scheduler / send log を通常表示しない
- 設定タブ: 「開発者向け情報は提出用画面では非表示です。」のみ（Cloud Run チェックリスト等は非表示）

## SHOW_DEVELOPER_MODE=true 時

- 従来どおり「開発者向け」を選択可能
- サイドバー expander・レポート詳細 expander で技術情報を確認可能

## 次ステップ

Phase 24.5E 完了後 → **Cloud Run minimal deploy**
