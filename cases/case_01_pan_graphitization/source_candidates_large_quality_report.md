# Large Candidate Quality Report — case_01_pan_graphitization

- imported_at: 2026-06-27T01:16:02+00:00
- input_path: /Users/esakitakusei/Documents/python/practice/portfolio/2026_Hackathon/PatentScout_AI_v8/cases/case_01_pan_graphitization/large_candidates/case_01_bigquery_export_1000.csv
- accepted: 1000
- rejected: 0

## Safety
- 1000件候補は母集団であり、全件を Claim Map / Evidence Map で深掘りしません。
- Top100 / Top20 / Top5 の段階選抜後、Top5 またはユーザー選択のみ深掘り対象です。
- heuristic_score は読む優先度の暫定値であり、技術的正しさ・特許価値・法的価値ではありません。
- FTO、侵害、有効性判断、法的結論は行いません。
- 重複除去は暫定 heuristic です。family_id や title 類似だけで同一特許と断定しません。
- 本 Phase では外部 API / BigQuery 実行 / メール送信 / Scheduler 起動を行いません。