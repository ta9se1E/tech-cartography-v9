# PatentScout AI v7 — Carbon Fiber Evidence Map

Patent Evidence Intelligence scaffold for carbon-fiber technology cartography.

v7 is a fresh project. It does not inherit v6's weekly-watch baseline as a bulk copy.

## Scope

- Carbon Fiber Evidence Map
- Patent Evidence Intelligence
- Tech cartography under `src/tech_cartography/`

## Layout

- `app.py` — application entry point
- `configs/` — runtime and case-study configuration
- `case_studies/carbon_fiber/` — carbon fiber reference cases
- `src/tech_cartography/` — core package
- `scripts/` — operational scripts
- `tests/` — test suite
- `data/reference/` — curated reference inputs
- `data/runtime/` — generated runtime artifacts (gitignored)
- `outputs/` — generated reports and exports (gitignored)

## Setup

Use the `2026hack` conda environment:

```bash
conda activate 2026hack
cd PatentScout_AI_v7
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

## Test

```bash
python -m pytest -q
```
