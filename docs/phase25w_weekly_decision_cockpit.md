# Phase 25W — Weekly Decision Cockpit and Demo Flow Simplification

## Weekly Decision Cockpit とは

既存 artifact（Watch Profile、Web Signal、Digest Preview、Evidence Gap、Strategic Watch Brief、Scheduler dry-run、Run History）を **読み取りだけ** で集約し、週次判断に必要な情報を1画面にまとめたコックピットです。

## なぜ7タブではなく1画面か

機能が増えると初見ユーザーは「何から見ればよいか」迷います。Deep Research 型の長文レポートではなく、Tech Cartography の価値は短時間で:

- 今週の変化候補
- Evidence Gap
- Next Verification Actions
- What Not To Conclude
- Source artifact / Run History

を確認できることです。

## 週30分で見る順番

1. 今週の確認対象テーマ
2. 今週の変化候補（候補のみ）
3. Evidence Gap Top 3
4. Next Verification Actions Top 3
5. What Not To Conclude
6. 必要なら詳細タブ（入力・実行 / Digest / Web Signal / Run History）

## Evidence Gap / Next Verification Actions との関係

Cockpit は Evidence Gap / Brief artifact を **参照** します。自動再生成はしません。

## Deep Research との差別化

- 外部 API / Deep Research API を呼ばない
- 長文レポートではなく構造化サマリー
- 候補情報・安全ラベル付き

## artifact 確認方法

`outputs/live_weekly_decision_cockpit/live_weekly_decision_cockpit_*.json`

## Run History

| action_type | 意味 |
|-------------|------|
| `live_weekly_decision_cockpit_build` | Cockpit 保存 |

## デモでの見せ方

1. **今週の判断** タブを開く
2. readiness_level と Top 3 gaps / actions を確認
3. admin で「Cockpit を保存」
4. Run History で `live_weekly_decision_cockpit_build` を確認
5. 詳細は「入力・実行」タブへ

## 禁止事項

- 外部 API / Deep Research API
- メール送信・Scheduler 起動
- Web Signal の確定事実化
- FTO / 侵害 / 有効性判断
- secret の保存・表示
