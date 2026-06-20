"""Final end-to-end validation summary for MVP freeze (Phase 24.4D)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from tech_cartography.validation.end_to_end_chain import (
  CHAIN_CAUTION,
  DIGEST_CAUTION,
  EndToEndChainConfig,
  LINK_CAUTION,
  PAPER_CAUTION,
  WATCH_CAUTION,
  WEB_SIGNAL_CAUTION,
  inspect_end_to_end_status,
)

FREEZE_READY_AFTER_CROSS_THEME_E2E = "freeze_ready_after_cross_theme_end_to_end_validation"
FREEZE_READY_WITH_DECLARED_E2E_LIMITATIONS = "freeze_ready_with_declared_e2e_limitations"
NOT_READY_FOR_FULL_E2E_FREEZE = "not_ready_for_full_e2e_freeze"

LEGAL_CAUTION = (
  "本サマリーは FTO（Freedom to Operate）、侵害、有効性の法的判断ではありません。"
  "原典確認と専門家レビューが必要です。"
)
QUERY_PLAN_CAUTION = (
  "query_plan_ready は計画のみであり、実データ取得済み（pass）と混同しないでください。"
)
CANDIDATE_CAUTION = (
  "Paper/Web/Link/Watch/Digest は candidate / preview であり、最終結論・法的判断ではありません。"
)


@dataclass
class SeedFinalStatus:
  publication_number: str
  stage2: str
  stage3: str
  stage4: str
  stage5: str
  stage6: str
  stage7: str
  stage8: str
  overall_status: str
  paper_data_type: str
  web_data_type: str
  artifacts: dict[str, bool] = field(default_factory=dict)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class FinalValidationSummary:
  theme_id: str
  theme_name: str
  created_at: str
  seed_publications: list[str]
  seed_count: int
  stage2_pass_count: int
  stage3_pass_count: int
  stage4_paper_count: int
  stage5_web_count: int
  stage6_link_count: int
  stage7_watch_count: int
  stage8_digest_count: int
  completed_end_to_end_count: int
  completed_seed_publications: list[str]
  incomplete_seed_publications: list[str]
  evidence_level: str
  freeze_readiness: str
  caveats: list[str]
  next_actions: list[str]
  seed_statuses: list[dict[str, Any]] = field(default_factory=list)
  stage4_query_plan_count: int = 0
  stage5_query_plan_count: int = 0

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


def _utc_now() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _paper_data_type(stage4: str) -> str:
  if stage4 == "pass":
    return "actual_data"
  if stage4 == "query_plan_ready":
    return "query_plan_only"
  return "missing"


def _web_data_type(stage5: str) -> str:
  if stage5 == "pass":
    return "actual_data"
  if stage5 == "query_plan_ready":
    return "query_plan_only"
  return "missing"


def _stage_pass(status: str) -> bool:
  return status == "pass"


def _stage7_complete(status: str) -> bool:
  return status in {"pass", "limited_watch_brief"}


def _seed_fully_complete(row: SeedFinalStatus) -> bool:
  return (
    row.stage2 == "pass"
    and row.stage3 == "pass"
    and row.stage4 == "pass"
    and row.stage5 == "pass"
    and row.stage6 == "pass"
    and _stage7_complete(row.stage7)
    and row.stage8 == "pass"
  )


def _seed_e2e_chain_complete(row: SeedFinalStatus) -> bool:
  """Stage 8 reached with link/watch/digest artifacts (Stage 4/5 may be query_plan)."""
  return (
    row.stage2 == "pass"
    and row.stage3 == "pass"
    and row.stage6 == "pass"
    and _stage7_complete(row.stage7)
    and row.stage8 == "pass"
    and row.stage4 in {"pass", "query_plan_ready"}
    and row.stage5 in {"pass", "query_plan_ready"}
  )


def _detect_artifacts(root: Path, theme_id: str, pub: str) -> dict[str, bool]:
  return {
    "manual_claims": (root / "outputs" / "manual_fulltext_inputs" / f"{pub}.json").exists(),
    "evidence_skeleton": (
      root / "outputs" / "evidence_map_synthesis" / pub / "evidence_map_skeleton.json"
    ).exists(),
    "paper_candidates_csv": (root / "outputs" / "paper_candidates" / pub / "paper_candidates.csv").exists(),
    "selected_evidence_papers": (
      root / "outputs" / "paper_candidates" / pub / "selected_evidence_papers.csv"
    ).exists(),
    "paper_query_plan": (root / "outputs" / "paper_candidates" / pub / "paper_query_plan.json").exists(),
    "web_signals_csv": (
      root / "outputs" / "web_signals" / f"{theme_id}_{pub}" / "web_signals.csv"
    ).exists(),
    "web_signal_query_plan": (
      root / "outputs" / "web_signals" / f"{theme_id}_{pub}" / "web_signal_query_plan.json"
    ).exists(),
    "link_candidates": (
      root / "outputs" / "web_signal_links" / pub / "web_signal_link_candidates.csv"
    ).exists(),
    "strategic_watch_brief": (
      root / "outputs" / "strategic_watch_briefs" / pub / "strategic_watch_brief.md"
    ).exists(),
    "digest_md": (root / "outputs" / "delivery" / f"jp_seed_digest_{pub}.md").exists(),
    "digest_html": (root / "outputs" / "delivery" / f"jp_seed_digest_{pub}.html").exists(),
  }


def build_final_validation_summary(
  *,
  project_root: Path | str,
  theme_id: str,
  theme_name: str,
  seed_publications: list[str],
) -> FinalValidationSummary:
  root = Path(project_root)
  pubs = [str(p).strip() for p in seed_publications if str(p).strip()]
  seen: set[str] = set()
  unique_pubs: list[str] = []
  for pub in pubs:
    if pub not in seen:
      seen.add(pub)
      unique_pubs.append(pub)

  config = EndToEndChainConfig(
    theme_id=theme_id,
    theme_name=theme_name,
    publication_numbers=unique_pubs,
    output_root=str(root),
    allow_external_api=False,
    dry_run=True,
  )
  e2e_result = inspect_end_to_end_status(config)

  seed_rows: list[SeedFinalStatus] = []
  for chain in e2e_result.seed_statuses:
    pub = chain.publication_number
    artifacts = _detect_artifacts(root, theme_id, pub)
    row = SeedFinalStatus(
      publication_number=pub,
      stage2=chain.stage2_manual_claims,
      stage3=chain.stage3_evidence_skeleton,
      stage4=chain.stage4_paper_candidates,
      stage5=chain.stage5_web_signals,
      stage6=chain.stage6_link_candidates,
      stage7=chain.stage7_strategic_watch,
      stage8=chain.stage8_digest,
      overall_status=chain.overall_status,
      paper_data_type=_paper_data_type(chain.stage4_paper_candidates),
      web_data_type=_web_data_type(chain.stage5_web_signals),
      artifacts=artifacts,
    )
    seed_rows.append(row)

  stage2_pass = sum(1 for r in seed_rows if _stage_pass(r.stage2))
  stage3_pass = sum(1 for r in seed_rows if _stage_pass(r.stage3))
  stage4_pass = sum(1 for r in seed_rows if _stage_pass(r.stage4))
  stage4_query = sum(1 for r in seed_rows if r.stage4 == "query_plan_ready")
  stage5_pass = sum(1 for r in seed_rows if _stage_pass(r.stage5))
  stage5_query = sum(1 for r in seed_rows if r.stage5 == "query_plan_ready")
  stage6_pass = sum(1 for r in seed_rows if _stage_pass(r.stage6))
  stage7_pass = sum(1 for r in seed_rows if _stage7_complete(r.stage7))
  stage8_pass = sum(1 for r in seed_rows if _stage_pass(r.stage8))

  completed_full = [r.publication_number for r in seed_rows if _seed_fully_complete(r)]
  completed_e2e = [r.publication_number for r in seed_rows if _seed_e2e_chain_complete(r)]
  incomplete = [r.publication_number for r in seed_rows if r.publication_number not in completed_e2e]

  if len(unique_pubs) > 0 and len(completed_full) == len(unique_pubs):
    freeze_readiness = FREEZE_READY_AFTER_CROSS_THEME_E2E
    evidence_level = "cross_theme_end_to_end_with_actual_paper_web_data"
  elif len(completed_e2e) == len(unique_pubs) and len(unique_pubs) > 0:
    if stage4_query > 0 or stage5_query > 0:
      freeze_readiness = FREEZE_READY_WITH_DECLARED_E2E_LIMITATIONS
      evidence_level = "cross_theme_end_to_end_with_query_plan_limitations"
    else:
      freeze_readiness = FREEZE_READY_AFTER_CROSS_THEME_E2E
      evidence_level = "cross_theme_end_to_end_candidate_artifacts"
  elif any(r.stage6 != "pass" or not _stage_pass(r.stage8) for r in seed_rows):
    freeze_readiness = NOT_READY_FOR_FULL_E2E_FREEZE
    evidence_level = "partial_end_to_end_incomplete"
  elif stage4_query > 0 or stage5_query > 0:
    freeze_readiness = FREEZE_READY_WITH_DECLARED_E2E_LIMITATIONS
    evidence_level = "cross_theme_end_to_end_with_query_plan_limitations"
  else:
    freeze_readiness = NOT_READY_FOR_FULL_E2E_FREEZE
    evidence_level = "partial_end_to_end_incomplete"

  next_actions: list[str] = []
  if incomplete:
    for row in seed_rows:
      if row.publication_number in incomplete:
        next_actions.append(f"{row.publication_number}: Stage 6以降または Paper/Web 実データを完了してください")
  elif freeze_readiness == FREEZE_READY_WITH_DECLARED_E2E_LIMITATIONS:
    next_actions.append("query_plan_ready の Stage がある場合は README/既知制限に明記した上で Freeze")
  elif freeze_readiness == FREEZE_READY_AFTER_CROSS_THEME_E2E:
    next_actions.append("MVP Freeze: US デモ + JP 3件 E2E 検証完了を README/デモ台本に反映")

  caveats = [
    QUERY_PLAN_CAUTION,
    PAPER_CAUTION,
    WEB_SIGNAL_CAUTION,
    LINK_CAUTION,
    WATCH_CAUTION,
    DIGEST_CAUTION,
    CANDIDATE_CAUTION,
    LEGAL_CAUTION,
    CHAIN_CAUTION,
  ]

  return FinalValidationSummary(
    theme_id=theme_id,
    theme_name=theme_name,
    created_at=_utc_now(),
    seed_publications=unique_pubs,
    seed_count=len(unique_pubs),
    stage2_pass_count=stage2_pass,
    stage3_pass_count=stage3_pass,
    stage4_paper_count=stage4_pass,
    stage5_web_count=stage5_pass,
    stage6_link_count=stage6_pass,
    stage7_watch_count=stage7_pass,
    stage8_digest_count=stage8_pass,
    completed_end_to_end_count=len(completed_e2e),
    completed_seed_publications=completed_e2e,
    incomplete_seed_publications=incomplete,
    evidence_level=evidence_level,
    freeze_readiness=freeze_readiness,
    caveats=caveats,
    next_actions=next_actions,
    seed_statuses=[row.to_dict() for row in seed_rows],
    stage4_query_plan_count=stage4_query,
    stage5_query_plan_count=stage5_query,
  )


def render_final_end_to_end_validation_summary_md(summary: FinalValidationSummary) -> str:
  lines = [
    "# Final End-to-End Validation Summary (Phase 24.4D)",
    "",
    "## 検証テーマ",
    "",
    f"- theme_id: `{summary.theme_id}`",
    f"- theme_name: {summary.theme_name}",
    f"- created_at: {summary.created_at}",
    f"- evidence_level: `{summary.evidence_level}`",
    "",
    "## Seed 公報",
    "",
  ]
  for pub in summary.seed_publications:
    lines.append(f"- {pub}")

  lines.extend(
    [
      "",
      "## Stage 2〜8 結果",
      "",
      "| publication_number | Stage 2 | Stage 3 | Stage 4 Paper | Stage 5 Web | Stage 6 Link | Stage 7 Watch | Stage 8 Digest | paper_type | web_type | overall |",
      "|---|---|---|---|---|---|---|---|---|---|---|",
    ],
  )
  for row in summary.seed_statuses:
    lines.append(
      f"| {row['publication_number']} | {row['stage2']} | {row['stage3']} | {row['stage4']} | "
      f"{row['stage5']} | {row['stage6']} | {row['stage7']} | {row['stage8']} | "
      f"{row['paper_data_type']} | {row['web_data_type']} | {row['overall_status']} |",
    )

  lines.extend(
    [
      "",
      "## 集計",
      "",
      f"- Stage 2 pass: **{summary.stage2_pass_count} / {summary.seed_count}**",
      f"- Stage 3 pass: **{summary.stage3_pass_count} / {summary.seed_count}**",
      f"- Stage 4 paper (actual data / pass): **{summary.stage4_paper_count} / {summary.seed_count}**",
      f"- Stage 4 query_plan_ready: **{summary.stage4_query_plan_count} / {summary.seed_count}**",
      f"- Stage 5 web (actual data / pass): **{summary.stage5_web_count} / {summary.seed_count}**",
      f"- Stage 5 query_plan_ready: **{summary.stage5_query_plan_count} / {summary.seed_count}**",
      f"- Stage 6 link: **{summary.stage6_link_count} / {summary.seed_count}**",
      f"- Stage 7 watch: **{summary.stage7_watch_count} / {summary.seed_count}**",
      f"- Stage 8 digest: **{summary.stage8_digest_count} / {summary.seed_count}**",
      f"- E2E chain complete: **{summary.completed_end_to_end_count} / {summary.seed_count}**",
      "",
      "## 完了状況",
      "",
    ],
  )
  if summary.completed_end_to_end_count == summary.seed_count and summary.seed_count > 0:
    lines.append(
      f"- **{summary.seed_count}件すべて End-to-End Chain（Stage 8 Digest preview まで）を確認**"
    )
  else:
    lines.append(f"- 完了: {', '.join(summary.completed_seed_publications) or '（なし）'}")
    if summary.incomplete_seed_publications:
      lines.append(f"- 未完了: {', '.join(summary.incomplete_seed_publications)}")

  lines.extend(
    [
      "",
      "## query_plan_ready と実データの区別",
      "",
      f"- {QUERY_PLAN_CAUTION}",
      "- `paper_type=actual_data`: paper_candidates.csv または selected_evidence_papers.csv あり",
      "- `paper_type=query_plan_only`: paper_query_plan.json のみ",
      "- `web_type=actual_data`: web_signals.csv または review_pack あり",
      "- `web_type=query_plan_only`: web_signal_query_plan.json のみ",
      "",
      "## Freeze Readiness",
      "",
      f"- **{summary.freeze_readiness}**",
      "",
      "## 重要な注意（candidate / preview）",
      "",
      f"- {PAPER_CAUTION}",
      f"- {WEB_SIGNAL_CAUTION}",
      f"- {LINK_CAUTION}",
      f"- {WATCH_CAUTION}",
      f"- {DIGEST_CAUTION}",
      f"- {LEGAL_CAUTION}",
      "",
    ],
  )
  return "\n".join(lines)


def render_freeze_readiness_final_md(summary: FinalValidationSummary) -> str:
  return "\n".join(
    [
      "# Freeze Readiness Final (Phase 24.4D)",
      "",
      "## 結論",
      "",
      f"**{summary.freeze_readiness}**",
      "",
      "## 理由",
      "",
      "1. 既存 US デモ（US-12565719-B2）は Weekly Digest まで complete_existing_demo。",
      f"2. 別テーマ「{summary.theme_name}」の JP seed {summary.seed_count} 件で End-to-End Chain を UI 上で実行。",
      f"3. Stage 2 pass: {summary.stage2_pass_count}, Stage 3: {summary.stage3_pass_count}, "
      f"Stage 4 paper (pass): {summary.stage4_paper_count}, Stage 5 web (pass): {summary.stage5_web_count}, "
      f"Stage 6 link: {summary.stage6_link_count}, Stage 7 watch: {summary.stage7_watch_count}, "
      f"Stage 8 digest: {summary.stage8_digest_count}.",
      f"4. E2E chain complete: {summary.completed_end_to_end_count}/{summary.seed_count}.",
      f"5. query_plan_ready: Stage 4={summary.stage4_query_plan_count}, Stage 5={summary.stage5_query_plan_count}.",
      f"6. evidence_level: `{summary.evidence_level}`.",
      "7. Paper/Web/Link/Watch/Digest は candidate / preview であり、法的判断ではない。",
      "",
      "## 次のアクション",
      "",
    ]
    + [f"- {a}" for a in summary.next_actions]
    + ["", f"- {LEGAL_CAUTION}", ""],
  )


def render_reviewer_response_final_md(summary: FinalValidationSummary) -> str:
  return "\n".join(
    [
      "# Reviewer Response Final (Phase 24.4D)",
      "",
      "## 指摘1: 1件だけの再現性",
      "",
      "- 以前: US 特許 1 件のみ Weekly Digest まで完全成功。",
      f"- 今回: JP seed {summary.seed_count} 件（{', '.join(summary.seed_publications)}）で "
      f"Manual Claims → skeleton → Paper/Web → Link → Watch → Digest preview まで横展開。",
      f"- E2E complete: {summary.completed_end_to_end_count}/{summary.seed_count}.",
      "",
      "## 指摘2: Stage 4 以降未検証",
      "",
      "- 以前の Core Validation Summary では Stage 4 以降未検証と記載。",
      "- 今回 JP seed で End-to-End Chain を UI 上で実行し、Stage 4〜8 の成果物を確認。",
      f"- ただし Paper/Web/Link/Watch/Digest は **candidate / preview** であり、最終結論ではない。",
      f"- query_plan_ready: Stage 4={summary.stage4_query_plan_count}, Stage 5={summary.stage5_query_plan_count} "
      "（実データ取得済みと混同しない）。",
      "",
      "## 指摘3: SMTP / scheduler 偏重",
      "",
      "- Phase24.4A〜C でコア検証（Manual Claims → E2E Chain）に回帰。",
      "- UI からメール送信・scheduler 登録は行わない。Digest は preview only。",
      "",
      "## 指摘4: MVP Freeze 最終判断",
      "",
      f"- **{summary.freeze_readiness}**",
      "- DB 永続化は Post-MVP。",
      f"- {LEGAL_CAUTION}",
      "",
    ],
  )


def render_readme_final_patch_notes_md(summary: FinalValidationSummary) -> str:
  return "\n".join(
    [
      "# README Final Patch Notes (Phase 24.4D)",
      "",
      "## 追記すべき内容",
      "",
      "### US デモ",
      "",
      "- US-12565719-B2: Weekly Digest まで complete_existing_demo",
      "",
      "### JP 別テーマ E2E",
      "",
      f"- テーマ: {summary.theme_name} (`{summary.theme_id}`)",
      f"- seeds: {', '.join(summary.seed_publications)}",
      f"- E2E complete: {summary.completed_end_to_end_count}/{summary.seed_count}",
      "",
      "### candidate / preview",
      "",
      "- Paper: supporting evidence candidate（証明ではない）",
      "- Web: signal candidate",
      "- Link: 確認候補（直接関係の証明ではない）",
      "- Watch: 監視候補",
      "- Digest: preview only（送信なし）",
      "",
      "### query_plan と実データ",
      "",
      f"- Stage 4 query_plan_ready: {summary.stage4_query_plan_count}件",
      f"- Stage 5 query_plan_ready: {summary.stage5_query_plan_count}件",
      "",
      "### その他",
      "",
      f"- {LEGAL_CAUTION}",
      "- DB 永続化は Post-MVP",
      "",
    ],
  )


def render_demo_script_final_patch_notes_md(summary: FinalValidationSummary) -> str:
  return "\n".join(
    [
      "# Demo Script Final Patch Notes (Phase 24.4D)",
      "",
      "## デモで見せる順序",
      "",
      "1. US デモ — Weekly Digest まで",
      "2. 別テーマ検証タブ",
      "3. Seed 別進捗 — 3件 Stage 3 pass",
      "4. JP Seed End-to-End Chain — 各ステップ",
      "5. Final Stage 表（Stage 2〜8）",
      "6. candidate / preview であることを口頭で説明",
      "",
      f"## seeds: {', '.join(summary.seed_publications)}",
      "",
      f"- freeze_readiness: {summary.freeze_readiness}",
      "",
      "## 言わないこと",
      "",
      "- FTO / 侵害 / 有効性の断定",
      "- query_plan を実データ取得済みと混同させない",
      "",
    ],
  )


def render_limitations_final_patch_notes_md(summary: FinalValidationSummary) -> str:
  return "\n".join(
    [
      "# Known Limitations Final Patch Notes (Phase 24.4D)",
      "",
      "## 追記すべき制限",
      "",
      f"- {QUERY_PLAN_CAUTION}",
      f"- {PAPER_CAUTION}",
      f"- {WEB_SIGNAL_CAUTION}",
      f"- {LINK_CAUTION}",
      f"- {WATCH_CAUTION}",
      f"- {DIGEST_CAUTION}",
      f"- {LEGAL_CAUTION}",
      "",
      f"- evidence_level: {summary.evidence_level}",
      f"- freeze: {summary.freeze_readiness}",
      "",
    ],
  )


def render_mvp_freeze_final_notes_md(summary: FinalValidationSummary) -> str:
  return "\n".join(
    [
      "# MVP Freeze Final Notes (Phase 24.4D)",
      "",
      f"- freeze_readiness: **{summary.freeze_readiness}**",
      f"- evidence_level: {summary.evidence_level}",
      f"- JP E2E complete: {summary.completed_end_to_end_count}/{summary.seed_count}",
      "- US demo + JP cross-theme E2E で MVP Freeze 判断",
      "- candidate/preview 制限を README / demo / limitations に明記",
      "",
    ],
  )


def render_final_known_limitations_md(summary: FinalValidationSummary) -> str:
  return render_limitations_final_patch_notes_md(summary).replace(
    "Known Limitations Final Patch Notes",
    "Final Known Limitations",
  )


def save_final_validation_summary_pack(
  summary: FinalValidationSummary,
  output_dir: Path | str,
) -> dict[str, Path]:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  paths = {
    "final_end_to_end_validation_summary_md": out / "final_end_to_end_validation_summary.md",
    "final_end_to_end_validation_summary_json": out / "final_end_to_end_validation_summary.json",
    "seed_end_to_end_status_csv": out / "seed_end_to_end_status.csv",
    "freeze_readiness_final_md": out / "freeze_readiness_final.md",
    "reviewer_response_final_md": out / "reviewer_response_final.md",
    "mvp_freeze_final_notes_md": out / "mvp_freeze_final_notes.md",
    "final_known_limitations_md": out / "final_known_limitations.md",
    "readme_final_patch_notes_md": out / "readme_final_patch_notes.md",
    "demo_script_final_patch_notes_md": out / "demo_script_final_patch_notes.md",
    "limitations_final_patch_notes_md": out / "limitations_final_patch_notes.md",
  }
  paths["final_end_to_end_validation_summary_md"].write_text(
    render_final_end_to_end_validation_summary_md(summary),
    encoding="utf-8",
  )
  paths["final_end_to_end_validation_summary_json"].write_text(
    json.dumps(summary.to_dict(), indent=2, ensure_ascii=False),
    encoding="utf-8",
  )
  if summary.seed_statuses:
    pd.DataFrame(summary.seed_statuses).to_csv(
      paths["seed_end_to_end_status_csv"],
      index=False,
      encoding="utf-8",
    )
  else:
    paths["seed_end_to_end_status_csv"].write_text("", encoding="utf-8")
  paths["freeze_readiness_final_md"].write_text(
    render_freeze_readiness_final_md(summary),
    encoding="utf-8",
  )
  paths["reviewer_response_final_md"].write_text(
    render_reviewer_response_final_md(summary),
    encoding="utf-8",
  )
  paths["mvp_freeze_final_notes_md"].write_text(
    render_mvp_freeze_final_notes_md(summary),
    encoding="utf-8",
  )
  paths["final_known_limitations_md"].write_text(
    render_final_known_limitations_md(summary),
    encoding="utf-8",
  )
  paths["readme_final_patch_notes_md"].write_text(
    render_readme_final_patch_notes_md(summary),
    encoding="utf-8",
  )
  paths["demo_script_final_patch_notes_md"].write_text(
    render_demo_script_final_patch_notes_md(summary),
    encoding="utf-8",
  )
  paths["limitations_final_patch_notes_md"].write_text(
    render_limitations_final_patch_notes_md(summary),
    encoding="utf-8",
  )
  return paths
