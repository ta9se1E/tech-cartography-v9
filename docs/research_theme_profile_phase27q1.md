# Research Theme Profile — Phase27Q.1

`ResearchThemeProfile` スキーマで研究テーマを構造化して保存・編集します。BigQuery SQL 生成と Input タブ UI の両方で利用します。

## フィールド

| フィールド | 説明 |
|-----------|------|
| `case_id` | 案件 ID |
| `theme_name` | テーマ名 |
| `theme_description` | テーマ説明 |
| `core_keywords` | コアキーワード（OR 一致、スコア +3） |
| `application_keywords` | 用途キーワード（+1） |
| `material_process_keywords` | 材料・プロセスキーワード（+2） |
| `exclude_keywords` | 除外キーワード（-10 / WHERE 除外） |
| `seed_publication_numbers` | シード公報番号（+10、必ず取得対象に含める） |
| `max_results` | 最大件数（上限 1000） |
| `countries` | 国コードフィルタ |
| `publication_year_from` / `publication_year_to` | 公開年範囲 |
| `search_mode` | `seed_and_keywords` / `keyword_only` / `seed_only` |
| `notes` | メモ |

## 動作ルール

- **seed が空** → `search_mode` は自動的に `keyword_only` にフォールバック
- **seed あり** → 標準は `seed_and_keywords`
- **publication number 正規化** — `JP2022090764A` / `JP-2022090764-A` / `jp2022090764a` を同一視
- BigQuery SQL では `REPLACE(publication_number, '-', '')` でも照合

## Case 1 初期値

- テーマ: PAN系炭素繊維前駆体の表面・内部欠陥制御
- 保存先: `cases/case_01_pan_graphitization/research_theme_profile.json`

## 安全上の注意

- claim 本文は Research Theme から生成しません
- FTO / 侵害 / 有効性判断は行いません
- score は読む優先度であり、特許価値ではありません
