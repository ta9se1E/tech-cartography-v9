"""v8 user-flow tab configuration (Phase 27B)."""

from __future__ import annotations

V8_TAB_IDS: tuple[str, ...] = (
  "intro",
  "input",
  "sources",
  "patent_shortlist",
  "claim_map",
  "evidence_map",
  "gap_next_actions",
  "fixed_point_observation",
  "export",
  "admin_settings",
)

V8_TAB_LABELS: dict[str, str] = {
  "intro": "はじめに",
  "input": "入力",
  "sources": "Sources一覧",
  "patent_shortlist": "読むべき特許",
  "claim_map": "Claim Map",
  "evidence_map": "Evidence Map",
  "gap_next_actions": "Gap / Next Actions",
  "fixed_point_observation": "定点観測",
  "export": "Export",
  "admin_settings": "管理者設定",
}

V8_CASE_SAMPLES: tuple[dict[str, str], ...] = (
  {
    "case_id": "case_01_pan_graphitization",
    "label": "Case 1: PAN系炭素繊維の前駆体・炭化・黒鉛化",
  },
  {
    "case_id": "case_02_sizing_interface",
    "label": "Case 2: サイジング・表面処理・界面・複合材料",
  },
  {
    "case_id": "case_03_pressure_vessel_filament_winding",
    "label": "Case 3: CFRP圧力容器・フィラメントワインディング・水素タンク",
  },
)

CLAIM_MAP_TECHNICAL_AXES: tuple[str, ...] = (
  "precursor",
  "sizing / surface treatment",
  "stabilization",
  "carbonization",
  "graphitization",
  "matrix / resin",
  "mechanical property",
  "microstructure",
  "application",
  "pressure vessel / filament winding",
)

CLAIM_MAP_PLANNED_COLUMNS: tuple[str, ...] = (
  "patent_id",
  "claim_no",
  "claim_text",
  "technical_axis",
  "mentioned_material",
  "mentioned_process",
  "mentioned_property",
  "evidence_needed",
)

EVIDENCE_MAP_PLANNED_COLUMNS: tuple[str, ...] = (
  "claim",
  "technical_axis",
  "example_support",
  "paper_support",
  "web_support",
  "support_level",
  "gap",
  "next_action",
)

EVIDENCE_SUPPORT_LEVELS: tuple[str, ...] = (
  "strong_example_support",
  "paper_supported_candidate",
  "web_only_candidate",
  "no_direct_evidence",
  "needs_human_review",
)

STATE_V8_INPUT = "v8_input_state"
STATE_V8_SELECTED_CASE = "v8_selected_case_id"
STATE_V8_SELECTED_PUBLICATION = "v8_selected_publication_number"

V8_STATUS_CAPTION = (
  "v8 submission demo — Phase27Q.3: Case 1 full Top5 manual claims / Evidence Gap（提出時 BQ・メール・Scheduler OFF）"
)

V8_SIDEBAR_PROGRESS_LINES: tuple[str, ...] = (
  "1. 入力",
  "2. Sources一覧",
  "3. 読むべき特許",
  "4. Claim Map",
  "5. Evidence Map",
  "6. Gap / Next Actions",
  "7. 定点観測",
  "8. Export",
)

V8_SIDEBAR_NEXT_STEP = (
  "Case 1 は1000件候補→Top5選抜→Top5全件35請求項投入済み。次はEvidence Gapと実施例確認。"
)

V8_SIDEBAR_SUBMISSION_SAFE_NOTICE = (
  "提出デモ: 外部API実行なし / BigQuery実行なし / メール送信なし / Scheduler起動なし / 管理者設定デフォルトOFF"
)

CASE_01_TOP5_PUBLICATIONS = (
  "CN108286090A, CN117987966A, CN105401262A, CN105506785B, CN109402791B"
)


def v8_sidebar_progress_text() -> str:
  return "\n".join(V8_SIDEBAR_PROGRESS_LINES)


def v8_sidebar_next_steps_text() -> str:
  return V8_SIDEBAR_NEXT_STEP


def v8_tab_labels() -> list[str]:
  return [V8_TAB_LABELS[tab_id] for tab_id in V8_TAB_IDS]


def v8_tab_label(tab_id: str) -> str:
  return V8_TAB_LABELS.get(tab_id, tab_id)
