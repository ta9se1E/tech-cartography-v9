# Phase 25N — Google IAP-ready Authentication Bridge

## Phase 25M との差分

| Phase | 内容 |
|-------|------|
| 25M | UserContext + Run History（手動実行履歴） |
| **25N** | **Google IAP / JWT 受け皿 + AUTH_PROVIDER_MODE + role mapping** |

## AUTH_PROVIDER_MODE の意味

| 値 | 動作 |
|----|------|
| `basic`（未設定時デフォルト） | 既存 Basic Login のみ |
| `iap` | IAP ヘッダーから UserContext を構築。ヘッダーなしは安全停止 |
| `hybrid` | IAP ヘッダーがあれば IAP、なければ Basic Login fallback |

## IAP header から UserContext を作る方針

- `X-Goog-Authenticated-User-Email` → `accounts.google.com:user@example.com` を正規化
- `user_id` = lowercase email
- `auth_provider` = `google_iap`
- password / JWT 全文は含めない

## IAP JWT verification mode

| IAP_JWT_VERIFY_MODE | 動作 |
|---------------------|------|
| `off`（未設定時） | ヘッダー解析のみ。production caution を表示 |
| `optional` | JWT があれば検証を試行。失敗は warning |
| `strict` | JWT 検証失敗でログイン不可。`IAP_EXPECTED_AUDIENCE` 必須 |

`google-auth` が利用可能な場合のみ検証を実行。不足時は `unavailable`。

## Role mapping env

- `TECH_CARTOGRAPHY_ADMIN_EMAILS` — カンマ区切り → `role=admin`
- `TECH_CARTOGRAPHY_MEMBER_EMAILS` — カンマ区切り → `role=member`
- `TECH_CARTOGRAPHY_ALLOWED_EMAIL_DOMAINS` — カンマ区切り → `role=member`

未許可 email:
- `iap` mode → access_denied
- `hybrid` mode → IAP identity がある場合は access_denied（Basic fallback しない）

## Run History との接続

Run History には Phase25M どおり以下が入ります:

- IAP user: `auth_provider=google_iap`, `user_id=email`
- Basic user: `auth_provider=streamlit_basic`

JWT / password は保存しません。

## まだ GCP 側 IAP を強制 ON しない理由

この Phase はアプリ側の受け皿のみです。Cloud Run / Load Balancer / IAP の GCP 設定は次 Phase（25O Runbook）で段階的に行います。

## 本番切替時の注意

- Direct Cloud Run URL に IAP ヘッダーだけを信頼しないこと
- `IAP_JWT_VERIFY_MODE=strict` + audience 設定を推奨
- role mapping env を事前に設定すること

## secret / JWT / password 非保存方針

UI・Run History・診断表示に以下を含めません:

- password / password_hash
- JWT 全文
- API キー / SMTP 設定

## 次 Phase 候補

- Phase25O: Cloud Run IAP Cutover Runbook
- Phase25P: CI/CD
- Phase25Q: 承認付きメンバー送信
- Phase25R: scheduler
