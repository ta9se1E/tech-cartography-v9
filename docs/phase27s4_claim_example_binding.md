# Phase27S.4 — Claim-Example Evidence Binding

## Purpose

Bind `claims_input.csv` claim text to extracted `example_facts.csv` within the same `publication_number`. Output is **candidate links only** — not verified evidence.

## Input

- `cases/{case_id}/claims_input.csv`
- `outputs/local_v8_example_facts/{case_id}_*/example_facts.csv` (latest auto-detected)
- `cases/{case_id}/extraction_vocabulary.json` (optional focus hints)

## Output

`outputs/local_v8_claim_example_links/{case_id}_{timestamp}_{hash}/`

- `claim_example_links.csv` / `.json` / `.md`
- `claim_example_binding_summary.csv` / `.md`
- `claim_example_review_prompts.md` (future Gemini review — no live call in S.4)

## Binding method

Rule-based keyword / field overlap scoring — no LLM in this phase.

## Next phase

Gap logic update to consume `claim_example_links` as supporting candidates.
