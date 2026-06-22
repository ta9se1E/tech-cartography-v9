# Phase 25M — User Run Context and Execution History

## Phase 25L との差分

| Phase | 内容 |
|-------|------|
| 25L | Live Beta Release Pack（関係者向け handoff） |
| **25M** | **User Context + 実行履歴（Run History）の記録・表示** |

## なぜ User Run Context が必要か

Live Beta では複数の手動アクションが週次サイクルで実行されます。業務上「誰が・いつ・何を実行したか」を追えるようにするため、ログインユーザー情報を共通形式で扱い、各成果物と実行履歴に紐付けます。

**これは監査ログではありません。** IP アドレス・User-Agent・法的監査証跡は対象外です。

## user_id / role / run_id の考え方

| 項目 | 意味 |
|------|------|
| `user_id` | ログインユーザー名（例: `admin`, `member01`） |
| `role` | `admin` または `member` |
| `run_id` | 1回の手動実行を識別する ID（例: `run-abc123`） |
| `auth_provider` | 現状 `streamlit_basic`（将来 IAP / Google login へ差し替え可能） |

各 Live 成果物 JSON には可能な範囲で以下を付与:

- `run_id`
- `created_by_user_id`
- `created_by_display_name`
- `created_by_role`
- `created_by_auth_provider`

## 保存先仕様

実行履歴: `LIVE_OUTPUTS_ROOT/live_run_history/`

- `run_history_<timestamp>_<run_id>.json`
- `run_history_<timestamp>_<run_id>.md`

## secret を保存しない方針

Run History および成果物に以下は含めません:

- ログインパスワード
- API キー
- SMTP 設定値
- メール本文全文
- 送信先メールの大量リスト

`input_summary` は短く sanitize し、env 値リークを拒否します。

## Optional Multi-user Basic Login

環境変数:

- `ENABLE_MULTI_USER_LOGIN=true` — 複数ユーザー JSON ログインを有効化
- `TECH_CARTOGRAPHY_USERS_JSON` — ユーザー配列（`password_hash` は pbkdf2_sha256 または bcrypt）

未設定時は従来どおり `TECH_CARTOGRAPHY_LOGIN_USERNAME` / `PASSWORD` の単一 admin ログインです。

ハッシュ生成:

```bash
python scripts/generate_login_password_hash.py --json --username member01 --role member
```

## 将来 Google Login / IAP へ接続する方針

`user_context.py` は `auth_provider` を抽象化しており、IAP 導入時は provider 実装を差し替えるだけで Run History 連携を維持できます。

## 次 Phase 候補

- Google Login / IAP
- CI/CD
- 承認付きメンバー送信
- scheduler（本 Phase では OFF のまま）
