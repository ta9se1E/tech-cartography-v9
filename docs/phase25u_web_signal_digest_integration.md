# Phase 25U — Web Signal Digest Integration and Evidence Review

## 目的

Phase 25T で手動収集した Web Signal collection artifact を読み取り、Digest Preview に **候補情報** として統合します。外部 API は呼びません。

## Phase 25T との関係

| Phase | 役割 |
|-------|------|
| 25T | active Watch Profile から Tavily で候補を **手動収集** → `live_web_signal_collection_*.json` |
| 25U | 収集済み artifact を **読むだけ** → Review 整理 → Digest Preview に統合 |

## 読むだけであること

- `live_web_signal_artifact_reader.py` は `outputs/live_web_signals/` の json を読むのみ
- Digest Preview 作成時に Tavily / 外部 API を呼ばない
- Scheduler dry-run も artifact パス参照のみ

## Digest Preview への統合内容

Digest に **Web Signal候補** セクションを追加:

- source artifact path
- result_count / queries_used
- top candidate signals（`confidence_label=candidate`）
- domain summary
- caution notes
- 「候補情報であり確定事実ではありません」
- 「FTO/侵害/有効性判断ではありません」

artifact がない場合: 「Web Signal候補はまだ収集されていません」

## Web Signal は候補情報

- `candidate_information_only=true`
- `legal_judgement=false`, `fto_judgement=false`, `infringement_judgement=false`, `validity_judgement=false`
- 人間による原典確認が前提

## artifact 確認方法

`LIVE_OUTPUTS_ROOT/live_web_signals/`:

- `live_web_signal_collection_success_*.json`
- `live_web_signal_review_*.json`（Review 保存時）
- `live_digest_preview_*.json`（`uses_web_signals`, `source_web_signal_artifact` フィールド）

## Run History 確認方法

| action_type | 意味 |
|-------------|------|
| `live_digest_preview` | Web Signal artifact なしで Digest 保存（`uses_web_signals=false`） |
| `live_web_signal_review` | Review 生成・保存 |
| `live_digest_preview_with_web_signals` | Web Signal artifact 参照付き Digest 保存 |

### IAP admin で Digest Preview を実行

IAP ログイン済み admin（例: `ta9se1@gmail.com`）は Digest Preview 作成が許可されます。
UI / サービスは `user_context`（`auth_provider=google_iap`, `role=admin`）を優先し、
旧 Basic ログイン session だけを見て blocked にしません。

### 成功時の Run History 期待値

| フィールド | 期待値 |
|-----------|--------|
| `user_id` | `ta9se1@gmail.com`（IAP email） |
| `auth_provider` | `google_iap` |
| `role` | `admin` |
| `status` | `success` |
| `output_artifact_paths` | Digest Preview の `json` / `markdown` / `text` |
| `source_artifact_paths` | pack path +（Web Signal あり時）collection artifact path |
| `operation_metadata.uses_web_signals` | `true` / `false` |

### blocked 時の見方

- `status=blocked` かつ `error_summary=ログイン後に実行できます。` だが
  `auth_provider=google_iap` / `role=admin` が記録されている場合 → **認証ガード不整合**（Phase 25U.1 で修正対象）
- `admin権限が必要です。` → IAP member など admin 以外
- Digest Preview 作成は外部 API を呼びません（Tavily なし）
- Web Signal は候補情報のみ（FTO / 侵害 / 有効性判断なし）

## デモ時の見せ方

1. Live Operation Console で最新 Web Signal artifact 概要を確認
2. **Web Signal Review** expander で domain summary / top candidates を確認
3. Digest Preview を作成 → **Web Signal候補** セクション付き markdown を表示
4. Run History で `live_digest_preview_with_web_signals` を確認

## 禁止事項

- 外部 API の自動実行
- Digest Preview / Scheduler dry-run からの Tavily 呼び出し
- メール送信・Scheduler 起動
- Web Signal を確定事実として扱うこと
- FTO / 侵害 / 有効性判断
- secret / TAVILY_API_KEY の保存・表示
