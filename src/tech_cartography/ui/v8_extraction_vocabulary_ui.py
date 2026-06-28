"""Extraction focus vocabulary UI (Phase 27S.3)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from tech_cartography.runtime.v8_extraction_vocabulary_schema import ExtractionVocabulary, VOCABULARY_NOTICES
from tech_cartography.services.v8_extraction_vocabulary import (
  get_default_extraction_vocabulary,
  keywords_to_text,
  load_extraction_vocabulary,
  parse_keyword_text,
  save_extraction_vocabulary,
)
from tech_cartography.ui.v8_judge_mode_copy import EXTRACTION_VOCABULARY_HELP


def _session_form_key(case_id: str) -> str:
  return f"v8_vocab_form_{case_id}"


def _ensure_form_state(case_id: str, project_root: Path) -> dict[str, str]:
  key = _session_form_key(case_id)
  if key not in st.session_state:
    vocab = load_extraction_vocabulary(case_id, project_root)
    st.session_state[key] = {
      "material_keywords": keywords_to_text(vocab.material_keywords),
      "process_keywords": keywords_to_text(vocab.process_keywords),
      "property_keywords": keywords_to_text(vocab.property_keywords),
      "structure_keywords": keywords_to_text(vocab.structure_keywords),
      "comparison_keywords": keywords_to_text(vocab.comparison_keywords),
      "table_keywords": keywords_to_text(vocab.table_keywords),
      "exclusion_keywords": keywords_to_text(vocab.exclusion_keywords),
      "user_notes": vocab.user_notes or "",
    }
  return st.session_state[key]


def _form_to_vocabulary(case_id: str, project_root: Path, form: dict[str, str]) -> ExtractionVocabulary:
  base = load_extraction_vocabulary(case_id, project_root)
  return ExtractionVocabulary(
    case_id=case_id,
    theme_name=base.theme_name,
    theme_description=base.theme_description,
    material_keywords=parse_keyword_text(form.get("material_keywords", "")),
    process_keywords=parse_keyword_text(form.get("process_keywords", "")),
    property_keywords=parse_keyword_text(form.get("property_keywords", "")),
    structure_keywords=parse_keyword_text(form.get("structure_keywords", "")),
    comparison_keywords=parse_keyword_text(form.get("comparison_keywords", "")),
    table_keywords=parse_keyword_text(form.get("table_keywords", "")),
    exclusion_keywords=parse_keyword_text(form.get("exclusion_keywords", "")),
    user_notes=form.get("user_notes") or None,
    source="user",
  )


def render_extraction_vocabulary_section(
  case_id: str,
  project_root: Path,
  *,
  key_prefix: str = "v8_vocab",
) -> ExtractionVocabulary:
  st.markdown("#### 抽出フォーカス語彙")
  st.caption(EXTRACTION_VOCABULARY_HELP)
  for notice in VOCABULARY_NOTICES:
    st.caption(notice)

  saved = load_extraction_vocabulary(case_id, project_root)
  form = _ensure_form_state(case_id, project_root)

  col_load, col_reset = st.columns(2)
  with col_load:
    if st.button("Load current vocabulary", key=f"{key_prefix}_load"):
      vocab = load_extraction_vocabulary(case_id, project_root)
      st.session_state[_session_form_key(case_id)] = {
        "material_keywords": keywords_to_text(vocab.material_keywords),
        "process_keywords": keywords_to_text(vocab.process_keywords),
        "property_keywords": keywords_to_text(vocab.property_keywords),
        "structure_keywords": keywords_to_text(vocab.structure_keywords),
        "comparison_keywords": keywords_to_text(vocab.comparison_keywords),
        "table_keywords": keywords_to_text(vocab.table_keywords),
        "exclusion_keywords": keywords_to_text(vocab.exclusion_keywords),
        "user_notes": vocab.user_notes or "",
      }
      st.rerun()
  with col_reset:
    if st.button("Reset to Case default", key=f"{key_prefix}_reset"):
      vocab = get_default_extraction_vocabulary(case_id)
      st.session_state[_session_form_key(case_id)] = {
        "material_keywords": keywords_to_text(vocab.material_keywords),
        "process_keywords": keywords_to_text(vocab.process_keywords),
        "property_keywords": keywords_to_text(vocab.property_keywords),
        "structure_keywords": keywords_to_text(vocab.structure_keywords),
        "comparison_keywords": keywords_to_text(vocab.comparison_keywords),
        "table_keywords": keywords_to_text(vocab.table_keywords),
        "exclusion_keywords": keywords_to_text(vocab.exclusion_keywords),
        "user_notes": "",
      }
      st.rerun()

  form["material_keywords"] = st.text_area(
    "材料キーワード", value=form["material_keywords"], height=100, key=f"{key_prefix}_mat",
  )
  form["process_keywords"] = st.text_area(
    "工程キーワード", value=form["process_keywords"], height=100, key=f"{key_prefix}_proc",
  )
  form["property_keywords"] = st.text_area(
    "物性キーワード", value=form["property_keywords"], height=100, key=f"{key_prefix}_prop",
  )
  form["structure_keywords"] = st.text_area(
    "構造キーワード", value=form["structure_keywords"], height=80, key=f"{key_prefix}_struct",
  )
  form["comparison_keywords"] = st.text_area(
    "比較例キーワード", value=form["comparison_keywords"], height=80, key=f"{key_prefix}_cmp",
  )
  form["table_keywords"] = st.text_area(
    "表・テーブルキーワード", value=form["table_keywords"], height=60, key=f"{key_prefix}_tbl",
  )
  form["exclusion_keywords"] = st.text_area(
    "除外キーワード", value=form["exclusion_keywords"], height=60, key=f"{key_prefix}_excl",
  )
  form["user_notes"] = st.text_area(
    "補足メモ", value=form["user_notes"], height=60, key=f"{key_prefix}_notes",
  )

  vocabulary = _form_to_vocabulary(case_id, project_root, form)
  counts = vocabulary.keyword_counts()
  m1, m2, m3, m4, m5 = st.columns(5)
  m1.metric("material", counts["material"])
  m2.metric("process", counts["process"])
  m3.metric("property", counts["property"])
  m4.metric("comparison", counts["comparison"])
  m5.metric("exclusion", counts["exclusion"])

  if st.button("Save extraction vocabulary", key=f"{key_prefix}_save", type="primary"):
    path = save_extraction_vocabulary(case_id, project_root, vocabulary)
    st.success(f"保存しました — {path}")

  if saved.updated_at:
    st.caption(f"保存済み語彙: {saved.updated_at} ({saved.source})")

  return vocabulary
