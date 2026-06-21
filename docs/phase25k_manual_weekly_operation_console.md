# Phase 25K — Manual Weekly Operation Console

## Phase 25J との差分

| Phase | 内容 |
|-------|------|
| 25J | Watch Profile Draft → Next Cycle Search Plan → 手動 Tavily → Next Cycle Web Signal Pack |
| **25K** | **上記を含む Live 成果物の週次サイクル状態を一覧化する手動運用パネル** |

## なぜ運用パネルが必要か

Phase 25E〜25J で Live 機能は揃いましたが、成果物は Cloud Storage 上の複数ディレクトリに分散します。admin が「今どこまで進んだか」「次に何をすべきか」を一目で把握するため、**Live Operation Console** を追加しました。

## 手動週次運用の流れ

1. Web Signal Pack 作成
2. Digest Preview 作成（送信なし）
3. Self-only Email Send Test（任意）
4. Watch Expansion Proposals 作成
5. Watch Profile Draft 承認保存
6. Next Cycle Search Plan 作成
7. Next Cycle Web Signal Pack 作成（選択 query のみ Tavily）

**すべて手動。** 統合一括実行ボタンはありません。

## 各ステップの意味

| step | 意味 |
|------|------|
| web_signal_pack | Tavily → Web Signal candidate pack |
| digest_preview | 週次 Digest 下書き（送信なし） |
| self_only_email | 自分宛て1通テスト |
| watch_expansion_proposal | 監視範囲拡張候補 |
| watch_profile_draft | 人間承認済み Draft |
| next_cycle_search_plan | 次回 query 候補 |
| next_cycle_web_signal_pack | 次サイクル Web Signal Pack |

## 自動実行ではない

- scheduler **OFF** のまま
- 外部 API **自動実行なし**
- 一斉メール **なし**
- self_only メールのみ（Phase 25G までどおり）

## Cloud Storage 保存先

`LIVE_OUTPUTS_ROOT` 配下（例: `/mnt/live_artifacts/outputs`）

状態スナップショット: `live_operation_status/live_operation_status_<timestamp>.json`

## next_cycle_web_signal_pack が空の場合

- Plan あり / Pack なし → `ready`
- `DISABLE_EXTERNAL_API=true` → next_action に「外部APIを一時的にONにして…」
- Plan なし → `missing`

## 次 Phase

**運用パック共有** または **CI/CD** へ進む方針。
