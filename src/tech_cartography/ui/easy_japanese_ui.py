"""Easy Japanese UI components for Tech Cartography v7."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from tech_cartography.ui.japanese_labels import (
  explain_cost_guard_status,
  explain_evidence_validation_mode,
  explain_evidence_validation_readiness,
  explain_expensive_fulltext_approval,
  explain_fulltext_execute_trial,
  explain_fulltext_priority_top5,
  explain_fulltext_retrieval_status,
  explain_fulltext_scope,
  explain_stage_status,
  explain_strategic_watch,
  translate_cluster_id,
  translate_evidence_coverage_level,
  translate_fulltext_retrieval_status,
  translate_fulltext_scope,
  translate_recommended_next_action,
  translate_source_route,
  translate_stage_id,
  translate_stage_status,
  translate_tab_name,
)

EVIDENCE_MAP_INTRO_JAPANESE = (
  "このEvidence Mapは、請求項と論文候補の対応を整理したものです。"
  "論文候補は技術背景の裏取り候補であり、特許主張を証明するものではありません。"
)

WEAK_LINK_EXPLANATION_JAPANESE = (
  "これは請求項と論文候補の弱い対応です。"
  "技術背景を確認するための候補であり、特許主張を証明するものではありません。"
)

DEMO_DEEP_DIVE_PUBLICATION = "US-12565719-B2"
DEMO_DEEP_DIVE_TITLE = "Carbon fiber and method of manufacturing same"

DEMO_ARTIFACT_SPECS: tuple[tuple[str, str, str], ...] = (
  (
    "evidence_map_synthesis_md",
    "Evidence Map Synthesis Report",
    "outputs/evidence_map_synthesis/US-12565719-B2/evidence_map_synthesis.md",
  ),
  (
    "evidence_map_items_csv",
    "Evidence Map Items",
    "outputs/evidence_map_synthesis/US-12565719-B2/evidence_map_items.csv",
  ),
  (
    "selected_evidence_papers_csv",
    "Selected Evidence Papers",
    "outputs/openalex_limited_execution/selected_evidence_papers.csv",
  ),
  (
    "claim_paper_candidate_links_csv",
    "Claim × Paper Candidate Links",
    "outputs/openalex_limited_execution/claim_paper_candidate_links.csv",
  ),
  (
    "paper_candidate_relevance_report_md",
    "Paper Candidate Relevance Report",
    "outputs/openalex_limited_execution/paper_candidate_relevance_report.md",
  ),
)

V7_EASY_CSS = """
<style>
.tc-main-title { font-size: 2.2rem; font-weight: 700; margin-bottom: 0.35rem; color: var(--tc-text, #0f172a); }
.tc-main-subtitle { font-size: 1.15rem; color: var(--tc-muted, #475569); line-height: 1.7; margin-bottom: 1rem; }
.tc-card-box {
  background: var(--tc-card-bg, #f8fafc); color: var(--tc-text, #0f172a);
  border: 1px solid var(--tc-border, #dbeafe); border-radius: 12px;
  padding: 1.2rem 1.4rem; margin: 0.8rem 0; font-size: 1.02rem; line-height: 1.65;
}
.tc-ok-box {
  background: var(--tc-success-bg, #ecfdf5); color: var(--tc-success-text, #064e3b);
  border: 1px solid var(--tc-success-border, #6ee7b7); border-radius: 12px;
  padding: 1rem 1.2rem; margin: 1rem 0; font-size: 1.05rem;
}
.tc-caution-box {
  background: var(--tc-warn-bg, #fff7ed); color: var(--tc-warn-text, #431407);
  border: 1px solid var(--tc-warn-border, #fdba74); border-radius: 12px;
  padding: 1rem 1.2rem; margin: 1rem 0; font-size: 1.05rem;
}
.tc-user-badge {
  display: inline-block; background: var(--tc-info-bg, #eff6ff); color: var(--tc-text, #0f172a);
  border: 1px solid var(--tc-info-border, #93c5fd); border-radius: 999px;
  padding: 0.35rem 0.9rem; font-size: 0.92rem; margin: 0.25rem 0.4rem 0.25rem 0;
}
div.stButton > button { min-height: 2.75rem; font-size: 1.02rem; padding: 0.55rem 1.1rem; }
</style>
"""

EASY_UI_CSS = """
<style>
.tc-easy-title { font-size: 2rem; font-weight: 700; margin-bottom: 0.25rem; color: var(--tc-text, #0f172a); }
.tc-easy-subtitle { color: var(--tc-muted, #475569); margin-bottom: 1rem; }
.tc-info-box {
  background: var(--tc-info-bg, #dbeafe); color: var(--tc-info-text, #0f172a);
  border-left: 5px solid var(--tc-info-border, #2563eb);
  padding: 1rem 1.1rem; border-radius: 8px; margin: 0.8rem 0;
}
.tc-warning-box {
  background: var(--tc-warn-bg, #ffedd5); color: var(--tc-warn-text, #431407);
  border-left: 5px solid var(--tc-warn-border, #ea580c);
  padding: 1rem 1.1rem; border-radius: 8px; margin: 0.8rem 0;
}
.tc-success-box {
  background: var(--tc-success-bg, #d1fae5); color: var(--tc-success-text, #064e3b);
  border-left: 5px solid var(--tc-success-border, #059669);
  padding: 1rem 1.1rem; border-radius: 8px; margin: 0.8rem 0;
}
.tc-step-header {
  background: var(--tc-step-bg, #f1f5f9); color: var(--tc-text, #0f172a);
  border: 1px solid var(--tc-border, #cbd5e1); border-radius: 12px;
  padding: 1rem 1.2rem; margin: 1rem 0 0.6rem 0;
}
.tc-step-no { color: var(--tc-accent, #2563eb); font-weight: 700; font-size: 0.95rem; }
.tc-step-title { font-size: 1.35rem; font-weight: 700; margin: 0.15rem 0; color: var(--tc-text, #0f172a); }
.tc-step-subtitle { color: var(--tc-muted, #64748b); font-size: 0.95rem; }
.tc-metric-card {
  background: var(--tc-card-bg, #ffffff); color: var(--tc-text, #0f172a);
  border: 1px solid var(--tc-border, #cbd5e1); border-radius: 10px;
  padding: 0.9rem 1rem; min-height: 88px;
}
.tc-metric-label { color: var(--tc-muted, #64748b); font-size: 0.85rem; }
.tc-metric-value { font-size: 1.5rem; font-weight: 700; margin-top: 0.2rem; color: var(--tc-text, #0f172a); }
.tc-patent-card {
  background: var(--tc-card-bg, #ffffff); color: var(--tc-text, #0f172a);
  border: 1px solid var(--tc-border, #cbd5e1); border-radius: 12px;
  padding: 1rem 1.1rem; margin: 0.7rem 0;
}
.tc-patent-title { font-size: 1.05rem; font-weight: 700; margin-bottom: 0.35rem; color: var(--tc-text, #0f172a); }
.tc-patent-meta { color: var(--tc-muted, #475569); font-size: 0.92rem; line-height: 1.5; }
.tc-caveat-footer {
  background: var(--tc-footer-bg, #f8fafc); color: var(--tc-muted, #64748b);
  border-top: 1px solid var(--tc-border, #e2e8f0);
  padding: 1rem 0.2rem; font-size: 0.9rem;
}
[data-theme="dark"] .tc-easy-title,
[data-theme="dark"] .tc-step-title,
[data-theme="dark"] .tc-metric-value,
[data-theme="dark"] .tc-patent-title,
[data-theme="dark"] .tc-patent-card,
[data-theme="dark"] .tc-metric-card,
[data-theme="dark"] .tc-step-header {
  --tc-text: #f1f5f9;
  --tc-muted: #cbd5e1;
  --tc-card-bg: #1e293b;
  --tc-step-bg: #1e293b;
  --tc-border: #475569;
  --tc-footer-bg: #0f172a;
}
[data-theme="dark"] .tc-info-box {
  --tc-info-bg: #1e3a5f; --tc-info-text: #e2e8f0; --tc-info-border: #60a5fa;
}
[data-theme="dark"] .tc-warning-box {
  --tc-warn-bg: #431407; --tc-warn-text: #ffedd5; --tc-warn-border: #fb923c;
}
[data-theme="dark"] .tc-success-box {
  --tc-success-bg: #064e3b; --tc-success-text: #d1fae5; --tc-success-border: #34d399;
}
@media (prefers-color-scheme: dark) {
  [data-theme="dark"] .tc-easy-subtitle { color: #cbd5e1; }
}
</style>
"""


def inject_easy_ui_css() -> str:
  return V7_EASY_CSS + EASY_UI_CSS


def render_main_title(title: str, subtitle: str) -> str:
  return (
    f'<div class="tc-main-title">{title}</div>'
    f'<div class="tc-main-subtitle">{subtitle}</div>'
  )


def render_login_notice() -> str:
  return (
    '<div class="tc-card-box">'
    "<b>メールアドレスでログイン</b><br>"
    "将来、週次レポートやWatch Profileをこのメールアドレスに紐づけます。<br>"
    "現在はローカル開発用の簡易ログインです。パスワード認証やメール送信はまだ行いません。"
    "</div>"
  )


def render_user_badge(user: dict[str, Any]) -> str:
  name = _safe(user.get("display_name") or user.get("email"), "ユーザー")
  company = _safe(user.get("company_name"), "")
  company_html = f" / {company}" if company and company != "—" else ""
  return f'<span class="tc-user-badge">{name}{company_html}</span>'


def render_watch_profile_card(profile: dict[str, Any]) -> str:
  theme = _safe(profile.get("theme"), "（テーマ未設定）")
  keywords = ", ".join(profile.get("keywords") or [])[:200]
  companies = ", ".join(profile.get("companies") or [])[:200]
  countries = ", ".join(profile.get("countries") or [])
  return (
    f'<div class="tc-card-box">'
    f"<b>Watch Profile</b><br>"
    f"テーマ: {theme}<br>"
    f"キーワード: {keywords or '—'}<br>"
    f"注目企業: {companies or '—'}<br>"
    f"対象国: {countries or '—'}"
    f"</div>"
  )


def render_status_card(title: str, value: str, description: str = "") -> str:
  desc_html = f"<br><span style='font-size:0.92rem;color:#64748b;'>{description}</span>" if description else ""
  return (
    f'<div class="tc-metric-card">'
    f'<div class="tc-metric-label">{title}</div>'
    f'<div class="tc-metric-value">{value}</div>{desc_html}'
    f"</div>"
  )


def render_caution_box(text: str) -> str:
  return f'<div class="tc-caution-box">{text}</div>'


def render_ok_box(text: str) -> str:
  return f'<div class="tc-ok-box">{text}</div>'


def render_next_action_box(actions: list[str]) -> str:
  items = "".join(f"<li>{_safe(action)}</li>" for action in actions if action)
  return f'<div class="tc-card-box"><b>次にやること</b><ul>{items or "<li>実行結果を読み込んでください。</li>"}</ul></div>'


def _coerce_mapping(value: Any) -> dict[str, Any]:
  if isinstance(value, dict):
    return value
  if value is None:
    return {}
  if isinstance(value, str):
    text = value.strip()
    if not text:
      return {}
    try:
      parsed = json.loads(text)
      if isinstance(parsed, dict):
        return parsed
      return {"raw_value": value}
    except Exception:
      return {"raw_value": value}
  return {"raw_value": value}


def normalize_dataframe_row(row: Any) -> dict[str, Any]:
  if not isinstance(row, dict):
    return _coerce_mapping(row)
  out: dict[str, Any] = {}
  for key, value in row.items():
    if pd.isna(value):
      out[str(key)] = ""
    else:
      out[str(key)] = value
  return out


def _render_dataframe_stretch(df: pd.DataFrame, **kwargs: Any) -> None:
  import streamlit as st

  try:
    st.dataframe(df, width="stretch", **kwargs)
  except TypeError:
    st.dataframe(df, use_container_width=True, **kwargs)


def render_dataframe_stretch(df: pd.DataFrame, **kwargs: Any) -> None:
  """Public wrapper for stretch-width dataframe display."""
  _render_dataframe_stretch(df, **kwargs)


def render_small_table(df: pd.DataFrame, height: int = 320) -> None:
  import streamlit as st

  if df is None or df.empty:
    st.info("表示するデータがありません。")
    return
  _render_dataframe_stretch(df, hide_index=True, height=height)


def render_markdown_preview(md: str, max_chars: int = 4000) -> str:
  text = str(md or "")
  if len(text) > max_chars:
    return text[:max_chars] + "\n\n…（以下省略）"
  return text


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


def render_fulltext_execute_summary(preview: dict[str, Any] | None, summary: dict[str, Any] | None = None) -> str:
  preview = preview or {}
  summary = summary or {}
  metrics = [
    {"label": "全文実行対象", "value": preview.get("selected_for_execute_count", summary.get("execute_selected_count", 0))},
    {"label": "取得できた件数", "value": summary.get("retrieved_count", 0)},
    {"label": "キャッシュ利用", "value": summary.get("cache_hit_count", summary.get("cache_hits", 0))},
    {"label": "実行対象外", "value": summary.get("skipped_not_selected_count", preview.get("skipped_not_selected_count", 0))},
    {"label": "コストガード停止", "value": summary.get("cost_guard_failed_count", summary.get("blocked_by_cost_guard", 0))},
    {"label": "手動確認（中国等）", "value": preview.get("manual_required_count", summary.get("manual_required_count", 0))},
  ]
  mode = preview.get("estimated_mode") or summary.get("mode") or "dry_run"
  confirm = preview.get("confirmation_required", False)
  scope = preview.get("fulltext_scope") or summary.get("fulltext_scope") or "claims_only"
  expensive_cmd = preview.get("recommended_expensive_command", "")
  confirm_note = "確認フラグが必要です（--confirm-fulltext-execute）" if confirm else "計画/プレビューまたは確認済みです"
  expensive_note = ""
  if preview.get("cost_guard_requires_expensive_confirmation") or summary.get("cost_guard_requires_expensive_count", 0) > 0:
    expensive_note = (
      f"<br><br>{explain_expensive_fulltext_approval()}"
      f"<br>推奨コマンド: <code>{_safe(expensive_cmd)}</code>" if expensive_cmd else ""
    )
  return (
    f"{render_info_box(explain_fulltext_execute_trial())}"
    f"{render_info_box(explain_fulltext_scope(scope))}"
    f"{render_metric_cards(metrics)}"
    f'<div class="tc-patent-card"><div class="tc-patent-title">実行モード: {mode}</div>'
    f'<div class="tc-patent-meta">{confirm_note}<br>'
    f"スコープ: {scope}<br>"
    f"まず1件だけ全文取得を試すのが安全です。中国候補は別枠で手動確認リストに残しています。"
    f"{expensive_note}"
    f"</div></div>"
  )


def render_evidence_validation_summary(summary: dict[str, Any] | None) -> str:
  if not summary:
    return render_warning_box("Evidence Validation の結果がまだありません。")

  s = summary.get("summary") if isinstance(summary.get("summary"), dict) else summary
  openalex_mode = str(s.get("openalex_mode") or summary.get("openalex_mode") or "plan_only")
  openalex_limited = summary.get("openalex_limited_execution") if isinstance(summary, dict) else {}
  metrics = [
    {"label": "全文レコード", "value": s.get("fulltext_records", 0)},
    {"label": "請求項分解可能", "value": s.get("ready_for_claim_extraction", 0)},
    {"label": "dry-runのみ", "value": s.get("dry_run_only", 0)},
    {"label": "手動確認", "value": s.get("manual_required", 0)},
    {"label": "Claim Element", "value": s.get("generated_claim_elements", 0)},
    {"label": "論文クエリ候補", "value": s.get("generated_paper_queries", 0)},
    {"label": "OpenAlex paper", "value": s.get("openalex_paper_records", 0)},
    {"label": "Claim×Paper link", "value": s.get("claim_paper_candidate_links", 0)},
  ]
  next_actions = summary.get("recommended_actions") or []
  action_html = "".join(f"<li>{_safe(action)}</li>" for action in next_actions[:5])
  limited_html = ""
  if openalex_limited:
    limited_html = render_openalex_limited_execution_card(openalex_limited)
  link_block = summary.get("claim_paper_candidate_links") if isinstance(summary, dict) else {}
  links = link_block.get("representative_links") if isinstance(link_block, dict) else []
  link_html = render_claim_paper_candidate_map_card(links) if links else ""
  relevance_block = summary.get("paper_candidate_relevance") if isinstance(summary, dict) else {}
  relevance_html = render_paper_candidate_relevance_card(relevance_block) if relevance_block else ""
  synthesis_block = summary.get("evidence_map_synthesis") if isinstance(summary, dict) else {}
  synthesis_html = render_evidence_map_synthesis_card(synthesis_block) if synthesis_block else ""
  return (
    f"{render_info_box(explain_evidence_validation_readiness())}"
    f"{render_metric_cards(metrics)}"
    f'<div class="tc-patent-card">'
    f'<div class="tc-patent-title">OpenAlex: {openalex_mode}</div>'
    f'<div class="tc-patent-meta">{explain_evidence_validation_mode(openalex_mode)}</div>'
    f"</div>"
    f"{synthesis_html}"
    f"{relevance_html}"
    f"{limited_html}"
    f"{link_html}"
    f'<div class="tc-patent-card"><div class="tc-patent-title">次にやるべきこと</div>'
    f"<ul>{action_html or '<li>全文取得または手動確認リストを確認してください。</li>'}</ul></div>"
    f'<div class="tc-patent-meta">論文候補は技術背景の裏取り候補です。特許の有効性、実施可能性、侵害性を判断するものではありません。</div>'
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


_COST_TOKENS = ("usd", "$", "ドル", "原価", "課金", "price", "cost_cap", "budget")


def _text_has_cost_amounts(text: str) -> bool:
  lower = text.lower()
  return any(token in lower for token in _COST_TOKENS)


def render_acquisition_policy_summary(summary: dict[str, Any] | None) -> str:
  if not summary:
    return render_info_box("取得方針のサマリーはまだありません。パイプライン実行後に表示されます。")
  included = summary.get("included_items") or []
  excluded = summary.get("excluded_items") or []
  included_html = "<br>".join(f"• {item}" for item in included) or "• 特許候補の定点観測"
  excluded_html = "<br>".join(f"• {item}" for item in excluded) or "• （なし）"
  stop = _safe(summary.get("skipped_reason_japanese") or summary.get("execution_status_japanese"), "今回の取得方針に沿って処理しました。")
  return (
    f'<div class="tc-info-box">'
    f"<strong>今回の取得方針</strong><br>"
    f"実行タイプ: {_safe(summary.get('user_facing_name_japanese'))}<br>"
    f"{_safe(summary.get('user_facing_description_japanese'))}<br><br>"
    f"<strong>取得する情報</strong><br>{included_html}<br><br>"
    f"<strong>今回取得しない情報</strong><br>{excluded_html}<br><br>"
    f"<strong>停止理由</strong><br>{stop}<br>"
    f"手動確認候補: {int(summary.get('manual_watch_count', 0))} 件 / "
    f"全文取得対象: {int(summary.get('selected_targets_count', 0))} 件"
    f"</div>"
  )


def render_weekly_digest_preview_block(preview: dict[str, Any] | None, markdown_text: str = "") -> str:
  delivery_note = (
    "<br><em>この内容が週次で届く想定です。実際のメール送信はまだ行いません。</em>"
  )
  if markdown_text and not _text_has_cost_amounts(markdown_text):
    return (
      f'<div class="tc-info-box"><strong>Weekly Digest Preview</strong>'
      f"{delivery_note}"
      f'<pre style="white-space:pre-wrap">{markdown_text[:6000]}</pre></div>'
    )
  if not preview:
    return render_info_box("Weekly Digest Preview はまだありません。")
  policy = preview.get("acquisition_policy") or {}
  note = _safe(preview.get("note_japanese"), "週次メールのプレビューです。実際の送信はまだ行いません。")
  ev_map = preview.get("evidence_map_synthesis") or {}
  lines = [
    "<strong>Weekly Digest Preview — 今週の特許インテリジェンス</strong>",
    note,
    delivery_note,
    f"監視テーマ / 取得方針: {_safe(policy.get('name_japanese'))}",
    f"今週のDeep Dive: {ev_map.get('publication_number', '')} / {ev_map.get('title', '')}",
    f"Evidence Map: {ev_map.get('synthesis_status', '—')} "
    f"(papers={ev_map.get('selected_evidence_paper_count', 0)}, links={ev_map.get('claim_paper_link_count', 0)})",
    f"重要特許: {len(preview.get('important_patents', []))} 件",
    f"中国 Strategic Watch: {len(preview.get('china_strategic_watch', []))} 件",
    f"US Deep Dive候補: {len(preview.get('us_deep_dive_candidates', []))} 件",
  ]
  return f'<div class="tc-info-box">{"<br>".join(lines)}</div>'


def render_cost_ledger_debug(ledger_summary: dict[str, Any] | None) -> str:
  if not ledger_summary:
    return ""
  return (
    f'<div class="tc-warning-box">'
    f"<strong>開発者向け cost ledger</strong><br>"
    f"entries: {ledger_summary.get('entry_count', 0)}<br>"
    f"status counts: {ledger_summary.get('retrieval_status_counts', {})}"
    f"</div>"
  )


def render_fulltext_availability_notice(record: Any = None, markdown_text: str = "") -> str:
  if markdown_text and not _text_has_cost_amounts(markdown_text):
    return (
      f'<div class="tc-info-box"><strong>Fulltext Availability Probe</strong>'
      f'<pre style="white-space:pre-wrap">{markdown_text[:5000]}</pre></div>'
    )
  row = normalize_dataframe_row(record) if isinstance(record, dict) else _coerce_mapping(record)
  if not row:
    if record in (None, "", {}):
      return ""
    row = _coerce_mapping(record)
  probe_raw = (
    row.get("fulltext_availability_probe")
    or row.get("availability_probe")
    or row.get("probe")
  )
  probe = _coerce_mapping(probe_raw)
  probe_status = str(probe.get("probe_status") or row.get("probe_status") or "")
  status = str(row.get("retrieval_status") or probe.get("retrieval_status") or "")
  if status == "skipped_known_not_found":
    msg = "前回確認済みのため、今回は手動確認候補として扱います。"
  elif status in {"not_found", "bigquery_fulltext_not_available", "manual_google_patents_recommended", "fulltext_probe_not_found"} or probe_status in {
    "not_found_in_bigquery",
    "manual_route_recommended",
    "found_metadata_only",
  }:
    msg = (
      "BigQuery側では請求項が確認できませんでした。"
      "Google Patents / PDF / 手動貼り付けルートで確認してください。"
    )
  elif probe_status == "found_claims" or status == "fulltext_probe_found_claims":
    msg = "BigQueryで請求項の存在を確認しました。fulltext取得に進めます。"
  else:
    recommendation = str(probe.get("recommendation") or row.get("recommendation") or "")
    if recommendation == "manual_route_recommended":
      msg = (
        "BigQuery側では請求項が確認できませんでした。"
        "Google Patents / PDF / 手動貼り付けルートで確認してください。"
      )
    else:
      msg = str(probe.get("user_status_japanese") or row.get("user_status_japanese") or "")
  if not msg:
    raw = probe.get("raw_value")
    if raw:
      msg = f"全文確認の状態: {_safe(str(raw))}"
    elif record not in (None, "", {}):
      msg = "全文確認の状態を表示できませんでした。手動で Google Patents 等を確認してください。"
    else:
      return ""
  return f'<div class="tc-caution-box">{_safe(msg)}</div>'


def render_manual_fulltext_route_card(
  publication_number: str,
  manual_status: dict[str, Any] | None = None,
  *,
  bigquery_not_found: bool = False,
) -> str:
  status = manual_status or {}
  claims_present = bool(status.get("claims_present"))
  description_present = bool(status.get("description_present"))
  manual_exists = bool(status.get("manual_input_exists"))
  ready = bool(status.get("ready_for_claim_extraction"))
  route_label = _safe(status.get("route_label_japanese"), "claims入力待ち")

  intro = (
    "BigQuery public dataでは本文が確認できなかったため、"
    "Google Patents等からclaimsを手動で貼り付けるルートを使用します。"
  )
  if not bigquery_not_found and not manual_exists:
    intro = "Manual Fulltext Input Route（BigQueryで取れない公報向けの正式ルート）"

  cli_example = (
    "python scripts/import_manual_fulltext.py "
    f"--publication-number {publication_number or 'US-12565719-B2'} "
    "--source-url https://patents.google.com/patent/US12565719B2 "
    f"--claims-file inputs/manual/{publication_number or 'US-12565719-B2'}_claims.txt "
    "--input-route manual_google_patents "
    "--entered-by local_user"
  )

  ready_text = "はい（請求項ベースの限定解析）" if ready else "いいえ（claimsの入力が必要）"
  return (
    f'<div class="tc-info-box">'
    f"<strong>Manual Route</strong><br>"
    f"{intro}<br><br>"
    f"公報番号: {_safe(publication_number)}<br>"
    f"Manual input JSON: {'あり' if manual_exists else 'なし'}<br>"
    f"claims: {'あり' if claims_present else 'なし'}<br>"
    f"description: {'あり' if description_present else 'なし'}<br>"
    f"Claim Element抽出に進める: {ready_text}<br>"
    f"Manual Route状態: {route_label}<br><br>"
    f"<strong>CLI例</strong><br>"
    f'<pre style="white-space:pre-wrap;font-size:0.85em;">{cli_example}</pre>'
    f"</div>"
  )


def render_claims_paper_query_plan_card(
  plan: dict[str, Any] | None,
  *,
  manual_claims_loaded: bool = False,
) -> str:
  if not plan or (not plan.get("queries") and not plan.get("query_examples") and not plan.get("total_queries")):
    if manual_claims_loaded:
      return render_info_box(
        "manual claimsは読み込まれていますが、paper query候補はまだ生成されていません。"
        "Evidence Validationを実行するか、build_claims_paper_query_plan.py を実行してください。",
      )
    return ""

  total = int(plan.get("total_queries", 0))
  mode = str(plan.get("openalex_mode", "plan_only"))
  quality = plan.get("quality_summary") or {}
  ready = bool(plan.get("plan_ready_for_openalex", quality.get("plan_ready_for_openalex", False)))
  ready_label = "OpenAlex実行準備OK" if ready else "OpenAlex実行準備: 要改善"
  confidences = ", ".join(plan.get("confidence_levels", [])) or "medium/low"
  type_dist = plan.get("query_type_distribution") or quality.get("query_type_distribution") or {}
  type_html = "<br>".join(f"• {k}: {v}" for k, v in sorted(type_dist.items())) or "• n/a"
  conf_dist = plan.get("confidence_distribution") or quality.get("confidence_distribution") or {}
  conf_html = ", ".join(f"{k}={v}" for k, v in sorted(conf_dist.items())) or confidences
  examples_html = "".join(
    f"<li>{_safe(example)}</li>"
    for example in (plan.get("query_examples") or [])[:5]
  )
  caveat = _safe(
    plan.get("caveat_japanese")
    or "請求項から論文検索候補を作成しました。ただし、請求項は権利範囲を広く書くため、明細書・実施例ベースの裏取りより精度は限定的です。",
  )
  manual_note = (
    "<br>manual claims loaded: はい"
    if manual_claims_loaded
    else ""
  )
  return (
    f'<div class="tc-info-box">'
    f"<strong>Claims-based Paper Query Plan</strong>{manual_note}<br>"
    f"請求項から論文検索候補を作成しました。ただし、請求項は権利範囲を広く書くため、"
    f"明細書・実施例ベースの裏取りより精度は限定的です。<br><br>"
    f"候補数: {total} / {ready_label}<br>"
    f"query type分布:<br>{type_html}<br>"
    f"confidence分布: {conf_html}<br>"
    f"OpenAlex: {mode}（本実行はまだ任意）<br>"
    f"論文の位置づけ: supporting evidence candidate（証明ではありません）<br><br>"
    f"<strong>代表query</strong><ul>{examples_html}</ul>"
    f"<strong>Caveat</strong><br>{caveat}"
    f"</div>"
  )


def render_openalex_limited_execution_card(
  limited: dict[str, Any] | None,
  *,
  source_quality: list[dict[str, Any]] | None = None,
) -> str:
  if not limited:
    return ""
  mode = str(limited.get("mode") or "plan_only")
  status = str(limited.get("execution_status") or mode)
  selected = limited.get("selected_queries") or []
  papers = limited.get("paper_records") or []
  queries_html = "".join(
    f"<li>[{_safe(row.get('query_type'))}] ({_safe(row.get('confidence'))}) {_safe(row.get('query'))}</li>"
    for row in selected[:5]
  )
  papers_html = "".join(
    f"<li>{_safe(p.get('title', '(no title)'))}</li>"
    for p in papers[:5]
  )
  quality_rows = source_quality or limited.get("source_quality_results") or []
  quality_html = "".join(
    f"<li>{_safe(row.get('quality_level', 'unknown'))}: {_safe(row.get('source_name') or row.get('source_id', ''))}</li>"
    for row in quality_rows[:5]
  )
  errors = limited.get("api_errors") or []
  error_html = "".join(f"<li>{_safe(err)}</li>" for err in errors[:3])
  caveat = _safe(
    limited.get("caveat_japanese")
    or "論文候補は技術背景の裏取り候補です。特許の有効性、実施可能性、侵害性を判断するものではありません。",
  )
  return (
    f'<div class="tc-info-box">'
    f"<strong>OpenAlex Limited Execution</strong><br>"
    f"実行状態: {_safe(status)} / モード: {_safe(mode)}<br>"
    f"実行query: {limited.get('executed_queries_count', 0)} / "
    f"取得paper: {limited.get('total_paper_records', len(papers))} / "
    f"cache hits: {limited.get('cache_hits', 0)}<br><br>"
    f"<strong>Selected queries</strong><ul>{queries_html or '<li>(none)</li>'}</ul>"
    f"<strong>Paper records</strong><ul>{papers_html or '<li>(none)</li>'}</ul>"
    f"<strong>Source quality</strong><ul>{quality_html or '<li>(none)</li>'}</ul>"
    f"{f'<strong>API errors</strong><ul>{error_html}</ul>' if errors else ''}"
    f"<strong>Caveat</strong><br>{caveat}"
    f"</div>"
  )


def render_claim_paper_candidate_map_card(links: list[dict[str, Any]] | None) -> str:
  if not links:
    return ""
  type_counts: dict[str, int] = {}
  conf_counts: dict[str, int] = {}
  for link in links:
    type_counts[str(link.get("link_type"))] = type_counts.get(str(link.get("link_type")), 0) + 1
    conf_counts[str(link.get("confidence"))] = conf_counts.get(str(link.get("confidence")), 0) + 1
  type_html = ", ".join(f"{k}={v}" for k, v in sorted(type_counts.items()))
  conf_html = ", ".join(f"{k}={v}" for k, v in sorted(conf_counts.items()))
  rep_html = "".join(
    f"<li>{_safe(link.get('element_type'))} ↔ {_safe(link.get('paper_title'))} "
    f"({_safe(link.get('link_type'))}, {_safe(link.get('confidence'))}"
    f"{', 弱い対応' if link.get('is_fallback_link') else ''})</li>"
    for link in links[:5]
  )
  return (
    f'<div class="tc-info-box">'
    f"<strong>Claim × Paper Candidate Map</strong><br>"
    f"link数: {len(links)}<br>"
    f"link_type分布: {_safe(type_html)}<br>"
    f"confidence分布: {_safe(conf_html)}<br><br>"
    f"<strong>代表リンク</strong><ul>{rep_html}</ul>"
    f"論文候補は技術背景の裏取り候補です。特許の有効性、実施可能性、侵害性を判断するものではありません。"
    f"</div>"
  )


def render_paper_candidate_relevance_card(relevance: dict[str, Any] | None) -> str:
  if not relevance:
    return ""
  selected = relevance.get("representative_selected_papers") or relevance.get("selected_evidence_papers") or []
  excluded = relevance.get("excluded_broad_off_topic") or []
  bucket_dist = relevance.get("relevance_bucket_distribution") or {}
  bucket_html = ", ".join(f"{k}={v}" for k, v in sorted(bucket_dist.items())) or "n/a"
  selected_html = "".join(
    f"<li>{_safe(row.get('title', '(no title)'))} "
    f"({_safe(row.get('relevance_bucket'))}, score={row.get('relevance_score', '')}, "
    f"doi={_safe(row.get('doi') or 'n/a')}, source={_safe(row.get('source') or row.get('source_name') or 'n/a')}, "
    f"cited_by={row.get('cited_by_count', 'n/a')})</li>"
    for row in selected[:5]
    if isinstance(row, dict)
  )
  broad_html = "".join(
    f"<li>{_safe(row.get('title', '(no title)'))} ({_safe(row.get('relevance_bucket'))})</li>"
    for row in excluded[:5]
    if isinstance(row, dict)
  )
  caveat = _safe(
    relevance.get("caveat_japanese")
    or "広い複合材料レビューは背景候補として扱い、PAN系炭素繊維・炭化・物性に近い論文を優先します。",
  )
  return (
    f'<div class="tc-info-box">'
    f"<strong>Paper Candidate Relevance Filter</strong><br>"
    f"total candidates: {relevance.get('total_paper_candidates', 0)} / "
    f"selected: {relevance.get('selected_evidence_papers', len(selected))}<br>"
    f"off-topic除外: {relevance.get('excluded_off_topic_count', 0)} / "
    f"broad background: {relevance.get('broad_background_count', 0)}<br>"
    f"bucket分布: {_safe(bucket_html)}<br><br>"
    f"<strong>Selected evidence papers</strong><ul>{selected_html or '<li>(none)</li>'}</ul>"
    f"<strong>Broad background / excluded</strong><ul>{broad_html or '<li>(none)</li>'}</ul>"
    f"<strong>Caveat</strong><br>{caveat}"
    f"</div>"
  )


def render_evidence_map_synthesis_card(synthesis: dict[str, Any] | None) -> str:
  if not synthesis:
    return ""
  findings_html = "".join(
    f"<li>{_safe(f)}</li>" for f in (synthesis.get("key_findings_japanese") or [])[:5]
  )
  gaps_html = "".join(
    f"<li>{_safe(g)}</li>" for g in (synthesis.get("evidence_gaps_japanese") or [])[:5]
  )
  actions_html = "".join(
    f"<li>{_safe(a)}</li>" for a in (synthesis.get("next_actions_japanese") or [])[:5]
  )
  papers_html = "".join(
    f"<li>{_safe(p.get('title', '(no title)'))} "
    f"({_safe(p.get('relevance_bucket', ''))}, doi={_safe(p.get('doi') or 'n/a')}, "
    f"source={_safe(p.get('source') or p.get('source_name') or 'n/a')}, "
    f"cited_by={p.get('cited_by_count', 'n/a')})</li>"
    for p in (synthesis.get("selected_evidence_papers") or [])[:5]
    if isinstance(p, dict)
  )
  items = synthesis.get("evidence_map_items") or []
  items_html = "".join(
    f"<li>{_safe(i.get('element_type'))}: {_safe((i.get('element_text') or '')[:60])} "
    f"→ {_safe(i.get('best_paper_title') or '(no paper)')} "
    f"({_safe(i.get('confidence'))}"
    f"{', 弱い対応' if i.get('is_fallback_link') else ''})</li>"
    for i in items[:8]
    if isinstance(i, dict)
  )
  caveat = _safe(
    (synthesis.get("caveats_japanese") or [""])[0]
    if synthesis.get("caveats_japanese")
    else "このEvidence Mapは、請求項と論文候補の対応を整理したものです。論文候補は技術背景の裏取り候補であり、特許主張を証明するものではありません。",
  )
  return (
    f'<div class="tc-info-box">'
    f"<strong>Evidence Map Synthesis</strong><br>"
    f"対象: {_safe(synthesis.get('publication_number'))} / {_safe(synthesis.get('title'))}<br>"
    f"status: {_safe(synthesis.get('synthesis_status'))} / "
    f"Claim Elements: {synthesis.get('claim_element_count', 0)} / "
    f"selected papers: {synthesis.get('selected_evidence_paper_count', 0)} / "
    f"links: {synthesis.get('claim_paper_link_count', 0)}<br><br>"
    f"<strong>Key findings</strong><ul>{findings_html or '<li>(none)</li>'}</ul>"
    f"<strong>Claim Element × Paper Candidate</strong><ul>{items_html or '<li>(none)</li>'}</ul>"
    f"<strong>Selected evidence papers</strong><ul>{papers_html or '<li>(none)</li>'}</ul>"
    f"<strong>Evidence gaps</strong><ul>{gaps_html or '<li>(none)</li>'}</ul>"
    f"<strong>Next actions</strong><ul>{actions_html or '<li>(none)</li>'}</ul>"
    f"<strong>Caveat</strong><br>{caveat}"
    f"</div>"
  )


def discover_demo_artifacts(project_root: str | Path | None = None) -> list[dict[str, Any]]:
  root = Path(project_root or Path.cwd())
  rows: list[dict[str, Any]] = []
  for key, label, relative in DEMO_ARTIFACT_SPECS:
    path = root / relative
    rows.append(
      {
        "key": key,
        "label": label,
        "path": str(path),
        "exists": path.exists(),
      },
    )
  return rows


def render_demo_artifact_status(artifacts: list[dict[str, Any]] | None) -> str:
  rows = artifacts or []
  if not rows:
    return render_info_box("デモ成果物の検出情報がありません。")
  items_html = "".join(
    f"<li>{'✓' if row.get('exists') else '—'} {_safe(row.get('label'))}"
    f"{'（準備済み）' if row.get('exists') else '（まだ生成されていません）'}</li>"
    for row in rows
  )
  return (
    f'<div class="tc-card-box">'
    f"<strong>デモ成果物の状態</strong><ul>{items_html}</ul>"
    f"存在する成果物だけEvidence Mapセクションに表示します。"
    f"</div>"
  )


def render_demo_story_cards() -> str:
  card1 = (
    f'<div class="tc-card-box">'
    f"<strong>Tech Cartography がやること</strong><ul>"
    f"<li>特許候補を集める</li>"
    f"<li>読むべき特許を選ぶ</li>"
    f"<li>請求項から技術要素を抽出する</li>"
    f"<li>論文候補と対応づける</li>"
    f"<li>Evidence Gapと次アクションを出す</li>"
    f"</ul></div>"
  )
  card2 = (
    f'<div class="tc-card-box">'
    f"<strong>今回のDeep Dive対象</strong><ul>"
    f"<li>{DEMO_DEEP_DIVE_PUBLICATION}</li>"
    f"<li>{DEMO_DEEP_DIVE_TITLE}</li>"
    f"<li>manual claims route</li>"
    f"<li>Evidence Map ready</li>"
    f"</ul></div>"
  )
  card3 = (
    f'<div class="tc-caution-box">'
    f"<strong>重要な注意</strong><ul>"
    f"<li>論文は証明ではなく supporting evidence candidate</li>"
    f"<li>FTO / 侵害 / 有効性判断ではない</li>"
    f"<li>専門家レビューが必要</li>"
    f"</ul></div>"
  )
  return card1 + card2 + card3


def render_evidence_map_summary_metrics(synthesis: dict[str, Any] | None) -> str:
  if not synthesis:
    return ""
  metrics = [
    {"label": "synthesis status", "value": synthesis.get("synthesis_status", "—")},
    {"label": "Claim Elements", "value": synthesis.get("claim_element_count", 0)},
    {"label": "selected papers", "value": synthesis.get("selected_evidence_paper_count", 0)},
    {"label": "claim-paper links", "value": synthesis.get("claim_paper_link_count", 0)},
    {"label": "retrieval route", "value": synthesis.get("retrieval_route", "—")},
    {"label": "evidence level", "value": synthesis.get("evidence_level", "—")},
  ]
  return render_metric_cards(metrics)


def _relevance_role_label(bucket: str, role: str = "") -> str:
  if role and "supporting_evidence" in role:
    return "supporting evidence candidate"
  if role:
    return role.replace("_", " ")
  if bucket in {"strong_material_process_background", "property_background", "surface_interface_background"}:
    return "supporting evidence candidate"
  return "background literature"


def render_selected_evidence_papers_list(
  papers: list[dict[str, Any]] | None,
  *,
  excluded_papers: list[dict[str, Any]] | None = None,
) -> str:
  selected = [row for row in (papers or []) if isinstance(row, dict)]
  if not selected:
    return render_info_box("Selected Evidence Papers はまだ生成されていません。")

  cards_html = ""
  for paper in selected[:8]:
    bucket = str(paper.get("relevance_bucket") or "")
    role = _relevance_role_label(bucket, str(paper.get("recommended_evidence_role") or ""))
    cards_html += (
      f'<div class="tc-patent-card">'
      f'<div class="tc-patent-title">{_safe(paper.get("title", "(no title)"))}</div>'
      f'<div class="tc-patent-meta">'
      f"DOI: {_safe(paper.get('doi') or 'n/a')}<br>"
      f"年: {_safe(paper.get('publication_year') or 'n/a')} / "
      f"引用数: {_safe(paper.get('cited_by_count') or 'n/a')}<br>"
      f"source: {_safe(paper.get('source') or paper.get('source_name') or 'n/a')}<br>"
      f"relevance bucket: {_safe(bucket)}<br>"
      f"<em>{_safe(role)}</em>"
      f"</div></div>"
    )

  excluded_html = ""
  excluded = [row for row in (excluded_papers or []) if isinstance(row, dict)]
  if excluded:
    excluded_html = (
      f"<br><strong>Evidence Map外（broad / off-topic）</strong><ul>"
      + "".join(
        f"<li>{_safe(row.get('title', '(no title)'))} ({_safe(row.get('relevance_bucket'))})</li>"
        for row in excluded[:5]
      )
      + "</ul>"
    )

  return (
    f'<div class="tc-info-box">'
    f"<strong>Selected Evidence Papers</strong>（{len(selected)} 件）<br><br>"
    f"{cards_html}{excluded_html}"
    f"</div>"
  )


def render_claim_paper_links_detail(links: list[dict[str, Any]] | None) -> str:
  rows = [row for row in (links or []) if isinstance(row, dict)]
  if not rows:
    return render_info_box("Claim × Paper Candidate Links はまだ生成されていません。")

  items_html = ""
  for link in rows[:10]:
    confidence = str(link.get("confidence") or "weak")
    weak_note = ""
    if confidence in {"low", "weak"} or link.get("is_fallback_link"):
      weak_note = f"<br><span style='font-size:0.92rem;'>{WEAK_LINK_EXPLANATION_JAPANESE}</span>"
    fallback_tag = " <em>[弱い対応]</em>" if link.get("is_fallback_link") else ""
    items_html += (
      f'<div class="tc-patent-card">'
      f'<div class="tc-patent-title">{_safe(link.get("paper_title", "(no paper)"))}{fallback_tag}</div>'
      f'<div class="tc-patent-meta">'
      f"claim element: {_safe((link.get('element_text') or link.get('element_type') or '')[:80])}<br>"
      f"link type: {_safe(link.get('link_type'))} / confidence: {_safe(confidence)}<br>"
      f"DOI: {_safe(link.get('paper_doi') or 'n/a')} / "
      f"source: {_safe(link.get('paper_source') or 'n/a')} / "
      f"cited_by: {_safe(link.get('cited_by_count') or 'n/a')}<br>"
      f"caveat: {_safe(link.get('caveat_japanese') or '—')}"
      f"{weak_note}"
      f"</div></div>"
    )

  return (
    f'<div class="tc-info-box">'
    f"<strong>Claim × Paper Candidate Links</strong>（{len(rows)} 件）<br><br>"
    f"{items_html}"
    f"</div>"
  )


def render_evidence_gaps_caution(gaps: list[str] | None) -> str:
  gap_items = [gap for gap in (gaps or []) if gap]
  default_gaps = [
    "BigQuery全文が欠落している可能性があります。",
    "manual claims routeを使用しています。",
    "description未入力のため材料・プロセスの裏取り精度が限定的です。",
    "examples未確認のため物性数値の裏取りは不足しています。",
    "claims_only由来のため、論文は証明ではなく supporting evidence candidate としてのみ扱えます。",
    "CN/EP/JP候補はmanual route継続で確認が必要です。",
  ]
  display_gaps = gap_items or default_gaps
  items_html = "".join(f"<li>{_safe(gap)}</li>" for gap in display_gaps[:8])
  return (
    f'<div class="tc-caution-box">'
    f"<strong>Evidence Gaps（確認が必要な点）</strong>"
    f"<ul>{items_html}</ul>"
    f"これらは警告ではなく、現時点のデータ制約を示す注意事項です。"
    f"</div>"
  )


def render_evidence_map_demo_section(
  synthesis: dict[str, Any] | None,
  *,
  selected_papers: list[dict[str, Any]] | None = None,
  claim_links: list[dict[str, Any]] | None = None,
  excluded_papers: list[dict[str, Any]] | None = None,
  artifact_status: list[dict[str, Any]] | None = None,
) -> str:
  parts = [
    render_info_box(EVIDENCE_MAP_INTRO_JAPANESE),
    render_demo_artifact_status(artifact_status),
  ]
  if synthesis:
    parts.append(render_evidence_map_summary_metrics(synthesis))
    findings = synthesis.get("key_findings_japanese") or []
    if findings:
      findings_html = "".join(f"<li>{_safe(item)}</li>" for item in findings[:6])
      parts.append(
        f'<div class="tc-card-box"><strong>Key Findings</strong><ul>{findings_html}</ul></div>',
      )
    papers = selected_papers or synthesis.get("selected_evidence_papers") or []
    parts.append(
      render_selected_evidence_papers_list(
        papers,
        excluded_papers=excluded_papers or synthesis.get("broad_background_papers"),
      ),
    )
    links = claim_links or []
    if not links and synthesis.get("evidence_map_items"):
      links = [
        {
          "element_type": item.get("element_type"),
          "element_text": item.get("element_text"),
          "paper_title": item.get("best_paper_title"),
          "paper_doi": item.get("best_paper_doi"),
          "paper_source": item.get("best_paper_source"),
          "cited_by_count": item.get("best_paper_cited_by_count"),
          "link_type": item.get("link_type"),
          "confidence": item.get("confidence"),
          "is_fallback_link": item.get("is_fallback_link"),
          "caveat_japanese": item.get("caveat_japanese"),
        }
        for item in synthesis.get("evidence_map_items") or []
        if isinstance(item, dict) and item.get("best_paper_title")
      ]
    parts.append(render_claim_paper_links_detail(links))
    parts.append(render_evidence_gaps_caution(synthesis.get("evidence_gaps_japanese")))
    actions = synthesis.get("next_actions_japanese") or []
    if actions:
      parts.append(render_next_action_box(actions))
    caveats = synthesis.get("caveats_japanese") or [EVIDENCE_MAP_INTRO_JAPANESE]
    caveat_html = "".join(f"<li>{_safe(c)}</li>" for c in caveats[:4])
    parts.append(
      f'<div class="tc-card-box"><strong>Caveats</strong><ul>{caveat_html}</ul></div>',
    )
  else:
    parts.append(
      render_warning_box(
        "Evidence Map Synthesis はまだ生成されていません。filter / build スクリプトを実行してください。",
      ),
    )
  return "".join(parts)
