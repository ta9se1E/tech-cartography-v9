# Phase27S.0.1 — pytest failure triage report

Generated: 2026-06-28  
Base commit: `aac7bd78df7d342ed373cb28c28077f1e360d9b1` (tag: `v8-phase27s0-google-patents-pdf-links`)

## Summary

| Metric | Result |
|--------|--------|
| Full pytest | **1841 passed**, **12 failed**, **5 errors** |
| S.0 targeted (`test_v8_google_patents_links_phase27s0.py`) | **12 passed** |
| S.0 + related v8 UI tests (34 tests) | **34 passed** |
| readiness | **PASS** |
| **Phase27S.0 起因の失敗** | **0件** |

**結論: S.1（PDF解析）へ進行可能。** 全体 pytest の失敗はすべて Phase27S.0 以前から存在する環境依存・別 Phase の既知問題。

---

## 失敗テスト一覧（12 FAILED）

| # | テスト | 原因分類 | S.0関連 |
|---|--------|----------|---------|
| 1 | `tests/test_basic_auth.py::test_password_hash_not_equal_to_plaintext` | `ModuleNotFoundError: bcrypt` | いいえ |
| 2 | `tests/test_bigquery_light_retriever.py::test_dry_run_query_mock_returns_estimated_bytes` | dry_run status `error`（`google.cloud` 未インストール影響の可能性） | いいえ |
| 3 | `tests/test_bigquery_light_retriever.py::test_execute_true_passes_maximum_bytes_billed` | `ModuleNotFoundError: google.cloud` | いいえ |
| 4 | `tests/test_patent_fulltext_retriever.py::test_execute_passes_maximum_bytes_billed` | `ModuleNotFoundError: google.cloud` | いいえ |
| 5 | `tests/test_v8_bigquery_runner_phase27q1.py::test_dry_run_with_fake_client` | `ModuleNotFoundError: google.cloud` | いいえ |
| 6 | `tests/test_v8_bigquery_runner_phase27q1.py::test_execute_with_fake_client` | `ModuleNotFoundError: google.cloud` | いいえ |
| 7 | `tests/test_v8_case_validation_ui_phase27i.py::test_intro_ui_phase27i_guidance` | intro UI 文言が Judge Mode 移行（27R.1/R.2）で `v8_intro_ui.py` から削除 | いいえ |
| 8 | `tests/test_v8_cloud_run_readiness_ui_phase27n.py::test_intro_ui_phase27n` | 同上（`deploy` / `Cloud Run` 文言が intro から移動） | いいえ |
| 9 | `tests/test_v8_large_candidate_ui_phase27j0.py::test_input_ui_large_candidate_import` | テスト期待 `"1000件候補"`、実装は `"1000件は母集団"`（27R.2 以前から） | いいえ* |
| 10 | `tests/test_v8_one_case_demo_e2e_ui_phase27n5.py::test_intro_case1_real_demo` | intro 文言 Judge Mode 移行 | いいえ |
| 11 | `tests/test_web_signal_mapper.py::test_map_web_signals_to_patents` | `zip(..., strict=True)` — Python 3.9 非対応 | いいえ |
| 12 | `tests/test_web_signal_report.py::test_report_markdown_sections` | 同上 | いいえ |

\* S.0 は `v8_input_ui.py` の PDF セクションのみ変更。CSV 取込 expander の文言は未変更。

## ERROR 一覧（5 ERRORS）

すべて `tests/test_basic_auth.py` の fixture `sample_users_json` セットアップ時:

| テスト | 原因 |
|--------|------|
| `test_simple_login_takes_priority_over_bcrypt` | `hash_password()` → `import bcrypt` → ModuleNotFoundError |
| `test_bcrypt_fallback_when_simple_password_missing` | 同上 |
| `test_authenticate_success` | 同上 |
| `test_authenticate_wrong_password` | 同上 |
| `test_authenticate_unknown_user` | 同上 |

---

## Phase27S.0 変更ファイルとの関係

```
git diff --name-only v8-before-phase27s0-google-patents-links..HEAD
```

- `src/tech_cartography/runtime/v8_google_patents_links_schema.py`（新規）
- `src/tech_cartography/services/v8_google_patents_links.py`（新規）
- `src/tech_cartography/ui/v8_google_patents_links_ui.py`（新規）
- `src/tech_cartography/ui/v8_patent_shortlist_ui.py`
- `src/tech_cartography/ui/v8_top5_reading_ui.py`
- `src/tech_cartography/ui/v8_input_ui.py`（PDF セクション追加）
- `src/tech_cartography/ui/v8_gap_next_actions_ui.py`（example_support_missing 案内）
- `src/tech_cartography/ui/v8_judge_mode_copy.py`（PDF_UPLOAD_HELP）
- `tests/test_v8_google_patents_links_phase27s0.py`（新規）

失敗ログ内に `google_patents` / `v8_google` の参照は **0件**。

---

## 原因分類

### A. 環境依存 — オプション依存パッケージ未インストール（10件: 5 errors + 5 fails）

- **bcrypt**（6件）: ローカル dev 環境に `bcrypt` 未インストール。Cloud Run 本番では requirements に含まれる想定。
- **google.cloud**（4件）: `google-cloud-bigquery` 未インストール。BigQuery は提出デモでは OFF。

**後回し理由:** S.0 / S.1 と無関係。CI で optional extra を入れるか、mock を import 前に patch する別 Phase で対応。

### B. UI 文言スナップショットテスト陳腐化（3件）

Phase 27R.1/R.2 で intro コンテンツが `v8_judge_mode_ui.py` / `v8_judge_mode_copy.py` へ移行したが、Phase 27I/N/N.5 の UI テストが旧 intro 文字列を期待している。

**後回し理由:** S.0 非起因。Judge Mode リファクタのテスト追随タスクとして別 commit で修正可能。

### C. 脆い文字列マッチ（1件）

`test_input_ui_large_candidate_import` が `"1000件候補"` を期待。実装は Phase 27R.2 以降 `"1000件は母集団"`。

**後回し理由:** S.0 非起因。1行のテスト期待値更新で解消可能（別 Phase）。

### D. Python バージョン（2件）

`web_signal_mapper.py` の `zip(..., strict=True)` は Python 3.10+ 構文。実行環境: **Python 3.9**。

**後回し理由:** S.0 非起因。`strict=False` 相当への互換修正は別 Phase。

---

## Cloud Run 提出前の優先度

| 優先度 | 項目 | 対応時期 |
|--------|------|----------|
| 高（提出前） | S.0 機能・readiness・S.0 pytest | **完了済み** |
| 中（CI整備） | bcrypt / google.cloud を dev requirements または CI に追加 | 別 Phase |
| 低（品質） | intro UI スナップショットテスト更新 | 別 Phase |
| 低（品質） | web_signal `zip(strict=True)` Python 3.9 互換 | 別 Phase |
| 低（品質） | `1000件候補` テスト期待値 | 1行修正で可 |

**S.1 PDF解析はブロックされない。**

---

## 検証コマンド結果（triage 時点）

```bash
python -m pytest -q tests/test_v8_google_patents_links_phase27s0.py  # 12 passed
python -m compileall scripts src tests app.py                      # PASS
python scripts/check_v8_reframe_ready.py                           # PASS
python -m pytest -q                                                # 1841 passed, 12 failed, 5 errors
```

## ログファイル

- `outputs/debug_patches/pytest_phase27s0_full_failure.log` — 全文
- `outputs/debug_patches/pytest_phase27s0_failure_summary.log` — FAILED/ERROR 抽出
