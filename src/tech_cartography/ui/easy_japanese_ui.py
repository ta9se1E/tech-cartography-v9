"""Easy Japanese UI components for Tech Cartography v7."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from tech_cartography.ui.japanese_labels import (
  explain_evidence_validation_mode,
  explain_evidence_validation_readiness,
  explain_fulltext_priority_top5,
  explain_fulltext_retrieval_status,
  explain_stage_status,
  explain_strategic_watch,
  translate_cluster_id,
  translate_evidence_coverage_level,
  translate_fulltext_retrieval_status,
  translate_recommended_next_action,
  translate_source_route,
  translate_stage_id,
  translate_stage_status,
)

EASY_UI_CSS = """
<style>
.tc-easy-title { font-size: 2rem; font-weight: 700; margin-bottom: 0.25rem; }
.tc-easy-subtitle { color: #4b5563; margin-bottom: 1rem; }
.tc-info-box {
  background: #eff6ff; border-left: 5px solid #2563eb;
  padding: 1rem 1.1rem; border-radius: 8px; margin: 0.8rem 0;
}
.tc-warning-box {
  background: #fff7ed; border-left: 5px solid #ea580c;
  padding: 1rem 1.1rem; border-radius: 8px; margin: 0.8rem 0;
}
.tc-success-box {
  background: #ecfdf5; border-left: 5px solid #059669;
  padding: 1rem 1.1rem; border-radius: 8px; margin: 0.8rem 0;
}
.tc-step-header {
  background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px;
  padding: 1rem 1.2rem; margin: 1rem 0 0.6rem 0;
}
.tc-step-no { color: #2563eb; font-weight: 700; font-size: 0.95rem; }
.tc-step-title { font-size: 1.35rem; font-weight: 700; margin: 0.15rem 0; }
.tc-step-subtitle { color: #64748b; font-size: 0.95rem; }
.tc-metric-card {
  background: white; border: 1px solid #e2e8f0; border-radius: 10px;
  padding: 0.9rem 1rem; min-height: 88px;
}
.tc-metric-label { color: #64748b; font-size: 0.85rem; }
.tc-metric-value { font-size: 1.5rem; font-weight: 700; margin-top: 0.2rem; }
.tc-patent-card {
  background: white; border: 1px solid #dbe3ef; border-radius: 12px;
  padding: 1rem 1.1rem; margin: 0.7rem 0;
}
.tc-patent-title { font-size: 1.05rem; font-weight: 700; margin-bottom: 0.35rem; }
.tc-patent-meta { color: #475569; font-size: 0.92rem; line-height: 1.5; }
.tc-caveat-footer {
  background: #fafafa; border-top: 1px solid #e5e7eb;
  padding: 1rem 0.2rem; color: #6b7280; font-size: 0.9rem;
}
</style>
"""


def inject_easy_ui_css() -> str:
  return EASY_UI_CSS


def render_info_box(text: str) -> str:
  return f'<div class="tc-info-box">{text}</div>'


def render_warning_box(text: str) -> str:
  return f'<div class="tc-warning-box">{text}</div>'


def render_success_box(text: str) -> str:
  return f'<div class="tc-success-box">{text}</div>'


def render_step_header(step_no: int, title: str, subtitle: str) -> str:
  return (
    f'<div class="tc-step-header">'
    f'<div class="tc-step-no">ステップ {step_no}</div>'
    f'<div class="tc-step-title">{title}</div>'
    f'<div class="tc-step-subtitle">{subtitle}</div>'
    f"</div>"
  )


def render_metric_cards(metrics: list[dict[str, Any]]) -> str:
  cards = []
  for metric in metrics:
    label = str(metric.get("label", ""))
    value = str(metric.get("value", ""))
    cards.append(
      f'<div class="tc-metric-card">'
      f'<div class="tc-metric-label">{label}</div>'
      f'<div class="tc-metric-value">{value}</div>'
      f"</div>",
    )
  return '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;">' + "".join(cards) + "</div>"


def _safe(value: Any, default: str = "—") -> str:
  if value is None:
    return default
  text = str(value).strip()
  if not text or text.lower() in {"nan", "none", "null"}:
    return default
  return text


def render_patent_card(row: dict[str, Any]) -> str:
  title = _safe(row.get("title") or row.get("発明の名称"), "（タイトル不明）")
  pub = _safe(row.get("publication_number") or row.get("公開番号"))
  assignee = _safe(row.get("assignee") or row.get("出願人"), "出願人不明")
  cluster = _safe(
    row.get("primary_cluster_japanese")
    or translate_cluster_id(str(row.get("primary_cluster_id", ""))),
  )
  score = _safe(row.get("final_score") or row.get("total_score") or row.get("優先度スコア"))
  noise = _safe(row.get("noise_score") or row.get("ノイズ度"), "0")
  attention = _safe(row.get("attention_flag") or row.get("注意表示"), "")
  attention_html = (
    f'<div style="color:#ea580c;font-weight:600;">⚠ 注意: ノイズ候補の可能性があります（ノイズ度 {noise}）</div>'
    if attention == "注意" or float(noise or 0) >= 0.45
    else ""
  )
  return (
    f'<div class="tc-patent-card">'
    f'<div class="tc-patent-title">{title}</div>'
    f'<div class="tc-patent-meta">'
    f"公開番号: {pub}<br>"
    f"出願人: {assignee}<br>"
    f"技術分類: {cluster}<br>"
    f"優先度スコア: {score} / ノイズ度: {noise}"
    f"</div>{attention_html}</div>"
  )


def render_top5_fulltext_card(row: dict[str, Any]) -> str:
  title = _safe(row.get("title") or row.get("発明の名称"), "（タイトル不明）")
  pub = _safe(row.get("publication_number") or row.get("公開番号"))
  route = _safe(
    row.get("source_route_japanese")
    or translate_source_route(str(row.get("source_route", ""))),
  )
  why = _safe(row.get("why_selected_japanese") or row.get("選ばれた理由"), "選定理由は追加確認が必要です。")
  return (
    f'<div class="tc-patent-card">'
    f'<div class="tc-patent-title">{title}</div>'
    f'<div class="tc-patent-meta">'
    f"公開番号: {pub}<br>"
    f"全文確認ルート: {route}<br>"
    f"選ばれた理由: {why}"
    f"</div></div>"
  )


def render_strategic_watch_card(row: dict[str, Any]) -> str:
  title = _safe(row.get("title") or row.get("発明の名称"), "（タイトル不明）")
  pub = _safe(row.get("publication_number") or row.get("公開番号"))
  assignee = _safe(row.get("assignee") or row.get("出願人"), "出願人不明")
  country = _safe(row.get("country") or row.get("国"))
  watch_reason = _safe(row.get("watch_reason_japanese") or row.get("監視理由"), "戦略監視候補")
  manual = _safe(row.get("manual_route_reason") or row.get("手動確認理由"), "")
  action = _safe(
    row.get("recommended_next_action_japanese")
    or translate_recommended_next_action(str(row.get("recommended_next_action", ""))),
  )
  manual_html = f"<br>手動確認: {manual}" if manual else ""
  return (
    f'<div class="tc-patent-card">'
    f'<div class="tc-patent-title">{title}</div>'
    f'<div class="tc-patent-meta">'
    f"公開番号: {pub} / 国: {country}<br>"
    f"出願人: {assignee}<br>"
    f"監視理由: {watch_reason}{manual_html}<br>"
    f"次の確認: {action}"
    f"</div></div>"
  )


def render_fulltext_status_card(row: dict[str, Any]) -> str:
  title = _safe(row.get("title"), "（タイトル不明）")
  pub = _safe(row.get("publication_number"))
  status = _safe(row.get("retrieval_status"), "unknown")
  status_ja = translate_fulltext_retrieval_status(status)
  status_explain = explain_fulltext_retrieval_status(status)
  evidence = translate_evidence_coverage_level(str(row.get("evidence_level", "")))
  return (
    f'<div class="tc-patent-card">'
    f'<div class="tc-patent-title">{title}</div>'
    f'<div class="tc-patent-meta">'
    f"公開番号: {pub}<br>"
    f"全文取得状態: {status_ja}<br>"
    f"説明: {status_explain}<br>"
    f"根拠レベル: {evidence}"
    f"</div></div>"
  )


def render_manual_checklist_notice() -> str:
  return render_info_box(
    "全文が取れない場合でも、戦略監視候補として重要な場合があります。"
    "中国候補を除外しているわけではありません。"
  )


def render_fulltext_vs_watch_notice() -> str:
  return render_info_box(
    "米国公報は全文取得を試せます。"
    "中国・欧州・日本の重要特許は、PDFやGoogle Patentsで手動確認する候補として別枠で残します。"
    "中国候補を除外しているわけではありません。"
    f"<br><br>{explain_fulltext_priority_top5()}"
    f"<br><br>{explain_strategic_watch()}"
  )


def render_evidence_validation_summary(summary: dict[str, Any] | None) -> str:
  if not summary:
    return render_warning_box("Evidence Validation の結果がまだありません。")

  s = summary.get("summary") if isinstance(summary.get("summary"), dict) else summary
  openalex_mode = str(s.get("openalex_mode") or summary.get("openalex_mode") or "plan_only")
  metrics = [
    {"label": "全文レコード", "value": s.get("fulltext_records", 0)},
    {"label": "請求項分解可能", "value": s.get("ready_for_claim_extraction", 0)},
    {"label": "dry-runのみ", "value": s.get("dry_run_only", 0)},
    {"label": "手動確認", "value": s.get("manual_required", 0)},
    {"label": "Claim Element", "value": s.get("generated_claim_elements", 0)},
    {"label": "論文クエリ候補", "value": s.get("generated_paper_queries", 0)},
  ]
  next_actions = summary.get("recommended_actions") or []
  action_html = "".join(f"<li>{_safe(action)}</li>" for action in next_actions[:5])
  return (
    f"{render_info_box(explain_evidence_validation_readiness())}"
    f"{render_metric_cards(metrics)}"
    f'<div class="tc-patent-card">'
    f'<div class="tc-patent-title">OpenAlex: {openalex_mode}</div>'
    f'<div class="tc-patent-meta">{explain_evidence_validation_mode(openalex_mode)}</div>'
    f"</div>"
    f'<div class="tc-patent-card"><div class="tc-patent-title">次にやるべきこと</div>'
    f"<ul>{action_html or '<li>全文取得または手動確認リストを確認してください。</li>'}</ul></div>"
  )


def render_caveat_footer() -> str:
  lines = [
    "本ツールは特許の有効性・侵害・FTOを判断しません。",
    "論文やWeb情報は裏取り候補であり、証明ではありません。",
    "最終判断には専門家レビューと実験確認が必要です。",
  ]
  body = "<br>".join(f"• {line}" for line in lines)
  return f'<div class="tc-caveat-footer">{body}</div>'


DISPLAY_COLUMN_MAP = {
  "publication_number": "公開番号",
  "title": "発明の名称",
  "assignee": "出願人",
  "country": "国",
  "primary_cluster_id": "技術分類ID",
  "primary_cluster_japanese": "技術分類",
  "final_score": "優先度スコア",
  "total_score": "優先度スコア",
  "noise_score": "ノイズ度",
  "source_route": "全文確認ルートID",
  "source_route_japanese": "全文確認ルート",
  "why_selected_japanese": "選ばれた理由",
  "attention_flag": "注意表示",
  "rank": "順位",
  "fulltext_candidate_rank": "全文候補順位",
  "strategic_watch_rank": "戦略監視順位",
  "strategic_watch_score": "戦略監視スコア",
  "watch_reason_japanese": "監視理由",
  "manual_route_reason": "手動確認理由",
  "recommended_next_action_japanese": "次の確認",
  "caveat_japanese": "注意書き",
}


def prepare_patent_display_df(df: pd.DataFrame) -> pd.DataFrame:
  if df is None or df.empty:
    return pd.DataFrame()
  display = df.copy()
  if "primary_cluster_id" in display.columns and "primary_cluster_japanese" not in display.columns:
    display["primary_cluster_japanese"] = display["primary_cluster_id"].map(
      lambda value: translate_cluster_id(str(value)),
    )
  if "source_route" in display.columns and "source_route_japanese" not in display.columns:
    display["source_route_japanese"] = display["source_route"].map(
      lambda value: translate_source_route(str(value)),
    )
  if "final_score" not in display.columns and "total_score" in display.columns:
    display["final_score"] = display["total_score"]
  if "noise_score" in display.columns and "attention_flag" not in display.columns:
    display["attention_flag"] = display["noise_score"].map(
      lambda value: "注意" if float(value or 0) >= 0.45 else "",
    )
  rename_map = {key: value for key, value in DISPLAY_COLUMN_MAP.items() if key in display.columns}
  return display.rename(columns=rename_map)


def summarize_stage_statuses(manifest: dict[str, Any] | None) -> list[dict[str, str]]:
  if not manifest:
    return []
  rows: list[dict[str, str]] = []
  for stage in manifest.get("stage_results", []):
    if not isinstance(stage, dict):
      continue
    status = str(stage.get("status", "pending"))
    rows.append(
      {
        "段階": translate_stage_id(str(stage.get("stage_id", ""))),
        "状態": translate_stage_status(status),
        "説明": explain_stage_status(status),
        "stage_id": str(stage.get("stage_id", "")),
        "status": status,
      },
    )
  return rows


def serialize_list_field(value: Any) -> str:
  if value is None:
    return ""
  if isinstance(value, list):
    return "; ".join(str(item) for item in value)
  if isinstance(value, str) and value.startswith("["):
    try:
      parsed = json.loads(value)
      if isinstance(parsed, list):
        return "; ".join(str(item) for item in parsed)
    except json.JSONDecodeError:
      pass
  return str(value)
