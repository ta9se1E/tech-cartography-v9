# Phase 25A — Streamlit Basic Login Gate

## 目的

Cloud Run 上で本番実行機能を解放する前に、Streamlit アプリ内で **ユーザー名・パスワード** による簡易ログインを追加する。IAP / OAuth / DB は使わない。

## 認証方式（優先順）

### 1. Simple env login（Cloud Run live 推奨）

| 変数 | 説明 |
|------|------|
| `REQUIRE_LOGIN` | `true` でログインゲート有効 |
| `TECH_CARTOGRAPHY_LOGIN_USERNAME` | ログイン username |
| `TECH_CARTOGRAPHY_LOGIN_PASSWORD` | ログイン password（Cloud Run env / Secret で設定） |

`TECH_CARTOGRAPHY_LOGIN_PASSWORD` が設定されている場合、**bcrypt JSON より優先**して単純照合します。

成功時:

- `authenticated=True`
- `username` = env username
- `role=admin`
- `display_name=username`

### 2. bcrypt JSON fallback

`TECH_CARTOGRAPHY_LOGIN_PASSWORD` が **未設定** の場合のみ、`TECH_CARTOGRAPHY_USERS_JSON`（bcrypt hash）を使用。

```bash
python scripts/generate_password_hash.py --password "your-password"
```

## REQUIRE_LOGIN の挙動

| 値 | 挙動 |
|----|------|
| 未設定 / `false` | 既存のメールアドレスログイン。Cloud Run **demo** はこの設定 |
| `true` | 未ログイン時はログイン画面のみ。成功後に本体 UI |

## 本番実行系ガード（ログイン後のみ）

- 本番実行タブ / 外部 API チェックボックス
- Watch Profile / 週次メール設定
- メール下書きプレビュー
- scheduler（admin のみ）

## Cloud Run 設定例

### Demo

```bash
REQUIRE_LOGIN=false
APP_DEFAULT_MODE=demo
DEMO_OUTPUTS_ROOT=demo_outputs
```

### Live beta（simple login）

```bash
REQUIRE_LOGIN=true
APP_DEFAULT_MODE=analyst
TECH_CARTOGRAPHY_LOGIN_USERNAME=admin
TECH_CARTOGRAPHY_LOGIN_PASSWORD=<set-in-cloud-run-env-or-secret>
DISABLE_EXTERNAL_API=true
DISABLE_EMAIL_SEND=true
DISABLE_SCHEDULER=true
```

**注意:** パスワードをコードや git に含めない。画面・ログに password 値を出さない。

## モジュール

- `src/tech_cartography/auth/basic_auth.py`
- `src/tech_cartography/ui/login_ui.py`

## テスト

- `tests/test_basic_auth.py`
- `tests/test_login_gate.py`
