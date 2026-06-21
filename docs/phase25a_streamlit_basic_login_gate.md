# Phase 25A — Streamlit Basic Login Gate

## 目的

Cloud Run 上で本番実行機能を解放する前に、Streamlit アプリ内で **ユーザー名・パスワード** による簡易ログインを追加する。IAP / OAuth / DB は使わない。

## 認証方式

- 環境変数 `TECH_CARTOGRAPHY_USERS_JSON` にユーザー一覧（bcrypt `password_hash`）を設定
- `bcrypt` で平文パスワードを照合（平文は保存しない）
- ログイン成功後 `session_state` に `authenticated` / `username` / `role` / `display_name` を保存

## 環境変数

| 変数 | 例 | 説明 |
|------|-----|------|
| `REQUIRE_LOGIN` | `false` / `true` | `true` のとき username/password ゲートを有効化 |
| `TECH_CARTOGRAPHY_USERS_JSON` | JSON 配列 | ユーザー定義（bcrypt hash のみ） |

### ユーザー JSON 例

```json
[
  {
    "username": "admin",
    "password_hash": "<bcrypt_hash>",
    "role": "admin",
    "display_name": "Admin"
  }
]
```

## パスワードハッシュ生成

```bash
python scripts/generate_password_hash.py
# または
python scripts/generate_password_hash.py --password "your-password"
```

出力された bcrypt hash のみを `TECH_CARTOGRAPHY_USERS_JSON` に設定する。平文パスワードは git に含めない。

## REQUIRE_LOGIN の挙動

| 値 | 挙動 |
|----|------|
| 未設定 / `false` | 既存のメールアドレスログイン（Phase 24 までどおり）。Cloud Run **demo** はこの設定 |
| `true` | username/password ログイン画面のみ表示。成功後に本体 UI。live 想定 |

## 本番実行系ガード（ログイン後のみ）

- 本番実行タブ（テーマ入力・E2E Chain）
- 外部 API 実行チェックボックス
- Watch Profile / 週次メール設定の更新
- scheduler 設定（**admin** のみ）

`DISABLE_EXTERNAL_API=true` 等の Cloud Run 安全フラグは従来どおり優先。

## role

- `member`: 通常利用者（本番実行系はログイン後に利用可）
- `admin`: 管理者（scheduler 参照・開発者向けモード切替時に admin 必須）

## Cloud Run 設定例

### Demo（既存）

```bash
REQUIRE_LOGIN=false
APP_DEFAULT_MODE=demo
DEMO_OUTPUTS_ROOT=demo_outputs
```

### Live beta

```bash
REQUIRE_LOGIN=true
APP_DEFAULT_MODE=analyst
TECH_CARTOGRAPHY_USERS_JSON='[{"username":"admin","password_hash":"<bcrypt_hash>","role":"admin","display_name":"Admin"}]'
```

## モジュール

- `src/tech_cartography/auth/basic_auth.py` — 認証ロジック
- `src/tech_cartography/ui/login_ui.py` — ログイン UI / ガード

## テスト

- `tests/test_basic_auth.py`
- `tests/test_login_gate.py`
