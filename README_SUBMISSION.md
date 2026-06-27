# Tech Cartography / PatentScout AI v8 — Submission README

## Phase27Q.1 ハイライト

- **Structured Research Theme** — テーマ名・説明・キーワード群・除外・seed publication numbers
- **Claim CSV/Excel Batch Import** — Top5 請求項を `manual_input` として一括投入
- **BigQuery Admin Runner** — 管理者限定、提出時 OFF

## 提出デモ URL

Cloud Run: デプロイ済み revision を `docs/cloud_run_v8_deployment_result.md` 参照

## 安全設計（提出時必須）

| 機能 | 提出時 |
|------|--------|
| BigQuery 直接実行 | **OFF / 非表示** |
| Claim 本文 | **CSV/Excel / 手動のみ** |
| JP/CN claim from BQ | **取得しない** |
| メール送信 | **OFF** |
| Scheduler | **OFF** |
| FTO / 侵害 / 有効性 | **なし** |

## 推奨デモ手順

1. Case 1（PAN 前駆体欠陥制御）を選択
2. 既存 Large Candidate CSV で Sources → Shortlist
3. Claim Map で CN108286090A の manual claim を確認
4. Claim 一括投入 UI で残り Top5 を説明（実際の claim はユーザー提供）
5. Evidence Map / Gap / Next Actions

## 環境変数（Cloud Run 提出時）

```
ENABLE_BIGQUERY_RUN=false
SHOW_BIGQUERY_ADMIN=false
BIGQUERY_DRY_RUN_ONLY=true
BIGQUERY_ALLOW_EXECUTE=false
ENABLE_EMAIL_SEND=false
ENABLE_SCHEDULER=false
DISABLE_EMAIL_SEND=true
DISABLE_SCHEDULER=true
```

## 詳細ドキュメント

- [Research Theme Profile](docs/research_theme_profile_phase27q1.md)
- [Claim Batch Import](docs/claim_batch_import_phase27q1.md)
- [BigQuery Admin Runner](docs/bigquery_admin_runner_phase27q1.md)
- [Submission Demo Operation Guide](docs/submission_demo_operation_guide.md)

## 検証コマンド

```bash
conda run -n 2026hack python -m pytest -q
conda run -n 2026hack python scripts/check_v8_reframe_ready.py
```

## Tag

`v8-phase27q1-admin-bigquery-claim-import`
