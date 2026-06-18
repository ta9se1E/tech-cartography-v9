"""Reproducibility Smoke Run UI — load outputs and render Streamlit sections (Phase 22.1)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from tech_cartography.reports.project_export import load_records_csv
from tech_cartography.ui.easy_japanese_ui import (
  render_caution_box,
  render_dataframe_stretch,
  render_info_box,
  render_metric_cards,
  render_warning_box,
)

NOT_AVAILABLE = "not available"

REPRODUCIBILITY_RELATIVE_DIR = "outputs/reproducibility_smoke"

ARTIFACT_FILES: dict[str, str] = {
  "reproducibility_summary_csv": "reproducibility_summary.csv",
  "reproducibility_summary_json": "reproducibility_summary.json",
  "reproducibility_summary_md": "reproducibility_summary.md",
  "next_manual_claims_checklist_md": "next_manual_claims_checklist.md",
}

SUMMARY_DISPLAY_COLUMNS: tuple[str, ...] = (
  "publication_number",
  "title",
  "assignee",
  "country",
  "retrieval_route",
  "manual_input_exists",
  "query_plan_exists",
  "selected_evidence_papers_exists",
  "claim_paper_links_exists",
  "evidence_map_exists",
  "status",
  "confidence_limit",
  "next_action",
  "caveat",
)

EVIDENCE_MAP_READY_STATUSES: frozenset[str] = frozenset(
  {"complete_existing_demo", "evidence_map_ready"},
)
MANUAL_CLAIMS_REQUIRED_STATUSES: frozenset[str] = frozenset(
  {"blocked_missing_manual_claims", "manual_route_required"},
)

REPRODUCIBILITY_CAUTION = (
  "このSmoke Runは、FTO、侵害、有効性判断ではありません。"
  "論文候補は特許主張の証明ではなく supporting evidence candidate です。"
  "claims_only または Manual Claims Route の場合、confidenceは最大medium、基本はlow/weakです。"
  "架空情報は使いません。"
  'Synthetic demo signal を使う場合は必ず明記します。'
)

MANUAL_CHECKLIST_NOTICE = (
  "このチェックリストは自動スクレイピングを行うものではありません。"
  "Google Patents等をユーザーが確認し、claimsをmanual投入するための作業ガイドです。"
)

ONE_OFF_ANSWER_TITLE = "これは1件だけの偶然ですか？"
ONE_OFF_ANSWER_BODY = (
  "現時点でEvidence Mapまで完了しているのは US-12565719-B2 の1件です。"
  "ただし、Phase22では追加候補についても同じパイプラインに流し、どこで止まっているかを確認しています。"
  "今回の追加2件は manual claims 未投入のため停止しています。"
  "これは失敗ではなく、次に必要な手動アクションが明確になった状態です。"
)

MISSING_ARTIFACT_WARNING = (
  "Reproducibility Smoke Run の成果物が一部見つかりません。"
  "先に scripts/run_reproducibility_smoke.py を実行してください。"
)

STATUS_HELP_ITEMS: tuple[tuple[str, str], ...] = (
  (
    "complete_existing_demo",
    "既存のEvidence Mapデモ成果物が存在する状態",
  ),
  (
    "evidence_map_ready",
    "Evidence Map成果物が存在する状態",
  ),
  (
    "blocked_missing_manual_claims",
    "manual claimsが未投入のため次工程に進めない状態",
  ),
  (
    "manual_route_required",
    "BigQuery fulltextだけでは不十分でManual Claims Routeが必要な状態",
  ),
  (
    "query_plan_ready",
    "manual claimsからOpenAlex query planまで進める状態",
  ),
  (
    "error",
    "想定外エラー。ただし全体処理は継続",
  ),
)


@dataclass
class ReproducibilitySmokeArtifacts:
  status: str
  base_dir: Path
  summary_df: pd.DataFrame
  summary_json: dict[str, Any] | None
  summary_md: str | None
  manual_claims_checklist_md: str | None
  missing_artifacts: list[str] = field(default_factory=list)
  errors: list[str] = field(default_factory=list)


def safe_read_text(path: Path) -> tuple[str | None, str]:
  if not path.exists():
    return None, f"file not found: {path}"
  try:
    text = path.read_text(encoding="utf-8")
    if not text.strip():
      return None, f"empty file: {path}"
    return text, ""
  except OSError as exc:
    return None, f"read error ({path.name}): {exc}"


def safe_read_json(path: Path) -> tuple[dict[str, Any] | None, str]:
  text, err = safe_read_text(path)
  if err:
    return None, err
  if text is None:
    return None, f"empty file: {path}"
  try:
    parsed = json.loads(text)
    if isinstance(parsed, dict):
      return parsed, ""
    return None, f"json root is not object: {path.name}"
  except json.JSONDecodeError as exc:
    return None, f"json parse error ({path.name}): {exc}"


def safe_read_csv(path: Path) -> tuple[pd.DataFrame, str]:
  if not path.exists():
    return pd.DataFrame(), f"file not found: {path}"
  try:
    rows = load_records_csv(str(path))
    df = pd.DataFrame(rows) if rows else pd.DataFrame()
    return _normalize_dataframe(df), ""
  except Exception as exc:
    return pd.DataFrame(), f"csv read error ({path.name}): {exc}"


def _normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
  if df.empty:
    return df
  out = df.copy()
  for col in out.columns:
    out[col] = out[col].apply(_normalize_cell)
  return out


def _normalize_cell(value: Any) -> Any:
  if value is None:
    return ""
  if isinstance(value, float) and pd.isna(value):
    return ""
  if pd.isna(value):
    return ""
  return value


def _is_empty_value(value: Any) -> bool:
  if value is None:
    return True
  if isinstance(value, float) and pd.isna(value):
    return True
  if pd.isna(value):
    return True
  return str(value).strip() == ""


def _format_display_value(value: Any, *, default: str = NOT_AVAILABLE) -> str:
  if _is_empty_value(value):
    return default
  text = str(value).strip()
  if text.lower() in {"true", "false"}:
    return text.lower()
  return text


def _compute_loader_status(
  *,
  missing: list[str],
  errors: list[str],
  has_summary: bool,
) -> str:
  if errors and not has_summary:
    return "error"
  if not missing and not errors:
    return "ready"
  if len(missing) >= len(ARTIFACT_FILES):
    return "missing"
  if has_summary:
    return "partial"
  if errors:
    return "error"
  return "missing"


def load_reproducibility_smoke_artifacts(
  project_root: Path | str = ".",
) -> ReproducibilitySmokeArtifacts:
  base_dir = Path(project_root).resolve()
  smoke_dir = base_dir / REPRODUCIBILITY_RELATIVE_DIR
  missing: list[str] = []
  errors: list[str] = []

  csv_path = smoke_dir / ARTIFACT_FILES["reproducibility_summary_csv"]
  json_path = smoke_dir / ARTIFACT_FILES["reproducibility_summary_json"]
  md_path = smoke_dir / ARTIFACT_FILES["reproducibility_summary_md"]
  checklist_path = smoke_dir / ARTIFACT_FILES["next_manual_claims_checklist_md"]

  summary_df, csv_err = safe_read_csv(csv_path)
  if csv_err:
    if "not found" in csv_err:
      missing.append("reproducibility_summary_csv")
    else:
      errors.append(csv_err)

  summary_json, json_err = safe_read_json(json_path)
  if json_err:
    if "not found" in json_err:
      missing.append("reproducibility_summary_json")
    else:
      errors.append(json_err)

  summary_md, md_err = safe_read_text(md_path)
  if md_err:
    if "not found" in md_err:
      missing.append("reproducibility_summary_md")
    else:
      errors.append(md_err)

  checklist_md, checklist_err = safe_read_text(checklist_path)
  if checklist_err:
    if "not found" in checklist_err:
      missing.append("next_manual_claims_checklist_md")
    else:
      errors.append(checklist_err)

  has_summary = not summary_df.empty or bool(summary_json and summary_json.get("summary"))
  if summary_df.empty and summary_json and isinstance(summary_json.get("summary"), list):
    summary_df = pd.DataFrame(summary_json["summary"])

  status = _compute_loader_status(missing=missing, errors=errors, has_summary=has_summary)

  return ReproducibilitySmokeArtifacts(
    status=status,
    base_dir=base_dir,
    summary_df=_normalize_dataframe(summary_df),
    summary_json=summary_json,
    summary_md=summary_md,
    manual_claims_checklist_md=checklist_md,
    missing_artifacts=missing,
    errors=errors,
  )


def prepare_reproducibility_summary_display_df(df: pd.DataFrame | None) -> pd.DataFrame:
  if df is None or df.empty:
    return pd.DataFrame(columns=list(SUMMARY_DISPLAY_COLUMNS))

  rows: list[dict[str, str]] = []
  for _, row in df.iterrows():
    row_dict = {str(k): _normalize_cell(v) for k, v in row.to_dict().items()}
    display_row: dict[str, str] = {}
    for col in SUMMARY_DISPLAY_COLUMNS:
      if col in row_dict:
        display_row[col] = _format_display_value(row_dict[col])
      else:
        display_row[col] = NOT_AVAILABLE
    rows.append(display_row)
  return pd.DataFrame(rows, columns=list(SUMMARY_DISPLAY_COLUMNS))


def get_reproducibility_status_counts(df: pd.DataFrame | None) -> dict[str, int]:
  display_df = df if df is not None and not df.empty else pd.DataFrame()
  checked = len(display_df)
  evidence_map_ready = 0
  manual_claims_required = 0
  next_manual_actions = 0

  if not display_df.empty and "status" in display_df.columns:
    for status in display_df["status"].astype(str):
      normalized = status.strip()
      if normalized in EVIDENCE_MAP_READY_STATUSES:
        evidence_map_ready += 1
      if normalized in MANUAL_CLAIMS_REQUIRED_STATUSES:
        manual_claims_required += 1
        next_manual_actions += 1

  return {
    "checked_patents": checked,
    "evidence_map_ready": evidence_map_ready,
    "manual_claims_required": manual_claims_required,
    "next_manual_actions": next_manual_actions,
  }


def render_reproducibility_brief_card_html(counts: dict[str, int]) -> str:
  return (
    '<div class="tc-card-box">'
    "<strong>再現性確認の現在地</strong><ul>"
    f"<li>{counts.get('evidence_map_ready', 0)}件: Evidence Map ready</li>"
    f"<li>{counts.get('manual_claims_required', 0)}件: Manual Claims Route required</li>"
    "<li>次アクション: claimsをmanual投入してquery planへ進む</li>"
    "</ul></div>"
  )


def render_status_help_card_html() -> str:
  items = "".join(
    f"<li><code>{code}</code>: {desc}</li>" for code, desc in STATUS_HELP_ITEMS
  )
  return f'<div class="tc-info-box"><strong>status の意味</strong><ul>{items}</ul></div>'


def render_one_off_answer_card_html() -> str:
  return (
    f'<div class="tc-card-box">'
    f"<strong>{ONE_OFF_ANSWER_TITLE}</strong><br>{ONE_OFF_ANSWER_BODY}"
    f"</div>"
  )


def render_reproducibility_summary_cards(artifacts: ReproducibilitySmokeArtifacts) -> None:
  counts = get_reproducibility_status_counts(artifacts.summary_df)
  metrics = [
    {"label": "Checked Patents", "value": str(counts["checked_patents"])},
    {"label": "Evidence Map Ready", "value": str(counts["evidence_map_ready"])},
    {"label": "Manual Claims Required", "value": str(counts["manual_claims_required"])},
    {"label": "Next Manual Actions", "value": str(counts["next_manual_actions"])},
  ]
  st.markdown(render_metric_cards(metrics), unsafe_allow_html=True)


def render_reproducibility_summary_table(artifacts: ReproducibilitySmokeArtifacts) -> None:
  display_df = prepare_reproducibility_summary_display_df(artifacts.summary_df)
  if display_df.empty:
    st.warning("Reproducibility summary CSV が空です。smoke run を再実行してください。")
    return
  render_dataframe_stretch(display_df, hide_index=True)


def render_manual_claims_checklist(artifacts: ReproducibilitySmokeArtifacts) -> None:
  st.markdown(render_info_box(MANUAL_CHECKLIST_NOTICE), unsafe_allow_html=True)
  if artifacts.manual_claims_checklist_md:
    st.markdown(artifacts.manual_claims_checklist_md)
  else:
    st.info("next_manual_claims_checklist.md は not available です。")


def render_reproducibility_report(artifacts: ReproducibilitySmokeArtifacts) -> None:
  if artifacts.summary_md:
    st.markdown(artifacts.summary_md)
  else:
    st.info("reproducibility_summary.md は not available です。")


def render_reproducibility_brief_section(artifacts: ReproducibilitySmokeArtifacts) -> None:
  if artifacts.status == "missing":
    st.markdown(render_warning_box(MISSING_ARTIFACT_WARNING), unsafe_allow_html=True)
    return
  counts = get_reproducibility_status_counts(artifacts.summary_df)
  st.markdown(render_reproducibility_brief_card_html(counts), unsafe_allow_html=True)


def render_reproducibility_smoke_section(artifacts: ReproducibilitySmokeArtifacts) -> None:
  st.subheader("Reproducibility Smoke Run")
  st.markdown(render_caution_box(REPRODUCIBILITY_CAUTION), unsafe_allow_html=True)

  if artifacts.missing_artifacts:
    st.markdown(
      render_warning_box(
        f"{MISSING_ARTIFACT_WARNING}<br>missing: {', '.join(artifacts.missing_artifacts)}"
      ),
      unsafe_allow_html=True,
    )
  if artifacts.errors:
    with st.expander("読み込みエラー（デバッグ）"):
      for err in artifacts.errors:
        st.caption(err)

  if artifacts.status == "missing" and artifacts.summary_df.empty:
    return

  render_reproducibility_summary_cards(artifacts)
  st.markdown(render_one_off_answer_card_html(), unsafe_allow_html=True)
  st.markdown(render_status_help_card_html(), unsafe_allow_html=True)

  st.subheader("Reproducibility Summary Table")
  render_reproducibility_summary_table(artifacts)

  with st.expander("Next Manual Claims Checklist", expanded=False):
    render_manual_claims_checklist(artifacts)

  with st.expander("Phase22 Reproducibility Smoke Run Report", expanded=False):
    render_reproducibility_report(artifacts)
