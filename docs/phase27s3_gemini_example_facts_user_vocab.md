# Phase27S.3 — Gemini Example Facts with User Vocabulary

## Purpose

Extract structured example facts from patent `examples` / `comparative_examples` / `tables` sections using Gemini, guided by user-editable extraction focus vocabulary.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_GEMINI_EXAMPLE_FACTS` | `false` | Live Gemini calls only when `true` **and** user clicks extract |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Model name for google-genai |
| `GEMINI_PROVIDER` | `vertex_ai_or_google_genai` | Provider hint (documentation) |
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` | — | API key for google-genai Client |

## Vocabulary storage

- Per case: `cases/{case_id}/extraction_vocabulary.json`
- Copied to each example facts output pack

## Output

`outputs/local_v8_example_facts/{case_id}_{timestamp}_{hash}/`

- `example_facts.csv` / `.json` / `.md`
- `example_facts_summary.csv` / `.md`
- `gemini_prompts.md`
- `extraction_vocabulary.json`

## Safety

- Facts are **candidates** — `needs_human_review=true` by default
- Vocabulary is focus hints only — not a source of invented facts
- No OpenAI API in this phase
- No OCR, no PDF auto-download, no Google Patents scraping
- No claim generation, no legal/FTO/infringement/validity judgement

## UI

Input tab:

1. **抽出フォーカス語彙** — edit/save keywords
2. **Gemini実施例ファクト抽出** — extract or export prompts when Gemini disabled
